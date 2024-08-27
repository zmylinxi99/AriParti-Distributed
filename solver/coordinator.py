
import os
import time
import logging
import argparse
import subprocess
from mpi4py import MPI
from enum import Enum
# import enum
# from enum import auto

from partition_tree import ParallelTree
from partition_tree import ParallelNode
from partition_tree import ParallelNodeStatus
from partition_tree import ParallelNodeSolvedReason

from control_message import ControlMessage
from partitioner import Partitioner

class CoordinatorStatus(Enum):
    idle = 0
    solving = 1
    
    def is_idle(self):
        return self == CoordinatorStatus.idle

    def is_solving(self):
        return self == CoordinatorStatus.solving

class Coordinator():
    def __init__(self):
        self.coordinator_start_time = time.time()
        
        self.init_params()
        
        # assign a core to coordinator and partitioner
        self.available_cores -= 1
        
        self.rank = MPI.COMM_WORLD.Get_rank()
        self.leader_rank = MPI.COMM_WORLD.Get_size() - 1
        self.max_unsolved_tasks = self.available_cores + self.available_cores // 3 + 1
        
        self.solving_round = 0
        
        self.init_logging()
        logging.info(f'temp_folder_path: {self.temp_folder_path}')
        self.status: CoordinatorStatus = CoordinatorStatus.idle
    
    def init_params(self):
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--partitioner', type=str, required=True,
                                help="partitioner path")
        arg_parser.add_argument('--solver', type=str, required=True,
                                help="solver path")
        arg_parser.add_argument('--temp-dir', type=str, required=True, 
                                help='temp dir path')
        arg_parser.add_argument('--available-cores', type=int, required=True, 
                                help="available cores in this equipment")
        cmd_args = arg_parser.parse_args()
        self.partitioner_path: str = cmd_args.partitioner
        self.solver_path: str = cmd_args.solver
        self.temp_folder_path: str = cmd_args.temp_dir
        self.available_cores: int = cmd_args.available_cores
    
    def is_done(self):
        return self.result.is_done()
    
    def get_result(self):
        return self.result
    
    def get_solving_time(self):
        return time.time() - self.solving_start_time
    
    def get_coordinator_time(self):
        return time.time() - self.coordinator_start_time
    
    def init_logging(self):
        # if self.output_dir_path != None:
        #     logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
        #             filename=f'{self.output_dir_path}/log', level=logging.INFO)
        # self.start_time = time.time()
        # current_time = datetime.now()
        # formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        # self.write_line_to_log(f'start-time {formatted_time} ({self.start_time})')
        ### TBD ###
        pass
    
    def write_line_to_log(self, data: str):
        # logging.info(data)
        pass
    
    def process_partitioner_msg(self, msg: str):
        words = msg.split(' ')
        op = words[1]
        if op == 'debug-info':
            remains = " ".join(words[2: ])
            self.write_line_to_log(f'partitioner-debug-info {remains}')
        elif op in ['new-task', 'unsat-task']:
            id = int(words[2])
            pid = int(words[3])
            if pid == -1:
                parent = None
            else:
                parent = self.tree.nodes[pid]
            node = self.tree.make_node(parent)
            if op == 'unsat-task':
                self.tree.node_solved(node, ParallelNodeStatus.unsat, 
                                      ParallelNodeSolvedReason.partitioner)
            ### TBD ###
        elif op in ['sat', 'unsat', 'unknown']:
            ### TBD ###
            assert(len(words) == 1)
            self.partitioner.set_status(op)
        else:
            assert(False)
        
    def receive_message_from_partitioner(self):
        while True:
            msg = self.partitioner.receive_message()
            if msg == None:
                break
            self.process_partitioner_msg(msg)
    
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
            return ParallelNodeStatus.solving
        out_data, err_data = p.communicate()
        sta: str = out_data.strip('\n').strip(' ')
        if rc != 0:
            return ParallelNodeStatus.error
        if sta == 'sat':
            return ParallelNodeStatus.sat
        elif sta == 'unsat':
            return ParallelNodeStatus.unsat
        else:
            assert(False)
    
    def terminate_task(self, t: Task):
        t.status = 'terminated'
        if t.p != None:
            self.terminate(t.p)
            self.free_worker(t.p)
            t.p = None
        self.partitioner.send_message(f'terminate-node {t.id}')
    
    # True for still running
    def check_solving_status(self, node: ParallelNode):
        if not node.status.is_solving():
            return False
        sta: ParallelNodeStatus = self.check_subprocess_status(node.assign_to)
        if sta.is_solving():
            return True
            # if self.need_terminate(t):
            #     self.update_task_status(t, 'terminated')
            #     self.terminate_task(t)
            #     return False
            # else:
            #     return True
        node.assign_to = None
        self.tree.node_solved(node, 
                              ParallelNodeStatus.unsat)
        if self.tree.is_done():
            self.result = self.tree.get_result()
        return False
    
    def solve_node(self, node: ParallelNode):
        instance_path = f'{self.solving_folder_path}/task-{node.id}.smt2'
        cmd =  [self.solver_path,
                instance_path,
            ]
        self.write_line_to_log('exec-command {}'.format(' '.join(cmd)))
        p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        self.tree.solve_node(node, p)
        
        self.write_line_to_log(f'solve-node {node.id}')
    
    def check_solvings_status(self):
        still_solvings = [] 
        for node in self.tree.solvings:
            node: ParallelNode
            if not node.status.is_solving():
                if node.assign_to != None:
                    p: subprocess.Popen = node.assign_to
                    p.terminate()
                    node.assign_to = None
                continue
            if self.check_solving_status(node):
                still_solvings.append(node)
            else:
                if self.is_done():
                    return
        self.tree.solvings = still_solvings
        
        ### TBD ###
        # if self.partitioner.status != 'solving' and \
        #     len(self.status_tasks_dict['solving']) == 0 and \
        #     self.result not in ['sat', 'unsat']:
        #     self.result = 'unknown'
        #     self.reason = -3
        #     self.done = True
        #     if self.solve_ori_flag:
        #         if self.ori_task.status == 'solving':
        #             self.write_line_to_log(f'unknown partitioner bug')
        #         else:
        #             self.write_line_to_log(f'unknown instance bug')
        #     return
    
    
    
    # run waitings by:
    # currently: generation order
    # can be easily change to: priority select
    def run_waiting_tasks(self):
        ### TBD ###
        while self.tree.running_nodes_number() < self.available_cores:
            node = self.tree.get_next_waiting_node()
            if node == None:
                break
            self.solve_node(node)
            self.write_line_to_log(f'running: {self.get_running_num()}, unended: {self.get_unended_num()}')
    
    # run the partitioner
    def run_partitioner(self):
        cmd =  [self.partitioner_path,
                f'{self.solving_folder_path}/task-root.smt2',
                f"-outputdir:{self.solving_folder_path}",
                f"-partmrt:{self.available_cores}"
            ]
        self.write_line_to_log(f'exec-command {" ".join(cmd)}')
        p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        
        self.partitioner = Partitioner(p)
    
    def terminate_partitioner(self):
        if self.partitioner.status == 'solving':
            self.partitioner.p.terminate()
    
    def start_solving(self):
        self.solving_folder_path = f'{self.temp_folder_path}/tasks/round-{self.solving_round}'
        
        self.status = CoordinatorStatus.solving
        self.result = ParallelNodeStatus.unsolved
        self.solving_start_time = time.time()
        self.tree = ParallelTree(self.solving_start_time)
        
        # ##//linxi debug
        # print(self.temp_folder_path)
        # print(f'{self.output_dir_path}/log')
        
        ### TBD ###
        self.init_logging()
        logging.info(f'temp_folder_path: {self.temp_folder_path}')
        self.init_partitioner_comm()
        self.run_partitioner()

    # if self.partitioner.is_running():
    #     sta = self.check_partitioner_status()
    #     if sta != 'solving':
    #         if sta in ['sat', 'unsat']:
    #             self.result = sta
    #             self.done = True
    #             self.write_line_to_log(f'solved-by-partitioner {sta}')
    #             return
    #         self.partitioner.status = sta

    # coordinator [rank] solved the assigned node
    def send_result_to_leader(self):
        result: ParallelNodeStatus = self.get_result()
        assert(result.is_solved())
        
        MPI.COMM_WORLD.send(ControlMessage.C2L.notify_result,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(result, dest=self.leader_rank, tag=2)
    
    def parallel_solving(self):
        if self.partitioner.is_running():
            self.receive_message_from_partitioner()
        
        self.check_solvings_status()
        if self.is_done():
            self.send_result_to_leader()
            self.status = CoordinatorStatus.idle
            self.solving_round += 1
            return
        self.run_waiting_tasks()
        # if len(self.running_tasks) + self.base_run_cnt >= self.max_running_tasks \
        #     or (not self.need_communicate):
        #     time.sleep(0.1)

    
    def select_split_node(self):
        ### TBD ###
        pass
    
    def clean_up(self):
        ### TBD ###
        # finished
        pass
    
    def solve_node_0_in_leader(self):
        while not MPI.COMM_WORLD.Iprobe(source=self.leader_rank, tag=1):
            time.sleep(0.1)
        msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
        assert(isinstance(msg_type, ControlMessage.L2C))
        assert(msg_type.is_assign_node())
        self.start_solving()
        ### TBD ###
    
    def receive_node_from_coordinator(self, coordinator_rank):
        solving_folder_path = f'{self.temp_folder_path}/tasks/round-{self.solving_round}'
        os.makedirs(solving_folder_path)
        instance_path = f'{solving_folder_path}/task-root.smt2'
        while not MPI.COMM_WORLD.Iprobe(source=coordinator_rank, tag=2):
            time.sleep(0.1)
        instance_data = MPI.COMM_WORLD.recv(source=coordinator_rank, tag=2)
        with open(instance_path, 'bw') as file:
            file.write(instance_data)
    
    def process_assign_message(self):
        coordinator_rank, node_id = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=2)
        self.receive_node_from_coordinator(coordinator_rank, node_id)
        self.start_solving(node_id)
    
    def send_node_path_to_leader(self, path):
        MPI.COMM_WORLD.send(ControlMessage.C2L.send_path,
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(path, dest=self.leader_rank, tag=2)
    
    def process_split_message(self):
        # split a subnode and assign to coordinator {target_rank}
        node = self.select_split_node()
        path = self.tree.get_path(node)
        target_rank = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=2)

        MPI.COMM_WORLD.send(ControlMessage.C2L.send_path, 
                            dest=self.leader_rank, tag=1)
        MPI.COMM_WORLD.send(path, 
                            dest=self.leader_rank, tag=2)
        
        MPI.COMM_WORLD.send(ControlMessage.C2C.send_subnode,
                            dest=target_rank, tag=1)
        
        with open(instance_path, 'br') as file:
            instance_data = file.read()
        ### TBD ###
        pass
    
    def __call__(self):
        if self.rank == 0:
            self.solve_node_0_in_leader()
        
        while True:
            if MPI.COMM_WORLD.Iprobe(source=self.leader_rank, tag=1):
                msg_type = MPI.COMM_WORLD.recv(source=self.leader_rank, tag=1)
                assert(isinstance(msg_type, ControlMessage.L2C))
                if msg_type.is_assign_node():
                    # solve node from coordinator {rank}
                    assert(self.status.is_idle())
                    self.process_assign_message()
                elif msg_type.is_request_split():
                    # split a subnode and assign to coordinator {target_rank}
                    assert(self.status.is_solving())
                    self.process_split_message()
                elif msg_type.is_terminate_coordinator():
                    break
                else:
                    assert(False)
            if self.status.is_solving():
                self.parallel_solving()
            time.sleep(0.1)
            
        self.clean_up()
        
if __name__ == '__main__':
    # print(f'cmd_args.temp_dir: {cmd_args.temp_dir}')
    ap_coordinator = Coordinator()
    ap_coordinator()