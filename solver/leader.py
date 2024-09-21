import os
import shutil
import time
import logging
import argparse
import subprocess
from mpi4py import MPI
from datetime import datetime
import heapq
import traceback
from collections import deque
from partition_tree import DistributedNode
from partition_tree import DistributedTree
from partition_tree import NodeStatus
from partition_tree import NodeSolvedReason
from control_message import ControlMessage
from coordinator import CoordinatorStatus

class CoordinatorInfo:
    def __init__(self, rank, start_time):
        self.status = CoordinatorStatus.idle
        self.assigned = None
        self.solving_round = 0
        self.split_count = 0
        self.last_split = 0.0
        self.last_assign = 0.0
        
        self.rank = rank
        self.start_time = start_time
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def assign_node(self, node: DistributedNode):
        assert(self.status.is_idle())
        self.status = CoordinatorStatus.solving
        self.assigned = node
        self.solving_round += 1
        self.split_count = 0
        self.last_assign = self.get_current_time()
        self.last_split = self.get_current_time()
        
    def split_node(self):
        assert(self.status.is_splitting())
        self.status = CoordinatorStatus.solving
        self.split_count += 1
        self.last_split = self.get_current_time()
        
    def node_solved(self):
        self.status = CoordinatorStatus.idle
        self.assigned = None

