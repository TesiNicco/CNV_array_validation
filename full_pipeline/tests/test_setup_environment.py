"""Exercise setup command flow without installing or altering environments."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SETUP = Path(__file__).resolve().parents[2] / 'setup/setup_environment.sh'
FAKE_MAMBA = '''#!{python}
import json
import os
import sys
args = sys.argv[1:]
with open(os.environ['SETUP_TEST_LOG'], 'a') as out:
    out.write(json.dumps({{'args': args, 'always_yes': os.getenv('CONDA_ALWAYS_YES')}}) + '\\n')
if args == ['run', '--help']:
    print('--no-capture-output')
elif args and args[0] == 'run' and args[-1] == 'true':
    sys.exit(0 if os.environ['SETUP_TEST_EXISTS'] == 'yes' else 1)
elif args[:2] in [['env', 'update'], ['env', 'create']]:
    if os.environ.get('SETUP_TEST_FAIL') == 'environment':
        sys.exit(9)
elif any(arg.endswith('install_penncnv.sh') for arg in args):
    if os.environ.get('SETUP_TEST_FAIL') == 'penncnv-install':
        sys.exit(5)
elif any(arg.endswith('install_torch_runtime.R') for arg in args):
    if os.environ.get('SETUP_TEST_FAIL') == 'runtime-install':
        sys.exit(6)
elif any(arg.endswith('install_r_dependencies.R') for arg in args):
    if os.environ.get('SETUP_TEST_FAIL') == 'r-install':
        sys.exit(8)
elif any(arg.endswith('check_environment.R') for arg in args):
    if os.environ.get('SETUP_TEST_FAIL') == 'r-check':
        sys.exit(7)
'''


class SetupTests(unittest.TestCase):
    def run_setup(self, exists='yes', fail='', arguments=()):
        with tempfile.TemporaryDirectory(prefix='cnv-setup-test-') as tmp:
            root = Path(tmp)
            fake = root / 'mamba'
            fake.write_text(FAKE_MAMBA.format(python=sys.executable))
            fake.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       SETUP_TEST_LOG=str(root / 'commands.jsonl'),
                       SETUP_TEST_EXISTS=exists, SETUP_TEST_FAIL=fail)
            result = subprocess.run(['bash', str(SETUP), *arguments], cwd=root,
                                    env=env, capture_output=True, text=True)
            log = root / 'commands.jsonl'
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, commands

    def test_existing_environment_is_updated_and_checks_run(self):
        result, commands = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands[1]['args'][:2], ['env', 'update'])
        self.assertEqual(commands[1]['always_yes'], 'true')
        self.assertEqual(commands[1]['args'][-1], str(SETUP.parent / 'environment.yml'))
        r_commands = [c['args'] for c in commands if 'Rscript' in c['args']]
        self.assertTrue(r_commands[0][-1].endswith('install_torch_runtime.R'))
        self.assertTrue(r_commands[1][-1].endswith('install_r_dependencies.R'))
        self.assertTrue(r_commands[2][-1].endswith('check_environment.R'))
        self.assertIn('Environment setup and checks passed.', result.stdout)

    def test_missing_environment_is_created(self):
        result, commands = self.run_setup(exists='no')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands[1]['args'][:2], ['env', 'create'])
        self.assertFalse(any('--force' in c['args'] or '--prune' in c['args'] for c in commands))

    def test_penncnv_installed_by_default_before_r_setup(self):
        result, commands = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        install = next(i for i, c in enumerate(commands) if any(a.endswith('install_penncnv.sh') for a in c['args']))
        runtime = next(i for i, c in enumerate(commands) if any(a.endswith('install_torch_runtime.R') for a in c['args']))
        self.assertLess(install, runtime)

    def test_penncnv_can_be_skipped(self):
        result, commands = self.run_setup(arguments=('--skip-penncnv',))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(any(a.endswith('install_penncnv.sh') for a in c['args']) for c in commands))

    def test_penncnv_failure_stops_before_r_setup(self):
        result, commands = self.run_setup(fail='penncnv-install')
        self.assertEqual(result.returncode, 5)
        self.assertFalse(any('Rscript' in c['args'] for c in commands))
        self.assertNotIn('checks passed', result.stdout)

    def test_custom_name_used_for_every_environment_command(self):
        result, commands = self.run_setup(arguments=('--name', 'collaborator-test'))
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in commands:
            args = command['args']
            if '--name' in args:
                self.assertEqual(args[args.index('--name') + 1], 'collaborator-test')

    def test_environment_failure_stops_before_r_install(self):
        result, commands = self.run_setup(fail='environment')
        self.assertEqual(result.returncode, 9)
        self.assertFalse(any('Rscript' in c['args'] for c in commands))

    def test_r_install_failure_stops_before_checks(self):
        result, commands = self.run_setup(fail='r-install')
        self.assertEqual(result.returncode, 8)
        self.assertFalse(any(any(arg.endswith('check_environment.R') for arg in c['args']) for c in commands))
        self.assertNotIn('checks passed', result.stdout)

    def test_runtime_install_failure_stops_before_r_packages(self):
        result, commands = self.run_setup(fail='runtime-install')
        self.assertEqual(result.returncode, 6)
        self.assertFalse(any(any(arg.endswith('install_r_dependencies.R') for arg in c['args']) for c in commands))
        self.assertNotIn('checks passed', result.stdout)

    def test_tensor_check_failure_does_not_report_success(self):
        result, commands = self.run_setup(fail='r-check')
        self.assertEqual(result.returncode, 7)
        self.assertNotIn('checks passed', result.stdout)
        self.assertFalse(any('python' in c['args'] for c in commands))

    def test_missing_name_argument_is_rejected(self):
        result, commands = self.run_setup(arguments=('--name',))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(commands, [])


if __name__ == '__main__':
    unittest.main()
