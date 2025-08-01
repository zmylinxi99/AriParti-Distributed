
import time
from collections import deque
import logging
import subprocess
from enum import Enum, auto

# NodeStatus
# waiting solving sat unsat unknown
# waiting -> solving BY (run task)
#         -> unsat   BY (ancester, children, partitioner)
#         -> unknown BY (children)
# solving -> sat BY (solver)
#         -> unsat BY (solver, ancester, children, partitioner)
#         -> unknown BY (solver, children)
class NodeStatus(Enum):
    unsolved = auto()
    sat = auto()
    unsat = auto()
    solving = auto()
    terminated = auto()
    error = auto()
    
    def is_unsolved(self):
        return self == NodeStatus.unsolved
    
    def is_sat(self):
        return self == NodeStatus.sat
    
    def is_unsat(self):
        return self == NodeStatus.unsat
    
    def is_solved(self):
        return self.is_sat() or self.is_unsat()
    
    def is_solving(self):
        return self == NodeStatus.solving
    
    def is_terminated(self):
        return self == NodeStatus.terminated
    
    def is_error(self):
        return self == NodeStatus.error
    
    def is_ended(self):
        return self.is_solved() or self.is_terminated()

class NodeReason(Enum):
    # by
    itself = auto()
    ancester = auto()
    children = auto()
    
    # parallel
    partitioner = auto()
    split = auto()
    coordinator = auto()
    
    # distributed
    original = auto()

class PartitionNode:
    def __init__(self, id, parent, make_time):
        self.assign_to = None
        self.time_infos = {}
        self.children = []
        self.status: NodeStatus
        
        self.id = id
        self.parent = parent
        if parent != None:
            parent: PartitionNode
            parent.children.append(self)
        self.update_status(NodeStatus.unsolved, 
                           NodeReason.itself, 
                           make_time)

    def update_status(self, status, reason, current_time):
        self.time_infos[status] = current_time
        self.status = status
        self.reason = reason
        logging.debug(f'node-{self.id} is {status} by {reason}')
    
    def __str__(self) -> str:
        if self.parent == None:
            parent_id = -1
        else:
            parent_id = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {parent_id}'
        ret += f', status: {self.status}\n'
        ret += f'children: {[child.id for child in self.children]}\n'
        ret += f'time-infos: {self.time_infos}\n'
        return ret

class PartitionTree:
    def __init__(self, start_time):
        self.nodes = []
        self.result = NodeStatus.unsolved
        self.start_time = start_time
        self.root = None
        self.update_dict = {}
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def is_done(self):
        return self.result.is_solved()
    
    def get_result(self):
        return self.result
    
    def update_node_status(self, node: PartitionNode,
                           status: NodeStatus,
                           reason: NodeReason):
        current_time = self.get_current_time()
        node.update_status(status, reason, current_time)
        self.update_dict[(status, reason)] = self.update_dict.get((status, reason), 0) + 1
        

class ParallelNode(PartitionNode):
    def __init__(self, id, parent, make_time, pid):
        self.assigned_coord = None
        self.unsat_percent = 0.0
        
        super().__init__(id, parent, make_time)
        self.pid = pid
    
    def get_solve_start_time(self):
        return self.time_infos.get(NodeStatus.solving, None)
    
    def can_reason_unsat(self):
        if len(self.children) < 2:
            return False
        for child in self.children:
            child: ParallelNode
            if not child.status.is_unsat():
                return False
        return True
    
    def update_unsat_percent(self):
        self.unsat_percent = sum(child.unsat_percent for child in self.children) / 2.0
    
    def __str__(self) -> str:
        ret = super().__str__()
        ret += f'unsat_percent: {self.unsat_percent}, pid: {self.pid}\n'
        return ret

