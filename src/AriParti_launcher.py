import os
import re
import sys
import json
import time
import shlex
import shutil
import string
import hashlib
import random
import logging
import platform
import subprocess
import socket
from datetime import datetime

def generate_random_string(length=16):
    """Generate a random alphanumeric string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_logic(file_path):
    """Extract logic from SMT-LIB file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            match = re.search(r'set-logic ([A-Z_]+)', content)
            return match.group(1) if match else None
    except Exception as e:
        logging.error(f"Failed to read formula file: {e}")
        return None

def check_get_model_flag(file_path):
    """Check if (get-model) exists uncommented in SMT2 file."""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if '(get-model)' in line.split(';')[0]:
                    return 1
        return 0
    except Exception as e:
        logging.error(f"Error checking get-model flag: {e}")
        return 0

def init_logging(log_dir):
    """Initialize logging."""
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename=os.path.join(log_dir, 'launcher.log'),
        level=logging.DEBUG
    )
    logging.info("=== AriParti Launcher Started ===")

def require_bool(config, field):
    value = config[field]
    if not isinstance(value, bool):
        sys.exit(f"'{field}' must be a JSON boolean")
    return value

def require_positive_int(config, field):
    value = config[field]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        sys.exit(f"'{field}' must be a positive integer")
    return value

def require_string(config, field):
    value = config[field]
    if not isinstance(value, str) or not value:
        sys.exit(f"'{field}' must be a non-empty string")
    return value

