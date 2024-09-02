import os
import shutil
import time
import queue
import logging
import argparse
import subprocess
from datetime import datetime
from mpi4py import MPI
from partition_tree import DistributedNode
from partition_tree import DistributedTree
from partition_tree import DistributedNodeStatus
from partition_tree import DistributedNodeSolvedReason
from control_message import ControlMessage

class CoordinatorInfo:
    assign_to = None
    last_solving = 0.0
    last_split = 0.0
    solving_round = 0
    split_count = 0
    
    def __init__(self, rank):
        self.rank = rank
    
    def assign_node(self, node: DistributedNode, current_time):
        self.assign_to = node
        self.last_solving = current_time
        self.last_split = current_time
        self.solving_round += 1
        self.split_count = 0
        
    def split_node(self, current_time):
        self.last_split = current_time
        self.split_count += 1

class Leader:
    def __init__(self):
        self.solve_original_flag = True
        # self.solve_original_flag = False
        
        self.leader_rank = MPI.COMM_WORLD.Get_rank()
        self.num_nodes = self.leader_rank
        
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
        
        self.idle_coordinators = queue.Queue(range(self.num_nodes))
        self.coordinators = [CoordinatorInfo(i, self.start_time) for i in range(self.num_nodes)]
        self.split_candidate = queue.Queue()
        
        # self.split_target = [-1 for i in range(self.num_nodes)]
        self.split_stamp = 0.0
        
    
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
    
    def get_current_time(self):
        return time.time() - self.start_time
    
    # solver original task with base solver
    def solve_original_task(self):
        # run original task
        cmd =  [self.solver_path,
                self.input_file_path
            ]
        logging.info('exec-command {}'.format(' '.join(cmd)))
        # print(" ".join(cmd))
        self.original_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
    
    def is_done(self):
        return self.tree.is_done()
    
    def get_result(self):
        return self.tree.get_result()
    
    def update_assign_coordinator(self, parent: DistributedNode, idle_coord: int):
        current_time = self.get_current_time()
        child = self.tree.split_node_from(parent, idle_coord)
        self.coordinators[idle_coord].assign_node(child, current_time)
        self.split_candidate.put((idle_coord, current_time))
    
    def update_split_coordinator(self, split_coord: int):
        current_time = self.get_current_time()
        self.coordinators[split_coord].split_node(current_time)
        self.split_candidate.put((split_coord, current_time))
    
    def update_split_assign_info(self, split_coord: int, idle_coord: int):
        parent = self.coordinators[split_coord].assign_to
        assert(parent != None)
        self.update_assign_coordinator(parent, idle_coord)
        self.update_split_coordinator(split_coord)
    
    def check_coordinators(self):
        msg_status = MPI.Status()
        while MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=1, status=msg_status):
            src = msg_status.Get_source()
            msg_type = MPI.COMM_WORLD.recv(source=src, tag=1)
            assert(isinstance(msg_type, ControlMessage.C2L))
            if msg_type.is_split_succeed():
                target_rank = MPI.COMM_WORLD.recv(source=src, tag=2)
                self.send_assign_message(src, target_rank)
                # split node {path} to coordinator {target_rank}
                self.update_split_assign_info(src, target_rank)
            elif msg_type.is_split_failed():
                target_rank = MPI.COMM_WORLD.recv(source=src, tag=2)
                self.idle_coordinators.put(target_rank)
                self.split_candidate.put((src, self.get_current_time()))
            elif msg_type.is_notify_result():
                # coordinator {src} solved the assigned task
                result = MPI.COMM_WORLD.recv(source=src, tag=2)
                node = self.coordinators[src].assign_to
                self.tree.node_partial_solved(node, result)
                if self.is_done():
                    return
                self.idle_coordinators.put(src)
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

    def assign_root_node(self):
        os.makedirs(f'{self.temp_folder_path}/tasks/round-0', exist_ok=True)
        shutil.copyfile(self.input_file_path, 
                        f'{self.temp_folder_path}/tasks/round-0/task-root.smt2')
        MPI.COMM_WORLD.send(ControlMessage.L2C.assign_node, 
                            dest=0, tag=1)
        
        self.tree.split_node_from(None, 0)
        
        self.update_assign_coordinator(self.tree.root, )
    
    def get_next_idle_coordinator(self):
        # FIFO
        if self.idle_coordinators.empty():
            return None
        return self.idle_coordinators.get()
    
    def select_coordinator_to_split(self):
        # FIFO
        while not self.split_candidate.empty():
            coord_id, time_stamp = self.split_candidate.get()
            # assert(isinstance(self.coordinators[ret], CoordinatorInfo))
            split_coord: CoordinatorInfo = self.coordinators[coord_id]
            if time_stamp != split_coord.last_split:
                continue
            if split_coord.assign_to == None:
                continue
            return coord_id
        return None
    
    def send_split_message(self, split_coord, idle_coord):
        MPI.COMM_WORLD.send(ControlMessage.L2C.request_split,
                            dest=split_coord, tag=1)
        MPI.COMM_WORLD.send(idle_coord, 
                            dest=split_coord, tag=2)
        
    def send_assign_message(self, split_coord, idle_coord):
        MPI.COMM_WORLD.send(ControlMessage.L2C.assign_node,
                            dest=idle_coord, tag=1)
        MPI.COMM_WORLD.send(split_coord, 
                            dest=idle_coord, tag=2)
    
    def assign_node_to_idle_coordinator(self):
        idle_coord = self.get_next_idle_coordinator()
        if idle_coord == None:
            return
        split_coord = self.select_coordinator_to_split()
        if split_coord == None:
            return
        logging.info(f'assign node from coordinator-{split_coord} to coordinator-{idle_coord}')
        self.send_split_message(split_coord, idle_coord)
        # assert(self.split_target[split_coord] == -1)
        # self.split_target[split_coord] = idle_coord
    
    def solve(self):
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
            self.assign_node_to_idle_coordinator()
            if self.time_limit != 0 and self.get_current_time() >= self.time_limit:
                raise TimeoutError()
            if self.idle_coordinators.empty():
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
        
        if self.output_dir_path != None:
            with open(f'{self.output_dir_path}/result.txt', 'w') as f:
                f.write(f'{self.result}\n{execution_time}\n')
        
        self.terminate_coordinators()
        ### TBD: Terminate and clean up ###
        # MPI.COMM_WORLD.Abort()

if __name__ == '__main__':
    ap_leader = Leader()
    ap_leader()