class Leader:
    def __init__(self):
        self.solve_original_flag = False
        # self.solve_original_flag = False
        self.split_tabu = 5.0
        # self.split_tabu_rate = 1.5
        
        self.leader_rank = MPI.COMM_WORLD.Get_rank()
        self.num_nodes = self.leader_rank
        
        self.init_params()
        
        self.start_time = time.time()
        self.tree = DistributedTree(self.start_time)
        
        os.makedirs(self.temp_folder_path, exist_ok=True)
        
        # ##//linxi debug
        # print(self.temp_folder_path)
        # print(f'{self.output_folder_path}/log')
        
        os.makedirs(self.output_folder_path, exist_ok=True)
        
        self.init_logging()
        
        logging.debug(f'num_nodes: {self.num_nodes}')
        logging.debug(f'leader_rank: {self.leader_rank}')
        logging.debug(f'temp_folder_path: {self.temp_folder_path}')
        
        self.idle_coordinators = deque([i for i in range(1, self.num_nodes)])
        self.coordinators = [CoordinatorInfo(i, self.start_time) for i in range(self.num_nodes)]
        self.next_split_rank = 0
        logging.debug(f'init done!')
    
    def init_params(self):    
        arg_parser = argparse.ArgumentParser()
        common_args = arg_parser.add_argument_group('Common Arguments')
        common_args.add_argument('--temp-dir', type=str, required=True,
                                help='temp dir path')
        common_args.add_argument('--solver', type=str, required=True,
                                help="solver path")
        common_args.add_argument('--output-dir', type=str, required=True,
                                help='output dir path')
        
        leader_args = arg_parser.add_argument_group('Leader Arguments')
        leader_args.add_argument('--file', type=str, required=True,
                        help='input instance file path')
        leader_args.add_argument('--time-limit', type=int, default=0,
                                help='time limit, 0 means no limit')
        
        coordinator_args = arg_parser.add_argument_group('Coordinator Arguments')
        coordinator_args.add_argument('--partitioner', type=str, required=True,
                                help='partitioner path')
        coordinator_args.add_argument('--available-cores-list', type=str, required=True, 
                                help='available cores list')
        
        cmd_args = arg_parser.parse_args()
        self.input_file_path: str = cmd_args.file
        self.solver_path: str = cmd_args.solver
        self.temp_folder_path: str = cmd_args.temp_dir
        self.time_limit: int = cmd_args.time_limit
        self.output_folder_path: str = cmd_args.output_dir
        
        if not os.path.exists(self.input_file_path):
            print('file-not-found')
            assert(False)
        
        self.instance_name: str = self.input_file_path[ \
            self.input_file_path.rfind('/') + 1: self.input_file_path.find('.smt2')]
    
    def init_logging(self):
        log_dir_path = f'{self.output_folder_path}/logs'
        os.makedirs(log_dir_path, exist_ok=True)
        logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
                filename=f'{log_dir_path}/leader.log', level=logging.DEBUG)
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f'start-time {formatted_time} ({self.start_time})')
    
    def get_current_time(self):
        return time.time() - self.start_time
    
    # solver original task with base solver
    def solve_original_task(self):
        logging.debug('solve_original_task()')
        # run original task
        cmd =  [self.solver_path,
                self.input_file_path
            ]
        logging.debug('exec-command {}'.format(' '.join(cmd)))
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
        child = self.tree.split_node_from(parent, idle_coord)
        self.coordinators[idle_coord].assign_node(child)
    
    def update_split_coordinator(self, split_coord: int):
        self.coordinators[split_coord].split_node()
    
    # def update_split_tabu(self):
    #     logging.debug(f'update split tabu: {self.split_tabu}s')
    #     self.split_tabu *= self.split_tabu_rate
    
    def update_split_assign_info(self, split_coord: int, idle_coord: int):
        parent = self.coordinators[split_coord].assigned
        assert(parent != None)
        self.update_assign_coordinator(parent, idle_coord)
        self.update_split_coordinator(split_coord)
        logging.info(f'split: (node-{self.coordinators[idle_coord].assigned.id} coordinator-{idle_coord}) '
                     f'from (node-{self.coordinators[split_coord].assigned.id} coordinator-{split_coord})')
        # self.update_split_tabu()
    
    def set_coordinator_idle(self, coord_rank):
        self.coordinators[coord_rank].node_solved()
        self.idle_coordinators.append(coord_rank)
    
    def check_coordinators(self):
        msg_status = MPI.Status()
        while MPI.COMM_WORLD.Iprobe(source=MPI.ANY_SOURCE, tag=1, status=msg_status):
            src = msg_status.Get_source()
            msg_type = MPI.COMM_WORLD.recv(source=src, tag=1)
            assert(isinstance(msg_type, ControlMessage.C2L))
            logging.debug(f'receive {msg_type} message from coordinator-{src}')
            if msg_type.is_split_succeed():
                target_rank = MPI.COMM_WORLD.recv(source=src, tag=2)
                self.send_assign_message(src, target_rank)
                self.send_transfer_message(src, target_rank)
                # split node {path} to coordinator {target_rank}
                self.update_split_assign_info(src, target_rank)
            elif msg_type.is_split_failed():
                target_rank = MPI.COMM_WORLD.recv(source=src, tag=2)
                self.idle_coordinators.append(target_rank)
                coord: CoordinatorInfo = self.coordinators[src]
                if coord.status.is_splitting():
                    coord.status = CoordinatorStatus.solving
            elif msg_type.is_notify_result():
                # coordinator {src} solved the assigned task
                result = MPI.COMM_WORLD.recv(source=src, tag=2)
                node = self.coordinators[src].assigned
                logging.info(f'solved: node-{node.id} is {result}')
                self.tree.node_partial_solved(node, result)
                self.tree.log_display()
                if self.is_done():
                    return
                self.set_coordinator_idle(src)
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
            result = NodeStatus.sat
        elif sta == 'unsat':
            result = NodeStatus.unsat
        else:
            assert(False)
        
        self.tree.original_solved(result)
        logging.info(f'solved-by-original {sta}')

    def assign_root_node(self):
        logging.debug(f'assign_root_node()')
        target_path = f'{self.temp_folder_path}/Coordinator-0/tasks/round-0'
        os.makedirs(target_path, exist_ok=True)
        shutil.copyfile(self.input_file_path, 
                        f'{target_path}/task-root.smt2')
        MPI.COMM_WORLD.send(ControlMessage.L2C.assign_node, 
                            dest=0, tag=1)
        self.tree.assign_root_node()
        
        self.coordinators[0].assign_node(self.tree.root)
    
    def get_next_idle_coordinator(self):
        # FIFO
        if len(self.idle_coordinators) == 0:
            return None
        return self.idle_coordinators.popleft()
    
    def select_coordinator_to_split(self, skip_tabu: bool):
        # FIFO
        rank = self.next_split_rank
        self.next_split_rank = (rank + 1) % self.num_nodes
        split_coord: CoordinatorInfo = self.coordinators[rank]

        if split_coord.status.is_solving() and \
           (skip_tabu or self.get_current_time() >= split_coord.last_split + self.split_tabu):
            return rank
        else:
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
    
    def send_transfer_message(self, split_coord, idle_coord):
        MPI.COMM_WORLD.send(ControlMessage.L2C.transfer_node,
                            dest=split_coord, tag=1)
        MPI.COMM_WORLD.send(idle_coord, 
                            dest=split_coord, tag=2)
    
    def assign_node_to_idle_coordinator(self):
        # logging.debug('assign_node_to_idle_coordinator()')
        idle_coord = self.get_next_idle_coordinator()
        if idle_coord == None:
            return
        if self.coordinators[idle_coord].solving_round == 0:
            skip_tabu = True
        else:
            skip_tabu = False
        split_coord = self.select_coordinator_to_split(skip_tabu)
        if split_coord == None:
            self.idle_coordinators.append(idle_coord)
            return
        # logging.info(f'idle_coord: {idle_coord}')
        # logging.info(f'split_coord: {split_coord}')
        logging.info(f'assign node from coordinator-{split_coord} to coordinator-{idle_coord}')
        self.coordinators[split_coord].status = CoordinatorStatus.splitting
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
            if len(self.idle_coordinators) > 0:
                self.assign_node_to_idle_coordinator()
            time.sleep(0.1)
            if self.time_limit != 0 and self.get_current_time() >= self.time_limit:
                raise TimeoutError()

    def terminate_coordinators(self):
        for i in range(self.num_nodes):
            MPI.COMM_WORLD.send(ControlMessage.L2C.terminate_coordinator,
                                dest=i, tag=1)
        
    def __call__(self):
        try:
            self.solve()
        except TimeoutError:
            result = 'timeout'
        # except AssertionError as ae:
        #     result = 'AssertionError'
        #     # print(f'AssertionError: {ae}')
        #     # logging.info(f'AssertionError: {ae}')
        except Exception as e:
            result = 'Exception'
            # print(f'Leader Exception: {e}')
            logging.info(f'Leader Exception: {e}')
            logging.info(f'Traceback: {traceback.format_exc()}')
        else:
            status: NodeStatus = self.get_result()
            if status.is_sat():
                result = 'sat'
            elif status.is_unsat():
                result = 'unsat'
            else:
                assert(False)
        
        end_time = time.time()
        execution_time = end_time - self.start_time
        
        print(result)
        print(execution_time)
        logging.info(f'result: {result}, time: {execution_time}')
        
        if self.output_folder_path != None:
            with open(f'{self.output_folder_path}/result.txt', 'w') as f:
                f.write(f'{result}\n{execution_time}\n')
        
        self.terminate_coordinators()
        ### TBD: Terminate and clean up ###
        # MPI.COMM_WORLD.Abort()