def load_config(config_path):
    """Load JSON config and validate fields."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        sys.exit(f"Failed to load config: {e}")
    
    required_fields = ['formula_file', 'timeout_seconds', 'base_solver', 'mode']
    for field in required_fields:
        if field not in config:
            sys.exit(f"Missing required field: {field}")

    require_string(config, 'formula_file')
    require_string(config, 'base_solver')
    require_string(config, 'mode')
    require_positive_int(config, 'timeout_seconds')
    if os.path.basename(config['base_solver']) != config['base_solver']:
        sys.exit("'base_solver' must be a binary name under the launcher's binaries directory, not a path")
    if not os.path.isfile(config['formula_file']):
        sys.exit(f"Formula file does not exist: {config['formula_file']}")

    if config['mode'] == 'parallel':
        if 'parallel_core' not in config:
            sys.exit("'parallel_core' is required for mode=parallel")
        require_positive_int(config, 'parallel_core')
        config.setdefault('network_subnet', '127.0.0.1/32')
        config['worker_node_ips'] = ['localhost']
        config['worker_node_cores'] = [config['parallel_core']]
    elif config['mode'] == 'distributed':
        for field in ['worker_node_ips', 'worker_node_cores', 'network_subnet']:
            if field not in config:
                sys.exit(f"'{field}' is required for mode=distributed")
        if not isinstance(config['worker_node_ips'], list) or not config['worker_node_ips']:
            sys.exit("'worker_node_ips' must be a non-empty list")
        if not isinstance(config['worker_node_cores'], list) or not config['worker_node_cores']:
            sys.exit("'worker_node_cores' must be a non-empty list")
        if len(config['worker_node_ips']) != len(config['worker_node_cores']):
            sys.exit("'worker_node_ips' and 'worker_node_cores' must have the same length")
        for idx, ip in enumerate(config['worker_node_ips']):
            if not isinstance(ip, str) or not ip:
                sys.exit(f"'worker_node_ips[{idx}]' must be a non-empty string")
        for idx, cores in enumerate(config['worker_node_cores']):
            if not isinstance(cores, int) or isinstance(cores, bool) or cores <= 0:
                sys.exit(f"'worker_node_cores[{idx}]' must be a positive integer")
        require_string(config, 'network_subnet')
    else:
        sys.exit(f"Unsupported mode: {config['mode']}")

    config.setdefault('output_dir', './output')
    require_string(config, 'output_dir')
    config.setdefault('output_total_time', False)
    config.setdefault('bicp_enabled', True)
    config.setdefault('clause_reduction_enabled', True)
    require_bool(config, 'output_total_time')
    require_bool(config, 'bicp_enabled')
    require_bool(config, 'clause_reduction_enabled')
    ablation = config.setdefault('ablation', {})
    if not isinstance(ablation, dict):
        sys.exit("'ablation' must be a JSON object when provided")
    ablation.setdefault('isolated_original_solver', True)
    ablation.setdefault('pre_partition', True)
    ablation.setdefault('dynamic_splitting', True)
    ablation.setdefault('terminate_on_demand', True)
    ablation.setdefault('keep_temp', False)
    ablation.setdefault('allow_no_bicp_ablation', False)
    ablation.setdefault('partitioner_extra_args', [])
    for field in [
        'isolated_original_solver',
        'pre_partition',
        'dynamic_splitting',
        'terminate_on_demand',
        'keep_temp',
        'allow_no_bicp_ablation',
    ]:
        if not isinstance(ablation[field], bool):
            sys.exit(f"'ablation.{field}' must be a JSON boolean")
    if not isinstance(ablation['partitioner_extra_args'], list):
        sys.exit("'ablation.partitioner_extra_args' must be a list")
    ablation['partitioner_extra_args'] = [str(arg) for arg in ablation['partitioner_extra_args']]
    if not config['bicp_enabled'] and not ablation['allow_no_bicp_ablation']:
        sys.exit(
            "bicp_enabled=false is the non-default pure-ICP ablation configuration. "
            "Set ablation.allow_no_bicp_ablation=true to confirm that this "
            "ablation variant was selected intentionally."
        )
    os.makedirs(config['output_dir'], exist_ok=True)
    return config

def get_git_commit(repo_dir):
    """Return the current git commit for repo_dir, or an explicit missing marker."""
    try:
        result = subprocess.run(
            ['git', '-C', repo_dir, 'rev-parse', 'HEAD'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        return f'unavailable: {e}'

def sha256_file(path):
    """Return the SHA-256 digest for a file, or an explicit missing marker."""
    if not os.path.isfile(path):
        return 'missing'
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def command_version(path):
    """Return best-effort --version output for a binary."""
    if not os.path.isfile(path):
        return 'missing'
    try:
        result = subprocess.run(
            [path, '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            first_line = output.splitlines()[0]
            lowered = first_line.lower()
            if result.returncode == 0 and 'invalid option' not in lowered and 'unknown option' not in lowered:
                return first_line
            return f'unavailable: --version exited with {result.returncode}: {first_line}'
        return f'unavailable: --version exited with {result.returncode} and no output'
    except Exception as e:
        return f'unavailable: {e}'

def write_run_metadata(config, config_path, temp_folder, rankfile_path, mpi_command=None):
    """Write machine-readable metadata for this run."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    solver_bin = os.path.join(script_dir, 'binaries', config['base_solver'])
    partitioner_bin = os.path.join(script_dir, 'binaries', 'partitioner-bin')
    metadata = {
        'created_at_utc': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'argv': sys.argv,
        'config_path': os.path.abspath(config_path),
        'effective_config': config,
        'cwd': os.getcwd(),
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'python_version': sys.version,
        'git_commit': get_git_commit(repo_dir),
        'temp_folder': temp_folder,
        'rankfile_path': rankfile_path,
        'mpi_command': mpi_command,
        'binaries': {
            'solver': {
                'path': solver_bin,
                'sha256': sha256_file(solver_bin),
                'version': command_version(solver_bin)
            },
            'partitioner': {
                'path': partitioner_bin,
                'sha256': sha256_file(partitioner_bin),
                'version': command_version(partitioner_bin)
            }
        }
    }
    metadata_path = os.path.join(config['output_dir'], 'run-metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2, sort_keys=True)
        f.write('\n')
    logging.info(f"Run metadata written to {metadata_path}")

def prepare_rankfile(rankfile_path, worker_node_ips):
    """Write MPI rankfile."""
    try:
        with open(rankfile_path, 'w') as f:
            for idx, ip in enumerate(worker_node_ips):
                f.write(f"rank {idx}={ip} slot=*\n")
            # Add extra ranks for leader and isolated coordinator
            f.write(f"rank {len(worker_node_ips)}={worker_node_ips[0]} slot=*\n")
            f.write(f"rank {len(worker_node_ips)+1}={worker_node_ips[0]} slot=*\n")
        logging.info(f"Rankfile written to {rankfile_path}")
    except Exception as e:
        sys.exit(f"Failed to write rankfile: {e}")

def prepare_temp_folder():
    """Create temporary folder."""
    temp_path = os.path.join('/tmp/ap-files', generate_random_string())
    os.makedirs(temp_path, exist_ok=True)
    logging.info(f"Temporary folder created: {temp_path}")
    return temp_path

def build_mpi_command(config, temp_folder, rankfile_path):
    """Build MPI execution command."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dispatcher = os.path.join(script_dir, 'dispatcher.py')
    solver_bin = os.path.join(script_dir, 'binaries', config['base_solver'])
    partitioner_bin = os.path.join(script_dir, 'binaries', 'partitioner-bin')

    for binary in [solver_bin, partitioner_bin]:
        if not os.path.isfile(binary):
            sys.exit(f"Missing binary: {binary}")

    cmd = [
        'mpiexec',
        '--mca', 'oob_tcp_if_include', config['network_subnet'],
        '--mca', 'btl_tcp_if_include', config['network_subnet'],
        '--mca', 'btl', 'self,tcp',
        '--allow-run-as-root',
        '--use-hwthread-cpus',
        '--bind-to', 'none',
        '--rankfile', rankfile_path,
        'python3', dispatcher,
        '--temp-dir', temp_folder,
        '--output-dir', config['output_dir'],
        '--get-model-flag', str(check_get_model_flag(config['formula_file'])),
        '--file', config['formula_file'],
        '--time-limit', str(config['timeout_seconds']),
        '--solver', solver_bin,
        '--available-cores-list', json.dumps(config['worker_node_cores']),
        '--partitioner', partitioner_bin,
        '--ablation-json', json.dumps(config['ablation'], sort_keys=True),
        '--bicp-enabled', str(int(config['bicp_enabled'])),
        '--clause-reduction-enabled', str(int(config['clause_reduction_enabled']))
    ]
    return cmd

def adjust_cores_for_isolated_coordinator(config):
    """Adjust cores: reserve cores for leader and isolated coordinator."""
    server_0_cores = config['worker_node_cores'][0]
    if server_0_cores >= 16:
        if 'isolated_coordinator_cores' in config:
            reserved_cores = require_positive_int(config, 'isolated_coordinator_cores')
        else:
            reserved_cores = 8
    elif server_0_cores >= 8:
        reserved_cores = 4
    elif server_0_cores >= 4:
        reserved_cores = 2
    else:
        sys.exit(f"Error: Not enough cores on first node to reserve cores for isolated coordinator.")
    if reserved_cores >= server_0_cores:
        sys.exit(
            "'isolated_coordinator_cores' must be smaller than the first node's available cores "
            f"({server_0_cores})"
        )
    
    # Reserve cores
    config['worker_node_cores'][0] -= reserved_cores  # reserved_cores for coordinator
    config['worker_node_cores'].append(reserved_cores)
    logging.info(f"Reserved {reserved_cores} cores for isolated coordinator on first node.")
    logging.info(f"Adjusted worker_node_cores to {config['worker_node_cores']}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 AriParti_launcher.py <config.json>")
    
    config_path = sys.argv[1]
    config = load_config(config_path)
    log_dir = os.path.join(config['output_dir'], 'logs')
    init_logging(log_dir)

    adjust_cores_for_isolated_coordinator(config)
    logging.info(f"Configuration: {json.dumps(config, indent=2)}")

    temp_folder = prepare_temp_folder()
    rankfile_path = os.path.join(config['output_dir'], 'rankfile')
    prepare_rankfile(rankfile_path, config['worker_node_ips'])

    cmd = build_mpi_command(config, temp_folder, rankfile_path)
    logging.info(f"MPI Command: {shlex.join(cmd)}")
    write_run_metadata(config, config_path, temp_folder, rankfile_path, cmd)

    if config['output_total_time']:
        start_time = time.time()

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.info("STDOUT:\n" + result.stdout)
        logging.info("STDERR:\n" + result.stderr)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            logging.error(f"MPI command failed with return code {result.returncode}")
            sys.exit(result.returncode)
    except Exception as e:
        logging.error(f"Subprocess failed: {e}")
        sys.exit(1)
    
    if config['output_total_time']:
        elapsed = time.time() - start_time
        logging.info(f"Total execution time: {elapsed:.2f} seconds")
        print(f"\nTotal execution time: {elapsed:.2f} seconds")
