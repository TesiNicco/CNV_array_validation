#!/usr/bin/env bash
# Install PennCNV 1.0.5 with the selected environment's Perl and compiler.
set -euo pipefail
SOURCE_ARCHIVE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-archive)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo "--source-archive requires a local PennCNV 1.0.5 tar.gz file" >&2
                exit 2
            fi
            SOURCE_ARCHIVE="$2"; shift 2 ;;
        -h|--help)
            echo 'Usage: bash install_penncnv.sh [--source-archive /path/to/v1.0.5.tar.gz]'
            echo 'Run inside the selected environment. Installs at $CONDA_PREFIX/opt/PennCNV-1.0.5.'
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
if [[ -z "${CONDA_PREFIX:-}" || ! -x "$CONDA_PREFIX/bin/perl" ]]; then
    echo "Activate the analysis environment, or run setup_environment.sh." >&2
    exit 1
fi
export PATH="$CONDA_PREFIX/bin:$PATH"
PERL_BIN="$CONDA_PREFIX/bin/perl"
INSTALL_DIR="$CONDA_PREFIX/opt/PennCNV-1.0.5"
export PENNCNV_INSTALL_DIR="$INSTALL_DIR"

verify_extension() {
    "$PERL_BIN" -e 'use lib $ARGV[0]; require khmm; die "PennCNV HMM function missing\n" unless defined &khmm::testVit_CHMM; print "PennCNV extension OK with Perl $^V\n";' "$INSTALL_DIR/kext"
}

if [[ -d "$INSTALL_DIR" ]] && verify_extension >/dev/null 2>&1; then
    echo "PennCNV already installed and compatible: $INSTALL_DIR"
    verify_extension
    exit 0
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
    mkdir -p -- "$CONDA_PREFIX/opt"
    BUILD_DIR="$(mktemp -d "$CONDA_PREFIX/opt/.penncnv-download.XXXXXX")"
    # Stage on the destination filesystem, avoiding large source extraction in /tmp.
    trap 'rm -rf -- "$BUILD_DIR"' EXIT
    export PENNCNV_BUILD_DIR="$BUILD_DIR" PENNCNV_SOURCE_ARCHIVE="$SOURCE_ARCHIVE"
    python - <<'PY'
import os
import tarfile
import urllib.request
from pathlib import Path

build = Path(os.environ['PENNCNV_BUILD_DIR'])
archive = os.environ['PENNCNV_SOURCE_ARCHIVE']
if archive:
    archive = Path(archive).expanduser().resolve()
else:
    archive = build / 'v1.0.5.tar.gz'
    print('Downloading official PennCNV 1.0.5 release', flush=True)
    with urllib.request.urlopen('https://github.com/WGLab/PennCNV/archive/v1.0.5.tar.gz', timeout=120) as source, archive.open('wb') as target:
        import shutil
        shutil.copyfileobj(source, target)
with tarfile.open(archive) as handle:
    members = handle.getmembers()
    for member in members:
        parts = Path(member.name).parts
        if not parts or parts[0] != 'PennCNV-1.0.5' or '..' in parts or not (member.isfile() or member.isdir()):
            raise ValueError('Unexpected PennCNV archive member: ' + member.name)
    handle.extractall(build)
source = build / 'PennCNV-1.0.5'
for name in ('detect_cnv.pl', 'kext/Makefile', 'kext/kc.c', 'lib/hhall.hmm'):
    if not (source / name).is_file():
        raise ValueError('Incomplete PennCNV release: ' + name)
source.rename(Path(os.environ['PENNCNV_INSTALL_DIR']))
PY
fi

if [[ ! -f "$INSTALL_DIR/kext/Makefile" ]]; then
    echo "Incomplete PennCNV installation at $INSTALL_DIR; inspect it before retrying." >&2
    exit 1
fi

python - <<'PY'
import os
from pathlib import Path
source = Path(os.environ['PENNCNV_INSTALL_DIR']) / 'kext/kc.c'
text = source.read_text()
# GCC's format-security check rejects these two old Perl diagnostic wrappers.
# Pass their messages as literal strings; no CNV calculation is changed.
text = text.replace('croak (error_text);', 'croak ("%s", error_text);')
text = text.replace('warn (error_text);', 'warn ("%s", error_text);')
source.write_text(text)
PY

BUILD_LOG="$INSTALL_DIR/installation.log"
COMPILER="${CC:-$("$PERL_BIN" -MConfig -e 'print $Config{cc}')}"
echo "Compiling PennCNV using $PERL_BIN (log: $BUILD_LOG)"
if ! { make -C "$INSTALL_DIR/kext" clean && make -C "$INSTALL_DIR/kext" "CC=$COMPILER" "LD=$COMPILER"; } >"$BUILD_LOG" 2>&1; then
    tail -n 60 "$BUILD_LOG" >&2
    echo "PennCNV compilation failed. Full log: $BUILD_LOG" >&2
    exit 1
fi
verify_extension
echo "PennCNV installed at: $INSTALL_DIR"
