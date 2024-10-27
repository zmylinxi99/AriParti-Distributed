import os
import time
import logging
import argparse
import subprocess
import shutil
import json
import traceback
from collections import deque
from datetime import datetime
from mpi4py import MPI
from enum import Enum, auto

from partition_tree import ParallelNode, ParallelTree
from partition_tree import NodeStatus, NodeReason
from control_message import TerminateMessage, ControlMessage
from partitioner import Partitioner

class CoordinatorStatus(Enum):
    idle = auto()
    waiting = auto()
    solving = auto()
    splitting = auto()
    
    def is_idle(self):
        return self == CoordinatorStatus.idle

    def is_waiting(self):
        return self == CoordinatorStatus.waiting
    
    def is_solving(self):
        return self == CoordinatorStatus.solving
    
    def is_splitting(self):
        return self == CoordinatorStatus.splitting

class Coordinator:
    def __init__(self):
        self.partitioner = None
        self.solving_round = 0
        
        self.coordinator_start_time = time.time()
        self.rank = MPI.COMM_WORLD.Get_rank()
        self.leader_rank = MPI.COMM_WORLD.Get_size() - 1
        self.num_coords = self.leader_rank
        self.init_params()
        
        self.temp_folder_path = f'{self.temp_folder_path}/Coordinator-{self.rank}'
        # assign a core to coordinator and partitioner
        self.available_cores -= 1
        self.max_unsolved_tasks = self.available_cores + self.available_cores // 3 + 1
        
        self.init_logging()
        os.makedirs(self.temp_folder_path, exist_ok=True)
        
        self.status: CoordinatorStatus = CoordinatorStatus.idle
        self.result = NodeStatus.unsolved
        self.partitioner = None
        self.tree = None
        
        logging.debug(f'rank: {self.rank}, leader_rank: {self.leader_rank}')
        logging.debug(f'temp_folder_path: {self.temp_folder_path}')
        logging.debug(f'coordinator-{self.rank} init done!')
    
    def init_logging(self):
        log_dir_path = f'{self.output_folder_path}/logs'
        os.makedirs(log_dir_path, exist_ok=True)
        logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
                filename=f'{log_dir_path}/coordinator-{self.rank}.log', level=logging.DEBUG)
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f'start-time {formatted_time} ({self.coordinator_start_time})')
    
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
        self.partitioner_path: str = cmd_args.partitioner
        self.solver_path: str = cmd_args.solver
        self.temp_folder_path: str = cmd_args.temp_dir
        self.output_folder_path: str = cmd_args.output_dir
        
        available_cores_list: list = json.loads(cmd_args.available_cores_list)
        
        self.available_cores: int = available_cores_list[self.rank]
        if self.rank == 0:
            self.available_cores -= 3
    
    def is_done(self):
        if self.result.is_solved():
            return True
        if self.tree.is_done():
            self.result = self.tree.get_result()
            return True
        return False
    
    def get_result(self):
        return self.result
    
    def get_coordinator_time(self):
        return time.time() - self.coordinator_start_time
    
    def get_solving_time(self):
        return time.time() - self.solving_start_time
    
    def write_line_to_log(self, data: str):
        logging.info(data)
    
    def process_partitioner_msg(self, msg: str):
        words = msg.split(' ')
        if words[0] in ['sat', 'unsat', 'unknown']:
            result = words[0]
            self.partitioner.set_status(result)
            if result == 'sat':
                self.result = NodeStatus.sat
            elif result == 'unsat':
                self.result = NodeStatus.unsat
            elif result == 'unknown':
                if self.tree.get_node_number() == 0:
                    logging.error('Partitioner error')
                    assert(False)
                    # MPI.COMM_WORLD.Abort()
            else:
                assert(False)
        else:
            op = ControlMessage.P2C(int(words[0]))
            if op.is_debug_info():
                # remains = ' '.join(words[1: ])
                # logging.debug(f'partitioner-debug-info {remains}')
                pass
            elif op.is_new_node():
                pid = int(words[1])
                ppid = int(words[2])
                node = self.tree.make_node(pid, ppid)
                if op.is_new_unsat_node():
                    self.tree.node_solved_unsat(node,
                            NodeReason.partitioner)
                    if self.is_done():
                        return
                elif node.parent != None and node.parent.status.is_unsat():
                    self.tree.node_solved_unsat(node,
                            NodeReason.ancester)
                else:
                    self.tree.waitings.append(node)
                    if node.id == 0:
                        root_init_file = f'{self.solving_folder_path}/task-0.done'
                        with open(root_init_file, 'w') as file:
                            file.write('done')
                self.log_tree_infos()
                ### TBD ###
            else:
                assert(False)
        
    def receive_message_from_partitioner(self):
        is_done = self.partitioner.check_p_status()
        if not is_done:
            cnt = 0
        while True:
            if not is_done:
                if cnt >= 16:
                    break
                cnt += 1
            msg = self.partitioner.receive_message()
            if msg == None:
                break
            msg = msg.strip(' \n')
            if msg == '':
                break
            logging.debug(f'partitioner-message {msg}')
            self.process_partitioner_msg(msg)
            if self.partitioner.is_done():
                break
            # if self.is_done():
            #     break
        if is_done:
            assert(self.partitioner.is_done())
    
    ### TBD ###
    # def need_terminate(self, t: Task):
    #     if t.id <= 0:
    #         return False
    #     num_st = len(t.subtasks)
    #     st_end = 0
    #     if num_st > 0 and t.subtasks[0].status in ['solving', 'unsat', 'terminated']:
    #         st_end += 1
    #     if num_st > 1 and t.subtasks[1].status in ['solving', 'unsat', 'terminated']:
    #         st_end += 1
        
    #     if st_end == 0:
    #         return False
    #     if st_end == 1 and self.get_current_time() - t.time_infos['solving'] < 200.0:
    #         return False
    #     if st_end == 2 and self.get_current_time() - t.time_infos['solving'] < 100.0:
    #         return False
    #     return True

    def check_subprocess_status(self, p: subprocess.Popen):
        rc = p.poll()
        if rc == None:
            return NodeStatus.solving
        
        # if rc != 0:
        #     return NodeStatus.error
        out_data, err_data = p.communicate()
        if rc != 0:
            logging.error('return code != 0')
            logging.error(f'stdout: {out_data}')
            logging.error(f'stderr: {err_data}')
            MPI.COMM_WORLD.Abort(rc)

        sta: str = out_data.strip('\n').strip(' ')
        assert(rc == 0)
        if sta == 'sat':
            return NodeStatus.sat
        elif sta == 'unsat':
            return NodeStatus.unsat
        else:
            assert(False)
    
    def send_partitioner_message(self, msg: str):
        logging.debug(f'send_partitioner_message: {msg}')
        self.partitioner.send_message(msg)
    
    def sync_ended_to_partitioner(self):
        if self.partitioner.check_p_status():
            return
        for unsync in self.tree.unsyncs:
            unsync: ParallelNode
            if unsync.status.is_unsat():
                msg = f'{ControlMessage.C2P.unsat_node.value} {unsync.pid}'
            else:
                msg = f'{ControlMessage.C2P.terminate_node.value} {unsync.pid}'
            self.send_partitioner_message(msg)
        self.tree.unsyncs = []
    
    # True for still running
    def check_solving_status(self, node: ParallelNode):
        if not node.status.is_solving():
            return False
        sta: NodeStatus = self.check_subprocess_status(node.assign_to)
        if sta.is_solving():
            return True
            ### TBD ###
            # if self.need_terminate(t):
            #     self.update_task_status(t, 'terminated')
            #     self.terminate_task(t)
            #     self.sync_ended_to_partitioner()
            #     return False
            # else:
            #     return True
        node.assign_to = None
        logging.info(f'solved: node-{node.id} is {sta}')
        self.tree.node_solved(node, sta)
        self.log_tree_infos()
        if self.is_done():
            return False
        self.sync_ended_to_partitioner()
        return False
    
    def solve_node(self, node: ParallelNode):
        instance_path = f'{self.solving_folder_path}/task-{node.pid}.smt2'
        cmd =  [self.solver_path,
                instance_path,
            ]
        logging.debug('exec-command {}'.format(' '.join(cmd)))
        p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        self.tree.assign_node(node, p)
        logging.debug(f'solve-node {node.id} with pid {node.pid}')
    
    def check_solvings_status(self):
        still_solvings = [] 
        for node in self.tree.solvings:
            node: ParallelNode
            if not node.status.is_solving():
                continue
            if self.check_solving_status(node):
                still_solvings.append(node)
            else:
                if self.is_done():
                    return True
        self.tree.solvings = still_solvings
        return False
    
    def log_tree_infos(self):
        logging.debug(f'nodes: {self.tree.get_node_number()}, '
                      f'solvings: {self.tree.get_solving_number()}({self.available_cores}), '
                      f'solved: {self.tree.update_dict.get((NodeStatus.unsat, NodeReason.itself), 0)}(itself), '
                      f'{self.tree.update_dict.get((NodeStatus.unsat, NodeReason.children), 0)}(children), '
                      f'{self.tree.update_dict.get((NodeStatus.unsat, NodeReason.ancester), 0)}(ancester), '
                      f'{self.tree.update_dict.get((NodeStatus.unsat, NodeReason.partitioner), 0)}(partitioner), '
                      f'progress: {self.tree.root.unsat_percent * 100.0:.2f}%'
                    #   f'endeds: {self.tree.get_ended_number()}, '
                    #   f'unendeds: {self.tree.get_unended_number()}'
                )
    
    # run waitings by:
    # currently: generation order
    # can be easily change to: priority select
    def run_waiting_tasks(self):
        ### TBD ###
        while len(self.tree.solvings) < self.available_cores:
            node = self.tree.get_next_waiting_node()
            if node == None:
                break
            self.solve_node(node)
    
    # run the partitioner
    def run_partitioner(self):
        cmd =  [self.partitioner_path,
                f'{self.solving_folder_path}/task-root.smt2',
                f'-outputdir:{self.solving_folder_path}',
                f'-partmrt:{max(self.available_cores, self.num_coords)}'
            ]
        logging.debug(f'exec-command {" ".join(cmd)}')
        p = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        self.partitioner = Partitioner(p)
    
    def terminate_partitioner(self):
        if self.partitioner.is_running():
            self.partitioner.p.terminate()
    
    def start_solving(self):
        self.solving_folder_path = f'{self.temp_folder_path}/tasks/round-{self.solving_round}'
        
        self.status = CoordinatorStatus.solving
        self.result = NodeStatus.unsolved
        self.solving_start_time = time.time()
        self.tree = ParallelTree(self.solving_start_time)
        self.split_node = None
        # ##//linxi debug
        # print(self.temp_folder_path)
        # print(f'{self.output_dir_path}/log')
        
        ### TBD ###
        # self.init_logging()
        # logging.info(f'temp_folder_path: {self.temp_folder_path}')
        self.run_partitioner()

    # coordinator [rank] solved the assigned node
    def send_result_to_leader(self):
        result: NodeStatus = self.get_result()
        assert(result.is_solved())
        
        MPI.COMM_WORLD.send(ControlMessage.C2L.notify_result,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(result, dest=self.leader_rank, tag=2)
    
    # True -> solved
    def parallel_solving(self):
        if self.partitioner.is_running():
            self.receive_message_from_partitioner()
            if self.is_done():
                return True
        if self.check_solvings_status():
            # self.tree.log_display()
            return True
        self.run_waiting_tasks()
        return False
    
    def select_split_node(self):
        return self.tree.select_split_node()

    def set_node_split(self, node: ParallelNode, assigned_coord: int):
        ### TBD ###
        self.tree.set_node_split(node, assigned_coord)
        self.sync_ended_to_partitioner()
    
    def solve_leader_root(self):
        # while not MPI.COMM_WORLD.Iprobe(source=self.leader_rank, tag=1):
        #     time.sleep(0.01)
        msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
        assert(isinstance(msg_type, ControlMessage.L2C))
        assert(msg_type.is_assign_node())
        self.start_solving()
    
    def pre_partition(self):
        subnodes = deque()
        while True:
            self.receive_message_from_leader()
            self.receive_message_from_partitioner()
            if self.is_done():
                return True
            if self.partitioner.is_done():
                break
            if len(subnodes) == 0:
                if self.tree.root != None:
                    assert(self.tree.root.status.is_unsolved())
                    subnodes.append(self.tree.root)
            if len(subnodes) > 0:
                while len(subnodes) < self.num_coords:
                    node: ParallelNode = subnodes[0]
                    if len(node.children) < 2:
                        break
                    subnodes.popleft()
                    for child in node.children:
                        if child.status.is_unsolved():
                            subnodes.append(child)
                    
            if len(subnodes) >= self.num_coords:
                break
            if self.get_coordinator_time() > 20.0:
                break
            time.sleep(0.01)
        
        pp_num_nodes = len(subnodes)
        # assert(pp_num_nodes > 0)
        MPI.COMM_WORLD.send(ControlMessage.C2L.pre_partition_done,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(pp_num_nodes, 
                            dest=self.leader_rank, tag=2)
        msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
        assert(isinstance(msg_type, ControlMessage.L2C))
        if msg_type.is_assign_node():
            for i in range(1, pp_num_nodes):
                node = subnodes[i]
                self.split_node = node
                self.set_node_split(node, i)
                logging.debug(f'split node-{self.split_node.id} to coordinater-{i}')
                self.send_split_node_to_coordinator(i)
            return False
        elif msg_type.is_terminate_coordinator():
            raise TerminateMessage()
        else:
            assert(False)
    
    def receive_node_from_coordinator(self, coord_rank):
        solving_folder_path = f'{self.temp_folder_path}/tasks/round-{self.solving_round}'
        os.makedirs(solving_folder_path, exist_ok=True)
        instance_path = f'{solving_folder_path}/task-root.smt2'
        instance_data = MPI.COMM_WORLD.recv(source=coord_rank, tag=2)
        with open(instance_path, 'bw') as file:
            file.write(instance_data)
    
    def process_assign_message(self):
        coord_rank = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=2)
        logging.debug(f'receive instance from coordinator-{coord_rank}')
        self.receive_node_from_coordinator(coord_rank)
        self.start_solving()
    
    def send_split_succeed_to_leader(self, target_rank):
        MPI.COMM_WORLD.send(ControlMessage.C2L.split_succeed,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(target_rank, 
                            dest=self.leader_rank, tag=2)
    
    def send_split_node_to_coordinator(self, target_rank):
        instance_path = f'{self.solving_folder_path}/task-{self.split_node.pid}.smt2'
        logging.debug(f'split task path: {instance_path}')
        with open(instance_path, 'br') as file:
            instance_data = file.read()
        MPI.COMM_WORLD.send(instance_data, 
                            dest=target_rank, tag=2)
    
    def send_split_failed_to_leader(self, target_rank):
        MPI.COMM_WORLD.send(ControlMessage.C2L.split_failed,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(target_rank, 
                            dest=self.leader_rank, tag=2)
    
    def process_split_message(self):
        # split a subnode and assign to coordinator {target_rank}
        target_rank = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=2)
        if self.status.is_idle():
            self.send_split_failed_to_leader(target_rank)
            return
        node = self.select_split_node()
        if node == None:
            self.send_split_failed_to_leader(target_rank)
            return
        logging.debug(f'split target rank: {target_rank}')
        logging.debug(f'split node: {node}')
        self.send_split_succeed_to_leader(target_rank)
        self.split_node = node
        self.set_node_split(node, target_rank)
        
    def process_transfer_message(self):
        target_rank = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=2)
        logging.debug(f'split node-{self.split_node.id} to coordinater-{target_rank}')
        self.send_split_node_to_coordinator(target_rank)
    
    def round_clean_up(self):
        assert(self.partitioner != None)
        if self.partitioner.p != None:
            self.partitioner.p.terminate()
        self.partitioner = None
        assert(self.tree != None)
        for node in self.tree.solvings:
            assert(isinstance(node, ParallelNode))
            if node.assign_to != None:
                node.assign_to.terminate()
                node.assign_to = None
        self.tree = None
    
    def clean_up(self):
        if self.status.is_solving():
            self.round_clean_up()
        shutil.rmtree(self.temp_folder_path)

    def solving_round_done(self):
        self.send_result_to_leader()
        self.round_clean_up()
        self.status = CoordinatorStatus.idle
        self.solving_round += 1
        logging.debug(f'round-{self.solving_round} is done')
    
    # True for terminate
    def receive_message_from_leader(self):
        if MPI.COMM_WORLD.Iprobe(source=self.leader_rank, tag=1):
            msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
            assert(isinstance(msg_type, ControlMessage.L2C))
            # logging.debug(f'receive {msg_type} message from leader')
            if msg_type.is_request_split():
                # split a subnode
                self.process_split_message()
            elif msg_type.is_transfer_node():
                # transfer the split node to coordinator {target_rank}
                self.process_transfer_message()
            elif msg_type.is_assign_node():
                # solve node from coordinator {rank}
                assert(self.status.is_idle())
                self.process_assign_message()
            elif msg_type.is_terminate_coordinator():
                if self.tree != None:
                    self.tree.log_display()
                raise TerminateMessage()
            else:
                assert(False)
    
    def solve(self):
        if self.rank == 0:
            self.solve_leader_root()
            if self.pre_partition():
                self.solving_round_done()
        while True:
            self.receive_message_from_leader()
            if self.status.is_solving():
                if self.parallel_solving():
                    self.solving_round_done()
                
            ### TBD ###
            # if len(self.running_tasks) + self.base_run_cnt >= self.max_running_tasks \
            #     or (not self.need_communicate):
            #     time.sleep(0.01)
            
            # time.sleep(0.01)
    
    def __call__(self):
        try:
            self.solve()
        except TerminateMessage:
            logging.info(f'Coordinator-{self.rank} is Terminated by Leader')
        except Exception as e:
            logging.error(f'Coordinator-{self.rank} Exception: {e}')
            logging.error(f'{traceback.format_exc()}')
            MPI.COMM_WORLD.Abort()
        self.clean_up()