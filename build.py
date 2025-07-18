import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_DIR = PROJECT_ROOT / 'src'
PARTITIONER_DIR = SRC_DIR / 'partitioner'
PARTITIONER_BUILD_DIR = PARTITIONER_DIR / 'build'
BIN_DIR = PROJECT_ROOT / 'bin'
BINARIES_DIR = BIN_DIR / 'binaries'

PYTHON_SCRIPTS = [
    'AriParti_launcher.py',
    'control_message.py',
    'coordinator.py',
    'dispatcher.py',
    'leader.py',
    'partitioner.py',
    'partition_tree.py'
]

PARTITIONER_BINARY_SRC = PARTITIONER_BUILD_DIR / 'z3'
PARTITIONER_BINARY_DEST = BINARIES_DIR / 'partitioner-bin'

def log(msg):
    print(f"[build.py] {msg}")

def ensure_dir(path: Path):
    if not path.exists():
        log(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)

def copy_file(src: Path, dest: Path):
    log(f"Copying {src} -> {dest}")
    shutil.copy2(src, dest)

def run_command(command, cwd=None):
    log(f"Running command: {' '.join(command)} (cwd={cwd})")
    result = subprocess.run(command, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log(result.stdout.decode())
    if result.stderr:
        log(result.stderr.decode())

def build_partitioner():
    log("=== Building Partitioner ===")
    # Clean previous build if exists
    if PARTITIONER_BUILD_DIR.exists():
        log(f"Cleaning previous build directory: {PARTITIONER_BUILD_DIR}")
        shutil.rmtree(PARTITIONER_BUILD_DIR)

    # Run mk_make.py to prepare build
    run_command(['python', 'scripts/mk_make.py'], cwd=PARTITIONER_DIR)

    # Run make inside build/
    run_command(['make', '-j'], cwd=PARTITIONER_BUILD_DIR)

def main():
    log("=== AriParti Build Script Started ===")

    # 1. Create bin and bin/binaries
    ensure_dir(BIN_DIR)
    ensure_dir(BINARIES_DIR)

    # 2. Copy Python scripts from src to bin
    for script in PYTHON_SCRIPTS:
        src_file = SRC_DIR / script
        dest_file = BIN_DIR / script
        if not src_file.exists():
            raise FileNotFoundError(f"Missing source file: {src_file}")
        copy_file(src_file, dest_file)

    # 3. Build partitioner
    build_partitioner()
    
    # 4. Copy partitioner binary
    if not PARTITIONER_BINARY_SRC.exists():
        raise FileNotFoundError(f"Built partitioner binary not found at {PARTITIONER_BINARY_SRC}")
    copy_file(PARTITIONER_BINARY_SRC, PARTITIONER_BINARY_DEST)

    log("Build completed successfully.")
    log(f"Partitioner binary installed at: {PARTITIONER_BINARY_DEST}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Build failed: {e}")
        exit(1)
