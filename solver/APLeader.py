import os
import shutil
import time
import logging
import argparse
import subprocess
from datetime import datetime
from mpi4py import MPI
from APTask import Task
from APTask import TaskStatus
import partition_tree
from partition_tree import DistributedTree
from partition_tree import DistributedNodeStatus
from partition_tree import DistributedNodeSolvedReason

from control_message import ControlMessage

class Leader:
    def __init__(self):
        self.solve_original_flag = True
        # self.solve_original_flag = False
        
        self.num_nodes = MPI.COMM_WORLD.Get_rank()
        self.idle_coordinators = set(range(self.num_nodes))
        
        self.init_params()
        
        self.start_time = time.time()
        self.tree = DistributedTree(self.start_time)
        
        os.makedirs(f'{self.temp_folder_path}/tasks', exist_ok=True)
        
        # ##//linxi debug
        # print(self.temp_folder_path)
        # print(f'{self.output_dir_path}/log')
        
        if self.output_dir_path != None:
            os.makedirs(self.output_dir_path, exist_ok=True)
        
        self.init_logging()
        logging.info(f'temp_folder_path: {self.temp_folder_path}')

    def get_current_time(self):
        return time.time() - self.start_time
    
    def init_params(self):    
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--file', type=str, required=True,
                                help='input instance file path')
        arg_parser.add_argument('--solver', type=str, required=True,
                                help="solver path")
        arg_parser.add_argument('--temp-dir', type=str, required=True,
                                help='temp dir path')
        arg_parser.add_argument('--time-limit', type=int, default=0,
                                help='time limit, 0 means no limit')
        arg_parser.add_argument('--output-dir', type=str, default=None,
                                help='output dir path')
        cmd_args = arg_parser.parse_args()
        
        self.input_file_path: str = cmd_args.file
        self.solver_path: str = cmd_args.solver
        self.temp_folder_path: str = cmd_args.temp_dir
        self.time_limit: int = cmd_args.time_limit
        self.output_dir_path: str = cmd_args.output_dir
        
        if not os.path.exists(self.input_file_path):
            print('file-not-found')
            assert(False)
        
        self.instance_name: str = self.input_file_path[ \
            self.input_file_path.rfind('/') + 1: self.input_file_path.find('.smt2')]
    
    def init_logging(self):
        if self.output_dir_path != None:
            logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
                    filename=f'{self.output_dir_path}/log', level=logging.INFO)
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f'start-time {formatted_time} ({self.start_time})')
    
    # solver original task with base solver
    def solve_original_task(self):
        # run original task
        instance_path = f'{self.temp_folder_path}/tasks/original.smt2'
        cmd =  [self.solver_path,
                instance_path
            ]
        logging.info('exec-command {}'.format(' '.join(cmd)))
        # print(" ".join(cmd))
        self.original_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
    
    def init_original_task(self):
        shutil.copyfile(self.input_file_path, 
                        f'{self.temp_folder_path}/tasks/original.smt2')
    
    def is_done(self):
        return self.tree.is_done()
    
    def get_result(self):
        return self.tree.get_result()
    
    def split_node(self, coordinator_rank, path):
        ### TBD ###
        pass
    
    
    def check_coordinators(self):
        msg_status = MPI.Status()
        while MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=1, status=msg_status):
            src = msg_status.Get_source()
            msg_type = MPI.COMM_WORLD.recv(source=src, tag=1)
            assert(isinstance(msg_type, ControlMessage.C2L))
            if msg_type.is_send_path():
                # split node {path}
                path: list = MPI.COMM_WORLD.recv(source=src, tag=2)
                ### TBD ###
                pass
            elif msg_type.is_notify_result():
                # coordinator {src} solved the assigned task
                result = MPI.COMM_WORLD.recv(source=src, tag=2)
                self.idle_coordinators.add(src)
                self.tree.node_id_solved(src, result)
                if self.is_done():
                    return
            # elif msg_type.is_XXX:
            #     # coordinator {src} report current solving info
            #     ### TBD ###
            #     # data = MPI.COMM_WORLD.recv(source=src, tag=2)
            #     pass
            else:
                assert(False)
    
    def check_original_task(self):
        p = self.original_process
        rc = p.poll()
        if rc == None:
            return
        assert(rc == 0)
        out_data, err_data = p.communicate()
        sta : str = out_data.strip('\n').strip(' ')
        if sta == 'sat':
            result = DistributedNodeStatus.sat
        elif sta == 'unsat':
            result = DistributedNodeStatus.unsat
        else:
            assert(False)
        self.tree.update_node_status(self.tree.root, result, 
                                     DistributedNodeSolvedReason.original)
        logging.info(f'solved-by-original {sta}')

    # def assign_node_to(self, node_id, coordinator_rank):
    #     # coordinator_rank = self.idle_coordinators.pop()
    #     logging.info(f'assign node-{node_id} to coordinator-{coordinator_rank}')
    #     ### TBD ###
    #     MPI.COMM_WORLD.send(node_id, dest=coordinator_rank, tag=1)

    def assign_root_node(self):
        os.makedirs(f'{self.temp_folder_path}/tasks/round-0', exist_ok=True)
        shutil.copyfile(f'{self.temp_folder_path}/tasks/original.smt2', 
                        f'{self.temp_folder_path}/tasks/round-0/task-root.smt2')
        MPI.COMM_WORLD.send(ControlMessage.L2C.assign_node, 
                            dest=0, tag=1)
    
    def solve(self):
        self.init_original_task()
        if self.solve_original_flag:
            self.solve_original_task()
        
        self.assign_root_node()
        # communicate with coordinators
        while True:
            if self.solve_original_flag:
                self.check_original_task()
                if self.is_done():
                    return
            
            self.check_coordinators()
            if self.is_done():
                return
            if self.time_limit != 0 and self.get_current_time() >= self.time_limit:
                raise TimeoutError()
            time.sleep(0.1)
    
    def terminate_coordinators(self):
        for i in range(self.num_nodes):
            MPI.COMM_WORLD.send(ControlMessage.L2C.terminate_coordinator,
                                dest=i, tag=1)
        
    def __call__(self):
        try:
            self.solve()
        except TimeoutError:
            self.result = 'timeout'
            logging.info('timeout')
        # except AssertionError as ae:
        #     self.result = 'AssertionError'
        #     # print(f'AssertionError: {ae}')
        #     # logging.info(f'AssertionError: {ae}')
        # except Exception as e:
        #     self.result = 'Exception'
        #     # print(f'Exception: {e}')
        #     # logging.info(f'Exception: {e}')
        
        end_time = time.time()
        execution_time = end_time - self.start_time
        print(self.result)
        print(execution_time)
        
        self.terminate_coordinators()
        
        if self.output_dir_path != None:
            with open(f'{self.output_dir_path}/result.txt', 'w') as f:
                f.write(f'{self.result}\n{execution_time}\n')
        ### TBD: Terminate and clean up ###
        # MPI.COMM_WORLD.Abort()

if __name__ == '__main__':
    
    # print(f'cmd_args.temp_dir: {cmd_args.temp_dir}')
    ap_leader = Leader()
    ap_leader()