class ParallelTree(PartitionTree):
    def __init__(self, start_time):
        self.solvings = []
        self.waitings = deque()
        # self.endeds = []
        self.pid2node = {}
        
        self.total_solve_time = 0.0
        self.average_solve_time = 0.0
        self.split_thres_max = 25.0
        self.split_thres_min = 5.0
        
        super().__init__(start_time)
    
    def update_node_status(self, node: ParallelNode,
                           status: NodeStatus,
                           reason: NodeReason):
        super().update_node_status(node, status, reason)
        
        if status.is_unsat():
            node.unsat_percent = 1.0
            if reason == NodeReason.itself:
                solve_time = self.get_node_solving_time(node)
                self.total_solve_time += solve_time
                solved_number = self.update_dict[(NodeStatus.unsat, NodeReason.itself)]
                self.average_solve_time = self.total_solve_time / solved_number
                logging.debug(f'solve time: {solve_time}')
                logging.debug(f'solved_number: {solved_number}, average_solve_time: {self.average_solve_time}')
            # elif reason == NodeReason.split:
            #     self.sync_to_partitioner(node)
            # else:
            #     pass
        # elif status.is_terminated():
        #     self.sync_to_partitioner(node)
    
    # pid: id in partitioner
    # ppid: parent id in partitioner
    def make_node(self, pid, ppid):
        id = len(self.nodes)
        if ppid == -1:
            parent = None
        else:
            parent = self.pid2node[ppid]
        node = ParallelNode(id, parent, self.get_current_time(), pid)
        self.nodes.append(node)
        self.pid2node[pid] = node
        if id == 0:
            self.root = node
        # logging.debug(f'parallel tree make node: {node}')
        return node
    
    def get_next_waiting_node(self):
        while len(self.waitings) > 0:
            node: ParallelNode = self.waitings.popleft()
            if node.status.is_unsolved():
                return node
        return None
    
    def get_solving_number(self):
        return len(self.solvings)
    
    # def get_ended_number(self):
    #     return len(self.endeds)
    
    def get_node_number(self):
        return len(self.nodes)
    
    # def get_unended_number(self):
    #     return len(self.nodes) - len(self.endeds)
    
    # precond: node is solving
    # terminate: unsolved or solving
    def terminate_node(self, node: ParallelNode, reason: NodeReason):
        # if node.status.is_ended():
        #     return
        self.update_node_status(node, 
                    NodeStatus.terminated, 
                    reason)
        if node.assign_to != None:
            node.assign_to.terminate()
            node.assign_to = None
    
    # def terminate_split_path(self, node: ParallelNode):
    #     self.terminate_node(node, NodeReason.split)
    #     if node.parent != None:
    #         self.terminate_split_path(node.parent)
    
    def set_node_split(self, node: ParallelNode, assigned_coord: int):
        # self.terminate_split_path(node)
        node.assigned_coord = assigned_coord
        self.node_solved_unsat(node, NodeReason.split)
    
    def get_node_solving_time(self, node: ParallelNode):
        solve_start_time = node.get_solve_start_time()
        if solve_start_time == None:
            return None
        return self.get_current_time() - solve_start_time
    
    def satisfy_split_requirement(self, node: ParallelNode):
        solving_time = self.get_node_solving_time(node)
        if solving_time == None:
            return False
        if solving_time < self.split_thres_min:
            return False
        if solving_time > self.split_thres_max:
            return True
        return solving_time > self.average_solve_time
    
    def select_split_node(self):
        if self.root == None:
            return None
        if self.is_done():
            return None
        current: ParallelNode = self.root
        while True:
            if len(current.children) < 2:
                return None
            assert(len(current.children) == 2)
            lc: ParallelNode = current.children[0]
            rc: ParallelNode = current.children[1]
            assert((not lc.status.is_unsat()) or (not rc.status.is_unsat()))
            if lc.status.is_unsat():
                current = rc
            elif rc.status.is_unsat():
                current = lc
            else:
                if self.satisfy_split_requirement(lc) and \
                   self.satisfy_split_requirement(rc):
                    return rc
                else:
                    return None
    
    def propagate_node_unsat(self,
            node: ParallelNode,
            reason: NodeReason):
        self.update_node_status(node, 
                                NodeStatus.unsat, 
                                reason)
        
        # self.write_line_to_partitioner(f'unsat-node {t.id}')
        if node.assign_to != None:
            node.assign_to.terminate()
            node.assign_to = None
    
    def update_node_unsat_percent(self, node: ParallelNode):
        current = node
        while current is not None:
            current.update_unsat_percent()
            current = current.parent
    
    def unsat_push_up(self, node: ParallelNode):
        if node.status.is_unsat():
            return
        if node.can_reason_unsat():
            self.propagate_node_unsat(node, NodeReason.children)
            if node.parent != None:
                self.unsat_push_up(node.parent)
        else:
            self.update_node_unsat_percent(node)
    
    def unsat_push_down(self, node: ParallelNode):
        if node.status.is_unsat():
            return
        self.propagate_node_unsat(node, NodeReason.ancester)
        for child in node.children:
            self.unsat_push_down(child)
    
    def node_solved_unsat(self,
            node: ParallelNode,
            reason: NodeReason):
        self.update_node_status(node,
                NodeStatus.unsat,
                reason)
        if node.parent != None:
            self.unsat_push_up(node.parent)
        if self.root.status.is_unsat():
            self.result = NodeStatus.unsat
            return
        for child in node.children:
            self.unsat_push_down(child)
    
    def node_solved_sat(self,
            node: ParallelNode,
            reason: NodeReason):
        self.update_node_status(node,
                NodeStatus.sat, reason)
        self.result = NodeStatus.sat
    
    def node_solved(self, 
            node: ParallelNode,
            status: NodeStatus,
            reason: NodeReason = NodeReason.itself):
        # logging.debug(f'node-{node.id} is solved: {status} by {reason} in {self.get_node_solving_time(node)}s')
        if status.is_sat():
            self.node_solved_sat(node, reason)
        elif status.is_unsat():
            self.node_solved_unsat(node, reason)
        else:
            assert(False)
    
    def assign_node(self, node: ParallelNode, p: subprocess.Popen):
        assert(node.assign_to == None)
        node.assign_to = p
        node.update_status(NodeStatus.solving,
                           NodeReason.itself,
                           self.get_current_time())
        self.solvings.append(node)
        
    # def log_display_dfs(self, node: ParallelNode, depth: int):
    #     logging.debug(f'{" " * (2 * depth)}({node.id}, {node.status})')
    #     for child in node.children:
    #         self.log_display_dfs(child, depth + 1)
    
    # def log_display(self):
    #     logging.debug(f'display parallel tree')
    #     if self.root != None:
    #         self.log_display_dfs(self.root, 0)
    
    def log_display(self):
        logging.debug(f'display parallel tree')
        stack = deque()
        if self.root is not None:
            stack.append((self.root, 0))
        while len(stack) > 0:
            # bfs, dfs
            # node, depth = stack.popleft()
            node, depth = stack.pop()
            logging.debug(f'{" " * (2 * depth)}({node.id}, {node.status})')
            for child in node.children:
                stack.append((child, depth + 1))

