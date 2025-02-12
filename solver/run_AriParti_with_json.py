import os
import re
import sys
import json
import time
import string
import random
import subprocess

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
    # return 'z3pp-at-smt-comp-2023-bin'
    if logic == 'QF_LRA':
        return 'opensmt-2.5.2-bin'
    elif logic == 'QF_LIA':
        return 'opensmt-2.5.2-bin'
    elif logic == 'QF_NRA':
        return 'cvc5-1.0.8-bin'
    elif logic == 'QF_NIA':
        return 'z3-4.12.1-bin'
    else:
        assert(False)

def check_get_model_flag(file):
    with open(file, 'r') as f:
        content = f.read()
        return int(content.find(r'(get-model)') != -1)

if __name__ == '__main__':
    output_total_time = True
    
    if output_total_time:
        start_time = time.time()

    request_directory = sys.argv[1]
    with open(f'{request_directory}/input.json', 'r') as file:
        config_data: dict = json.load(file)

    formula_file = config_data['formula_file']
    timeout_seconds: int = config_data['timeout_seconds']
    worker_node_ips = config_data['worker_node_ips']
    worker_node_cores: list = config_data.get('worker_node_cores')
    
    # fixed_parallel_cores = 8
    # assert(worker_node_cores[0] > fixed_parallel_cores)
    
    # formula_logic = get_logic(formula_file)
    # base_solver = select_solver_for_logic(formula_logic)
    # base_solver = 'z3pp-at-smt-comp-2023-bin'
    # base_solver = 'z3-4.12.1-bin'
    base_solver = 'cvc5-1.0.8-bin'
    
    get_model_flag: int = check_get_model_flag(formula_file)
    
    output_dir = request_directory
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
            
    node_number = len(worker_node_ips)

    os.makedirs(output_dir, exist_ok=True)
    temp_folder_name = generate_random_string(16)
    temp_folder_path = f'/tmp/ap-files/{temp_folder_name}'
    os.makedirs(temp_folder_path, exist_ok=True)
    
    # solving_time_limit = timeout_seconds - 10
    solving_time_limit = timeout_seconds
    
    with open(f'{output_dir}/rankfile', 'w') as rfile:
        for i in range(node_number):
            node_ip = worker_node_ips[i]
            rfile.write(f'rank {i}={node_ip} slot=*\n')
            # ##//linxi-test
            # print(f'{node_ip} slots={slot}\n')
        rfile.write(f'rank {node_number}={worker_node_ips[0]} slot=*\n')
        rfile.write(f'rank {node_number + 1}={worker_node_ips[0]} slot=*\n')
    
    worker_node_cores[0] -= 8
    worker_node_cores.append(7)
    
    cmd_paras = [
        'mpiexec',
        ### COMP-UPDATE ###
        # '--mca btl_tcp_if_include eth0',
        # '--mca btl_tcp_if_include enp1s0f1',
        '--mca btl_tcp_if_include ens6f0',
        '--allow-run-as-root',
        '--use-hwthread-cpus',
        '--bind-to none', '--report-bindings',
        f'--rankfile {output_dir}/rankfile',
    ]
    
    cmd_paras.extend([
        f'python3 {script_dir}/AriParti.py',
        # common parameters
        f'--temp-dir {temp_folder_path}',
        f'--output-dir {output_dir}',
        f'--get-model-flag {get_model_flag}',
        # leader parameters
        f'--file {formula_file}',
        f'--time-limit {solving_time_limit}',
        # coordinator parameters
        # f'--temp-dir {temp_folder_path}',
        f'--solver {script_dir}/binary-files/{base_solver}',
        f'--available-cores-list "{json.dumps(worker_node_cores)}"',
        ##//linxi-test
        f'--partitioner {script_dir}/binary-files/partitioner-bin',
        # f'--partitioner {script_dir}/partitioner/build/z3',
    ])
    
    cmd = ' '.join(cmd_paras)
    # ##//linxi-test
    # print(f'command:\n{cmd}')
    
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # ##//linxi-test
    # print(f'stdout:')
    # print(result.stdout.decode('utf-8'))
    # print(f'stderr:')
    # print(result.stderr.decode('utf-8'))
    
    sys.stdout.write(result.stdout.decode('utf-8'))
    sys.stderr.write(result.stderr.decode('utf-8'))
    
    if output_total_time:
        end_time = time.time()
        execution_time = end_time - start_time
        print(f'total cost time (start MPI and clean up):\n{execution_time}')
    