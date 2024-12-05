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


def raise_error(error_info):
    logging.error(error_info)
    raise Exception(error_info)

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
        # terminate on demand
        # self.terminate_threshold = [1200.0, 200.0, 100.0]
        self.terminate_threshold = [1200.0, 400.0, 300.0, 200.0, 0.0]
        
        self.coordinator_start_time = time.time()
        self.rank = MPI.COMM_WORLD.Get_rank()
        self.leader_rank = MPI.COMM_WORLD.Get_size() - 1
        self.isolated_rank = self.leader_rank - 1
        self.num_dist_coords = self.isolated_rank
        self.init_params()
        
        self.coord_temp_folder_path = f'{self.temp_dir}/Coordinator-{self.rank}'
        # assign a core to coordinator and partitioner
        self.available_cores -= 1
        self.max_unsolved_tasks = self.available_cores + self.available_cores // 3 + 1
        
        self.init_logging()
        os.makedirs(self.coord_temp_folder_path, exist_ok=True)
        
        self.status: CoordinatorStatus = CoordinatorStatus.idle
        self.result = NodeStatus.unsolved
        self.partitioner = None
        self.tree = None
        
        logging.debug(f'rank: {self.rank}, leader_rank: {self.leader_rank}')
        logging.debug(f'temp_folder_path: {self.coord_temp_folder_path}')
        logging.debug(f'coordinator-{self.rank} init done!')
    
    def init_logging(self):
        log_dir_path = f'{self.output_folder_path}/logs'
        os.makedirs(log_dir_path, exist_ok=True)
        if self.rank == self.isolated_rank:
            log_file_path = f'{log_dir_path}/coordinator-isolated.log'
        else:
            log_file_path = f'{log_dir_path}/coordinator-{self.rank}.log'
        logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
                filename=log_file_path, level=logging.DEBUG)
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
        self.temp_dir: str = cmd_args.temp_dir
        self.output_folder_path: str = cmd_args.output_dir
        
        available_cores_list: list = json.loads(cmd_args.available_cores_list)
        
        self.available_cores: int = available_cores_list[self.rank]
        
    
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
                    raise_error('Partitioner error')
                    # assert(False)
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
                # if pid % 10 == 0:
                #     self.log_tree_infos()
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
    
    def check_subprocess_status(self, p: subprocess.Popen):
        rc = p.poll()
        if rc == None:
            return NodeStatus.solving

        out_data, err_data = p.communicate()
        
        if rc != 0:
            logging.error('subprocess error')
            logging.error(f'return code = {rc}')
            logging.error(f'stdout: {out_data}')
            logging.error(f'stderr: {err_data}')
            return NodeStatus.error
            # raise_error(f'return code = {rc}\nstdout: {out_data}\nstderr: {err_data}')

        sta: str = out_data.strip('\n').strip(' ')
        assert(rc == 0)
        if sta == 'sat':
            return NodeStatus.sat
        elif sta == 'unsat':
            return NodeStatus.unsat
        else:
            logging.error('subprocess error')
            logging.error(f'return code = {rc}')
            logging.error(f'stdout: {out_data}')
            logging.error(f'stderr: {err_data}')
            return NodeStatus.error
            # raise_error(f'subprocess error state: {sta}')
    
    def send_partitioner_message(self, msg: str):
        logging.debug(f'send_partitioner_message: {msg}')
        self.partitioner.send_message(msg)
    
    def sync_ended_to_partitioner(self, node: ParallelNode, status: NodeStatus):
        if self.partitioner.check_p_status():
            return
        if status.is_unsat():
            sta_val = ControlMessage.C2P.unsat_node.value
        else:
            sta_val = ControlMessage.C2P.terminate_node.value
        msg = f'{sta_val} {node.pid}'
        self.send_partitioner_message(msg)
    
    def need_terminate(self, node: ParallelNode):
        if node.id == 0:
            return False
        num_children = len(node.children)
        # num_start = 0
        child_progress = 0
        if num_children > 0:
            # lc: ParallelNode = node.children[0]
            # if not lc.status.is_unsolved():
            #     num_start += 1
            lc_sta: NodeStatus = node.children[0].status
            if not lc_sta.is_unsolved():
                if lc_sta.is_solved():
                    child_progress += 2
                else:
                    child_progress += 1
            if num_children > 1:
                # rc: ParallelNode = node.children[1]
                # if not rc.status.is_unsolved():
                #     num_start += 1
                rc_sta: NodeStatus = node.children[1].status
                if not rc_sta.is_unsolved():
                    if rc_sta.is_solved():
                        child_progress += 2
                    else:
                        child_progress += 1
        assert(child_progress < 4)
        solving_time = self.tree.get_node_solving_time(node)
        assert(solving_time is not None)
        # if solving_time < self.terminate_threshold[num_start]:
        #     return False
        # return True
        # return solving_time > self.terminate_threshold[num_start]
        return solving_time > self.terminate_threshold[child_progress]
    
    def terminate_node(self, node: ParallelNode):
        if node.status.is_ended():
            return
        logging.info(f'terminate node-{node.id}')
        self.tree.terminate_node(node, NodeReason.coordinator)
        self.sync_ended_to_partitioner(node, NodeStatus.terminated)
    
    # True for still running
    def check_solving_status(self, node: ParallelNode):
        if not node.status.is_solving():
            return False
        sta: NodeStatus = self.check_subprocess_status(node.assign_to)
        if sta.is_error():
            self.terminate_node(node)
            return False
        if sta.is_solving():
            # return True
            # ### TBD ###
            if not self.need_terminate(node):
                return True
            logging.info(f'terminate on demand')
            self.terminate_node(node)
            return False
        node.assign_to = None
        logging.info(f'solved: node-{node.id} is {sta}')
        self.tree.node_solved(node, sta)
        # if self.tree.update_dict.get((NodeStatus.unsat, NodeReason.itself), 0) % 10 == 0:
        #     self.log_tree_infos()
        self.log_tree_infos()
        if self.is_done():
            return False
        assert(sta.is_unsat())
        self.sync_ended_to_partitioner(node, NodeStatus.unsat)
        return False
    
    def solve_task(self, task_tag: str):
        instance_path = f'{self.solving_folder_path}/task-{task_tag}.smt2'
        cmd =  [self.solver_path,
                instance_path,
            ]
        # logging.debug('exec-command {}'.format(' '.join(cmd)))
        p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        return p
    
    def solve_node(self, node: ParallelNode):
        p = self.solve_task(f'{node.pid}')
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
        while len(self.tree.solvings) < self.available_cores:
            node = self.tree.get_next_waiting_node()
            if node == None:
                break
            self.solve_node(node)
    
    # run the partitioner
    def run_partitioner(self):
        if self.rank != self.isolated_rank:
            parti_seed = 0
        else:
            parti_seed = 1
        
        cmd =  [self.partitioner_path,
                f'{self.solving_folder_path}/task-root.smt2',
                f'-outputdir:{self.solving_folder_path}',
                f'-partimrt:{max(self.available_cores, self.num_dist_coords)}',
                f'-partiseed:{parti_seed}'
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
        self.solving_folder_path = f'{self.coord_temp_folder_path}/tasks/round-{self.solving_round}'
        
        self.status = CoordinatorStatus.solving
        self.result = NodeStatus.unsolved
        self.solving_start_time = time.time()
        self.tree = ParallelTree(self.solving_start_time)
        self.split_node = None
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
            # self.tree_log_display()
            return True
        self.run_waiting_tasks()
        return False
    
    def select_split_node(self):
        return self.tree.select_split_node()

    def set_node_split(self, node: ParallelNode, assigned_coord: int):
        path_node = node
        while path_node is not None:
            self.terminate_node(path_node)
            path_node = path_node.parent
        self.tree.set_node_split(node, assigned_coord)
        self.sync_ended_to_partitioner(node, NodeStatus.unsat)
    
    def solve_leader_root(self):
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
                while len(subnodes) < self.num_dist_coords:
                    node: ParallelNode = subnodes[0]
                    if len(node.children) < 2:
                        break
                    subnodes.popleft()
                    for child in node.children:
                        if child.status.is_unsolved():
                            subnodes.append(child)
                    
            if len(subnodes) >= self.num_dist_coords:
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
        solving_folder_path = f'{self.coord_temp_folder_path}/tasks/round-{self.solving_round}'
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
        # shutil.rmtree(self.solving_folder_path)

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
                self.tree_log_display()
                raise TerminateMessage()
            else:
                assert(False)
    
    def interactive_solve(self):
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
            # sleep
    
    def check_original_task(self):
        if self.original_process is None:
            return False
        sta: NodeStatus = self.check_subprocess_status(self.original_process)
        if sta.is_solving():
            return False
        elif sta.is_error():
            self.original_process = None
            return False
        else:
            self.result = sta
            logging.info(f'solved-by-original {sta}')
            return True
    
    # solver original task with base solver
    def solve_original_task(self):
        logging.debug('solve_original_task')
        self.original_process = self.solve_task('root')
    
    def isolated_solve(self):
        self.solve_leader_root()
        self.solve_original_task()
        while True:
            if MPI.COMM_WORLD.Iprobe(source=self.leader_rank, tag=1):
                msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
                assert(isinstance(msg_type, ControlMessage.L2C))
                assert(msg_type.is_terminate_coordinator())
                self.tree_log_display()
                raise TerminateMessage()
            if self.status.is_solving():
                if self.check_original_task():
                    self.solving_round_done()
                    continue
                if self.parallel_solving():
                    self.tree_log_display()
                    self.solving_round_done()
            ### TBD ###
            # sleep
    
    def tree_log_display(self):
        if self.tree != None:
            self.tree.log_display()
    
    def clean_up(self):
        if self.rank == self.isolated_rank:
            if self.original_process != None:
                self.original_process.terminate()
        if self.status.is_solving():
            self.round_clean_up()
            
    def clean_temp_dir(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def __call__(self):
        try:
            if self.rank == self.isolated_rank:
                self.isolated_solve()
            else:
                self.interactive_solve()
        except TerminateMessage:
            logging.info(f'Coordinator-{self.rank} is Terminated by Leader')
        except Exception as e:
            logging.error(f'Coordinator-{self.rank} Exception: {e}')
            logging.error(f'{traceback.format_exc()}')
            MPI.COMM_WORLD.send(ControlMessage.C2L.notify_error,
                            dest=self.leader_rank, tag=1)
            while True:
                msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
                assert(isinstance(msg_type, ControlMessage.L2C))
                if msg_type.is_terminate_coordinator():
                    break
            # MPI.COMM_WORLD.Abort()
        self.clean_up()
        MPI.COMM_WORLD.Barrier()
        self.clean_temp_dir()
