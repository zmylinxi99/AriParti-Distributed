import os
import sys
import psutil
import json
import signal
import time
from mpi4py import MPI

def get_current_time(start_time):
    return time.time() - start_time

# def handle_termination():
#     with open(overall_path, 'w') as f:
#         f.write(f'{get_current_time()}\n')
#         f.write(f'{avg_cpu_usage_overall}\n')
#     sys.exit(0)

if __name__ == "__main__":
    check_interval = 0.02
    cycle_interval = 0.1
    
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)


    avg_cpu_usage_overall = 0.0
    # rank = 1
    rank = MPI.COMM_WORLD.Get_rank()
    start_time = time.time()

    
    sleep_interval = cycle_interval - check_interval
    
    total_core = 512
    request_directory = sys.argv[1]
    
    overall_path = f'{request_directory}/rank-{rank}-overall.txt'
    log_path = f'{request_directory}/rank-{rank}-log.txt'
    config_path = f'{request_directory}/monitor.json'
    
    with open(config_path) as file:
        config_data: dict = json.load(file)
    worker_node_core: int = config_data.get('worker_node_core')
    time_limit: float = config_data.get('timeout_seconds')
    usage_multiple = total_core / worker_node_core
    
    # signal.signal(signal.SIGTERM, handle_termination)
    # signal.signal(signal.SIGINT, handle_termination)
    
    avg_cpu_usage_sum = 0.0
    check_cnt = 0
    
    log_interval = 1.0
    next_log_time = 0.0
    last_log_cnt = 0
    last_avg_cpu_usage_sum = 0.0
    
    if os.path.exists(log_path):
        os.remove(log_path)
    
    while True:
        cpu_percent_per_core = psutil.cpu_percent(interval=check_interval, percpu=True)
        avg_cpu_usage = sum(cpu_percent_per_core) / len(cpu_percent_per_core) if cpu_percent_per_core else 0.0
        avg_cpu_usage *= usage_multiple
        if avg_cpu_usage > 100.0:
            avg_cpu_usage = 100.0
        avg_cpu_usage_sum += avg_cpu_usage
        check_cnt += 1
        
        last_avg_cpu_usage_sum += avg_cpu_usage
        last_log_cnt += 1
        current_time = get_current_time(start_time)
        if next_log_time <= current_time:
            avg_cpu_usage_overall = avg_cpu_usage_sum / check_cnt
            last_avg_cpu_usage_sum /= last_log_cnt
            # print(f'current_time: {current_time}')
            # print(f'last_avg_cpu_usage_sum: {last_avg_cpu_usage_sum}')
            # print(f'avg_cpu_usage_overall: {avg_cpu_usage_overall}')
            with open(log_path, 'a') as f:
                f.write(f'{current_time :.2f} {last_avg_cpu_usage_sum :.2f} {avg_cpu_usage_overall :.2f}\n')
            last_avg_cpu_usage_sum = 0.0
            last_log_cnt = 0
            next_log_time = current_time + log_interval
            if os.path.exists(f'{request_directory}/terminate'):
                avg_cpu_usage_overall = avg_cpu_usage_sum / check_cnt
                with open(overall_path, 'w') as f:
                    f.write(f'{current_time :.2f}\n')
                    f.write(f'{avg_cpu_usage_overall :.2f}\n')
                break
        # if current_time >= time_limit:
        #     avg_cpu_usage_overall = avg_cpu_usage_sum / check_cnt
        #     with open(overall_path, 'w') as f:
        #         f.write(f'{current_time :.2f}\n')
        #         f.write(f'{avg_cpu_usage_overall :.2f}\n')
        #     break
        time.sleep(sleep_interval)
        
        
