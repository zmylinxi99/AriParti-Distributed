import os
import re
import sys
import json
import time
import shlex
import string
import random
import logging
import subprocess
from datetime import datetime

def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_logic(file):
    with open(file, 'r') as f:
        content = f.read()
        m = re.search('set-logic ([A-Z_]+)', content) 
        if m: 
            return m[1]
    return None

def select_solver_for_logic(logic: str):
    mapping = {
        'QF_LRA': 'opensmt-2.5.2-bin',
        'QF_LIA': 'opensmt-2.5.2-bin',
        'QF_NRA': 'cvc5-1.0.8-bin',
        'QF_NIA': 'z3-4.12.1-bin'
    }
    if logic in mapping:
        return mapping[logic]
    else:
        raise ValueError(f'Unsupported logic: {logic}')

def check_get_model_flag(file):
    with open(file, 'r') as f:
        content = f.read()
        return int(content.find(r'(get-model)') != -1)

def init_logging(log_dir_path):
    os.makedirs(log_dir_path, exist_ok=True)
    logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
            filename=f'{log_dir_path}/launcher.log', level=logging.DEBUG)
    current_time = datetime.now()
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f'start-time {formatted_time}')

def prepare_rankfile(output_dir, worker_node_ips):
    os.makedirs(output_dir, exist_ok=True)
    rankfile_path = os.path.join(output_dir, 'rankfile')
    try:
        with open(rankfile_path, 'w') as rfile:
            node_number = len(worker_node_ips)
            for i in range(node_number):
                rfile.write(f'rank {i}={worker_node_ips[i]} slot=*\n')
            rfile.write(f'rank {node_number}={worker_node_ips[0]} slot=*\n')
            rfile.write(f'rank {node_number + 1}={worker_node_ips[0]} slot=*\n')
    except Exception as e:
        logging.error(f'Error writing rankfile: {e}')
        raise
    return rankfile_path

def prepare_temp_folder():
    temp_folder_name = generate_random_string(16)
    temp_folder_path = os.path.join('/tmp/ap-files', temp_folder_name)
    os.makedirs(temp_folder_path, exist_ok=True)
    logging.info(f'temp_folder_path: {temp_folder_path}')
    return temp_folder_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 AriParti_launcher.py <request_directory>')
    
    output_total_time = True
    if output_total_time:
        start_time = time.time()
    
    request_directory = sys.argv[1]
    
    # Initialize logging
    init_logging(f'{request_directory}/logs')
    
    # Load configuration
    try:
        with open(os.path.join(request_directory, 'input.json'), 'r') as file:
            config_data: dict = json.load(file)
    except Exception as e:
        logging.error(f'Failed to load config: {e}')
        sys.exit(f'Failed to load config: {e}')

    formula_file = config_data.get('formula_file')
    timeout_seconds = config_data.get('timeout_seconds')
    worker_node_ips = config_data.get('worker_node_ips')
    worker_node_cores = config_data.get('worker_node_cores')
    if not all([formula_file, timeout_seconds, worker_node_ips]):
        logging.error(f'Failed to load config: {e}')
        sys.exit('Missing required configuration parameters')
    
    logging.info(f'request_directory: {request_directory}')
    logging.info(f'formula_file: {formula_file}')
    logging.info(f'timeout_seconds: {timeout_seconds}')
    logging.info(f'worker_node_ips: {worker_node_ips}')
    logging.info(f'worker_node_cores: {worker_node_cores}')
    
    # fixed_parallel_cores = 8
    # assert(worker_node_cores[0] > fixed_parallel_cores)
    
    # formula_logic = get_logic(formula_file)
    # base_solver = select_solver_for_logic(formula_logic)
    # base_solver = 'z3pp-at-smt-comp-2023-bin'
    # base_solver = 'z3-4.12.1-bin'
    base_solver = 'cvc5-1.0.8-bin'
    logging.info(f'base_solver: {base_solver}')
    
    get_model_flag: int = check_get_model_flag(formula_file)
    
    output_dir = request_directory
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
            
    node_number = len(worker_node_ips)

    # Create temporary folder for files
    temp_folder_path = prepare_temp_folder()
    
    # solving_time_limit = timeout_seconds - 10
    solving_time_limit = timeout_seconds
    
    # Prepare rankfile
    rankfile_path = prepare_rankfile(output_dir, worker_node_ips)
    
    with open(f'{output_dir}/rankfile', 'w') as rfile:
        for i in range(node_number):
            node_ip = worker_node_ips[i]
            rfile.write(f'rank {i}={node_ip} slot=*\n')
            # ##//linxi-test
            # print(f'{node_ip} slots={slot}\n')
        rfile.write(f'rank {node_number}={worker_node_ips[0]} slot=*\n')
        rfile.write(f'rank {node_number + 1}={worker_node_ips[0]} slot=*\n')
    
    # Adjust worker_node_cores if provided
    worker_node_cores[0] -= 8
    worker_node_cores.append(7)
    
    cmd_paras = [
        'mpiexec',
        ### COMP-UPDATE ###
        # '--mca btl_tcp_if_include eth0',
        '--mca', 'btl_tcp_if_include', 'enp1s0f1',
        # '--mca btl_tcp_if_include ens6f0',
        '--allow-run-as-root',
        '--use-hwthread-cpus',
        '--bind-to', 'none',
        '--report-bindings',
        '--rankfile', f'{output_dir}/rankfile',
    ]
    
    dispatcher_path = os.path.join(script_dir, 'dispatcher.py')
    solver_path = os.path.join(script_dir, 'binary-files', base_solver)
    partitioner_path = os.path.join(script_dir, 'binary-files', 'partitioner-bin')
    
    cmd_paras.extend([
        'python3', f'{dispatcher_path}',
        # common parameters
        '--temp-dir', f'{temp_folder_path}',
        '--output-dir', f'{output_dir}',
        '--get-model-flag', f'{get_model_flag}',
        # leader parameters
        '--file', f'{formula_file}',
        '--time-limit', f'{solving_time_limit}',
        # coordinator parameters
        # f'--temp-dir {temp_folder_path}',
        '--solver', f'{solver_path}',
        '--available-cores-list', json.dumps(worker_node_cores),
        ##//linxi-test
        '--partitioner', f'{partitioner_path}',
        # f'--partitioner {script_dir}/partitioner/build/z3',
    ])
    
    # Use shlex.join for a safe command string construction
    cmd = shlex.join(cmd_paras)
    logging.info(f'command: {cmd}')
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # text=True,
        )
    except Exception as e:
        logging.error(f'Subprocess error: {e}')
        sys.exit(1)
    
    logging.info(f'stdout:')
    logging.info(result.stdout.decode('utf-8'))
    logging.info(f'stderr:')
    logging.info(result.stderr.decode('utf-8'))
    
    sys.stdout.write(result.stdout.decode('utf-8'))
    sys.stderr.write(result.stderr.decode('utf-8'))
    
    if output_total_time:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f'total cost time (start MPI and clean up):\n{execution_time}')
    