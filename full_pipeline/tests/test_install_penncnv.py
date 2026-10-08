"""Offline installer tests for path, build failures and retry behavior."""
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[2] / 'setup/install_penncnv.sh'


class PennInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='penn-installer-test-')
        self.root = Path(self.temp.name)
        self.prefix = self.root / 'env'
        bins = self.prefix / 'bin'
        bins.mkdir(parents=True)
        (bins / 'python').symlink_to(sys.executable)
        self.env = dict(os.environ, CONDA_PREFIX=str(self.prefix),
                        PENN_TEST_LOG=str(self.root / 'commands.jsonl'))
        self.script(bins / 'perl', '''import json, os, sys
args = sys.argv[1:]
with open(os.environ['PENN_TEST_LOG'], 'a') as log:
    log.write(json.dumps(['perl', *args]) + '\\n')
if '-MConfig' in args:
    print('gcc', end='')
else:
    from pathlib import Path
    sys.exit(0 if (Path(args[-1]) / 'compiled.ok').exists() else 1)
''')
        self.script(bins / 'make', '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['PENN_TEST_LOG'], 'a') as log:
    log.write(json.dumps(['make', *args]) + '\\n')
path = Path(args[args.index('-C') + 1]) / 'compiled.ok'
if 'clean' in args:
    if path.exists(): path.unlink()
elif os.environ.get('PENN_TEST_FAIL') == 'yes':
    print('Simulated compiler failure')
    sys.exit(3)
else:
    path.write_text('compiled')
''')
        self.archive = self.root / 'source.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as handle:
            for name, text in {'detect_cnv.pl': 'test', 'lib/hhall.hmm': 'test',
                               'kext/Makefile': 'test',
                               'kext/kc.c': 'croak (error_text);\nwarn (error_text);\n'}.items():
                data = text.encode()
                info = tarfile.TarInfo('PennCNV-1.0.5/' + name)
                info.size = len(data)
                handle.addfile(info, io.BytesIO(data))

    def tearDown(self):
        self.temp.cleanup()

    def script(self, path, text):
        path.write_text('#!' + sys.executable + '\n' + text)
        path.chmod(0o755)

    def install(self):
        return subprocess.run(['bash', str(INSTALLER), '--source-archive', str(self.archive)],
                              env=self.env, capture_output=True, text=True)

    def test_installs_at_environment_opt_path_and_can_be_rerun(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.prefix / 'opt/PennCNV-1.0.5'
        self.assertTrue((installed / 'kext/compiled.ok').is_file())
        self.assertIn('croak ("%s", error_text);', (installed / 'kext/kc.c').read_text())
        self.assertFalse(list((self.prefix / 'opt').glob('.penncnv-download.*')))
        commands = (self.root / 'commands.jsonl').read_text()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        later = (self.root / 'commands.jsonl').read_text()[len(commands):]
        self.assertNotIn('"make"', later)
        self.assertIn('already installed and compatible', result.stdout)

    def test_build_failure_keeps_log_and_retry_rebuilds(self):
        self.env['PENN_TEST_FAIL'] = 'yes'
        result = self.install()
        self.assertEqual(result.returncode, 1)
        self.assertIn('compilation failed', result.stderr)
        installed = self.prefix / 'opt/PennCNV-1.0.5'
        self.assertIn('Simulated compiler failure', (installed / 'installation.log').read_text())
        del self.env['PENN_TEST_FAIL']
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_archive_path_traversal_is_rejected(self):
        with tarfile.open(self.archive, 'w:gz') as handle:
            info = tarfile.TarInfo('PennCNV-1.0.5/../../outside')
            info.size = 4
            handle.addfile(info, io.BytesIO(b'test'))
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected PennCNV archive member', result.stderr)
        self.assertFalse((self.prefix / 'opt/PennCNV-1.0.5').exists())


if __name__ == '__main__':
    unittest.main()