class DistributedNode(PartitionNode):
    def __init__(self, id, parent, make_time):
        self.partial_status = NodeStatus.unsolved
        super().__init__(id, parent, make_time)
        ### TBD ###
    
    def update_status(self, status, reason, current_time):
        super().update_status(status, reason, current_time)
        ### TBD ###
    
    def update_partial_status(self, partial_status):
        self.partial_status = partial_status
    
    def can_reason_unsat(self):
        if not self.partial_status.is_unsat():
            return False
        for child in self.children:
            child: DistributedNode
            if not child.status.is_unsat():
                return False
        return True

class DistributedTree(PartitionTree):
    def __init__(self, start_time):
        super().__init__(start_time)
    
    def make_node(self, parent):
        id = len(self.nodes)
        node = DistributedNode(id, parent, self.get_current_time())
        self.nodes.append(node)
        return node
    
    def unsat_push_up(self, node: DistributedNode):
        assert(not node.status.is_unsat())
        if node.can_reason_unsat():
            self.update_node_status(node, 
                NodeStatus.unsat, 
                NodeReason.itself)
            if node.parent != None:
                self.unsat_push_up(node.parent)
    
    def node_partial_solved_unsat(self,
            node: DistributedNode):
        node.update_partial_status(NodeStatus.unsat)
        self.unsat_push_up(node)
        if self.root.status.is_unsat():
            self.result = NodeStatus.unsat
            return
    
    def node_partial_solved_sat(self,
            node: DistributedNode):
        node.update_partial_status(NodeStatus.sat)
        self.result = NodeStatus.sat
    
    def node_partial_solved(self, 
            node: DistributedNode,
            status: NodeStatus):
        if status.is_sat():
            self.node_partial_solved_sat(node)
        elif status.is_unsat():
            self.node_partial_solved_unsat(node)
        else:
            assert(False)
    
    def original_solved(self, result):
        self.update_node_status(self.root, result, 
                                    NodeReason.original)
        self.result = result
    
    def assign_root_node(self, coord_isolated):
        self.root = self.make_node(None)
        self.root.assign_to = coord_isolated

    # split node from {parent} to {coord_id}
    def split_node(self, parent: DistributedNode, coord_id: int):
        ret = self.make_node(parent)
        ret.assign_to = coord_id
        return ret
    
    # def log_display_dfs(self, node: DistributedNode, depth: int):
    #     logging.debug(f'{" " * (2 * depth)}({node.id}, {node.partial_status}, {node.status})')
    #     for child in node.children:
    #         self.log_display_dfs(child, depth + 1)
    
    def log_display(self):
        logging.debug(f'display distributed tree')
        # self.log_display_dfs(self.root, 0)
        stack = deque()
        if self.root is not None:
            stack.append((self.root, 0))
        while len(stack) > 0:
            # bfs, dfs
            # node, depth = stack.popleft()
            node, depth = stack.pop()
            logging.debug(f'{" " * (2 * depth)}({node.id}, {node.partial_status}, {node.status})')
            for child in node.children:
                stack.append((child, depth + 1))
    