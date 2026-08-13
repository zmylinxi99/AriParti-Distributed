#!/usr/bin/python
import os
import time
import subprocess
import json
import shutil
import sys
# config_name = r'cvc5-partition'
# config_name = r'cvc5-partitioner'
config_name = r'smts'

if __name__ == '__main__':
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    request_directory = sys.argv[1]
    
    with open(f'{request_directory}/monitor.json') as file:
        config_data: dict = json.load(file)
    
    # for key, value in config_data.items():
    #     print(f'{key}: {value}')
    
    worker_node_ips = config_data['worker_node_ips']
    worker_node_core = config_data['worker_node_core']
    node_number = len(worker_node_ips)    
    hostfile_path = f'{request_directory}/monitor-hostfile'
    
    with open(hostfile_path, 'w') as hfile:
        for i in range(node_number):
            node_ip = worker_node_ips[i]
            hfile.write(f'{node_ip} slots=1\n')
    
    cmd_paras = [
        'mpiexec',
        '--mca btl_tcp_if_include ens6f0',
        '--bind-to none',
        f'--hostfile {hostfile_path}',
        f'python3 {script_dir}/monitor.py',
        f'{request_directory}',
    ]
    
    cmd = ' '.join(cmd_paras)
    
    # ##//linxi-test
    # print(f"command:\n{cmd}")
    
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=None,
        stderr=None
    )
    avg_cpu_usage_overall = 0.0
    for rank in range(node_number):
        overall_path = f'{request_directory}/rank-{rank}-overall.txt'
        with open(overall_path) as f:
            lines = f.read().strip('\n ').split('\n')
            avg_cpu_usage = float(lines[1])
            avg_cpu_usage_overall += avg_cpu_usage
    avg_cpu_usage_overall /= node_number
    with open(f'{request_directory}/overall.txt', 'w') as f:
        f.write(f'{avg_cpu_usage_overall}\n')
    print(avg_cpu_usage_overall)
