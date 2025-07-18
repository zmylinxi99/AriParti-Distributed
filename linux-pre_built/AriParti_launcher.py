import os
import re
import sys
import json
import time
import shlex
import shutil
import string
import random
import logging
import subprocess
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

    if config['mode'] == 'parallel':
        if 'parallel_core' not in config:
            sys.exit("'parallel_core' is required for mode=parallel")
        config.setdefault('network_interface', 'lo')
        config['worker_node_ips'] = ['localhost']
        config['worker_node_cores'] = [config['parallel_core']]
    elif config['mode'] == 'distributed':
        for field in ['worker_node_ips', 'worker_node_cores', 'network_interface']:
            if field not in config:
                sys.exit(f"'{field}' is required for mode=distributed")
    else:
        sys.exit(f"Unsupported mode: {config['mode']}")

    config.setdefault('output_dir', './output')
    config.setdefault('output_total_time', False)
    os.makedirs(config['output_dir'], exist_ok=True)
    return config

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
        '--mca', 'btl_tcp_if_include', config['network_interface'],
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
        '--partitioner', partitioner_bin
    ]
    return shlex.join(cmd)

def adjust_cores_for_isolated_coordinator(config):
    """Adjust cores: reserve cores for leader and isolated coordinator."""
    server_0_cores = config['worker_node_cores'][0]
    if server_0_cores >= 16:
        reserved_cores = config.get('isolated_coordinator_cores', 8)
    elif server_0_cores >= 8:
        reserved_cores = 4
    elif server_0_cores >= 4:
        reserved_cores = 2
    else:
        sys.exit(f"Error: Not enough cores on first node to reserve cores for isolated coordinator.")
    
    # Reserve cores
    config['worker_node_cores'][0] -= reserved_cores  # reserved_cores for coordinator
    config['worker_node_cores'].append(reserved_cores)
    logging.info(f"Reserved {reserved_cores} cores for isolated coordinator on first node.")
    logging.info(f"Adjusted worker_node_cores to {config['worker_node_cores']}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 AriParti_launcher.py <config.json>")
    
    config = load_config(sys.argv[1])
    log_dir = os.path.join(config['output_dir'], 'logs')
    init_logging(log_dir)

    adjust_cores_for_isolated_coordinator(config)
    logging.info(f"Configuration: {json.dumps(config, indent=2)}")

    temp_folder = prepare_temp_folder()
    rankfile_path = os.path.join(config['output_dir'], 'rankfile')
    prepare_rankfile(rankfile_path, config['worker_node_ips'])

    cmd = build_mpi_command(config, temp_folder, rankfile_path)
    logging.info(f"MPI Command: {cmd}")

    if config['output_total_time']:
        start_time = time.time()

    try:
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("STDOUT:\n" + result.stdout.decode())
        logging.info("STDERR:\n" + result.stderr.decode())
        sys.stdout.write(result.stdout.decode())
    except Exception as e:
        logging.error(f"Subprocess failed: {e}")
        sys.exit(1)
    
    if config['output_total_time']:
        elapsed = time.time() - start_time
        logging.info(f"Total execution time: {elapsed:.2f} seconds")
        print(f"\nTotal execution time: {elapsed:.2f} seconds")