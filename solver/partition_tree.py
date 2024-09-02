
import time
import queue
import subprocess
from enum import Enum

class PartitionNodeStatus(Enum):
    unsolved = 0
    sat = 1
    unsat = 2
    error = 3
    
    def is_unsolved(self):
        return self == PartitionNodeStatus.unsolved
    
    def is_sat(self):
        return self == PartitionNodeStatus.sat
    
    def is_unsat(self):
        return self == PartitionNodeStatus.unsat
    
    def is_solved(self):
        return self.is_sat() or self.is_unsat()

class PartitionNodeSolvedReason(Enum):
    # by
    itself = 0
    ancester = 1
    children = 2

class PartitionNode:
    assign_to = None
    time_infos = {}
    children = []
    status: PartitionNodeStatus
    reason: PartitionNodeSolvedReason
    
    def __init__(self, id, parent, make_time):
        self.id = id
        self.parent = parent
        self.update_status(PartitionNodeStatus.unsolved, 
                           PartitionNodeSolvedReason.itself, 
                           make_time)

    def update_status(self, status, reason, current_time):
        self.time_infos[status] = current_time
        self.status = status
        self.reason = reason
    
    def __str__(self) -> str:
        pid = -1
        if (self.parent != None):
            pid = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {pid}'
        ret += f', status: {self.status}'
        if len(self.children) > 0:
            stid = [child.id for child in self.children]
            ret += f', children: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret

class PartitionTree:
    root: None | PartitionNode
    nodes = []
    result = PartitionNodeStatus.unsolved
    
    def __init__(self, start_time):
        self.start_time = start_time
        self.root = None
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def make_node(self, parent):
        id = len(self.nodes)
        node = PartitionNode(id, parent, self.get_current_time())
        self.nodes.append(node)
        if id == 0:
            self.root = node
        return node
    
    def is_done(self):
        return self.result.is_solved()
    
    def get_result(self):
        return self.result
    
    def update_node_status(self, node: PartitionNode,
                           status: PartitionNodeStatus,
                           reason: PartitionNodeSolvedReason):
        current_time = self.get_current_time()
        node.update_status(status, reason, current_time)

# ParallelNodeStatus
# waiting solving sat unsat unknown
# waiting -> solving BY (run task)
#         -> unsat   BY (ancester, children, partitioner)
#         -> unknown BY (children)
# solving -> sat BY (solver)
#         -> unsat BY (solver, ancester, children, partitioner)
#         -> unknown BY (solver, children)
class ParallelNodeStatus(PartitionNodeStatus):
    # unsolved means waiting
    solving = 10
    terminated = 11
    
    def is_solving(self):
        return self == ParallelNodeStatus.solving

class ParallelNodeSolvedReason(PartitionNodeSolvedReason):
    partitioner = 10
    split = 11

class ParallelNode(PartitionNode):
    status: ParallelNodeStatus
    reason: ParallelNodeSolvedReason
    unsat_percentage = 0.0
    
    def __init__(self, id, parent, make_time):
        super().__init__(id, parent, make_time)
        ### TBD ###
    
    def can_reason_unsat(self):
        if len(self.children) == 0:
            return False
        for child in self.children:
            child: ParallelNode
            if not child.status.is_unsat():
                return False
        return True
    
    def update_unsat_percentage(self):
        self.unsat_percentage = 0.0
        for child in self.children:
            child: ParallelNode
            self.unsat_percentage += child.unsat_percentage
        self.unsat_percentage /= 2.0

class ParallelTree(PartitionTree):
    solvings = []
    waitings = queue.Queue()
    
    def __init__(self, start_time):
        super().__init__(start_time)
    
    def get_next_waiting_node(self):
        while not self.waitings.empty():
            node: ParallelNode = self.waitings.get()
            if node.status.is_unsolved():
                return node
        return None
    
    def set_node_split(self, node: ParallelNode, assigned_coord: int):
        if node.assign_to != None:
            node.assign_to.terminate()
        node.assign_to = assigned_coord
        self.node_solved_unsat(node, ParallelNodeSolvedReason.split)
    
    def select_split_node(self):
        current: ParallelNode = self.root
        while True:
            if len(current.children) == 0:
                break
            assert(len(current.children) == 2)
            lc: ParallelNode = current.children[0]
            rc: ParallelNode = current.children[1]
            assert((not lc.status.is_unsat()) or (not rc.status.is_unsat()))
            if lc.status.is_unsat():
                current = rc
            elif rc.status.is_unsat():
                current = lc
            else:
                return rc
        return None
    
    def propagate_node_unsat(self,
            node: ParallelNode,
            reason: ParallelNodeSolvedReason):
        self.update_node_status(node, 
                                ParallelNodeStatus.unsat, 
                                reason)
        # self.write_line_to_partitioner(f'unsat-node {t.id}')
        if node.assign_to != None:
            node.assign_to.terminate()
            node.assign_to = None
    
    def unsat_push_up(self, node: ParallelNode):
        if node.status.is_unsat():
            return
        if node.can_reason_unsat():
            self.propagate_node_unsat(node, ParallelNodeSolvedReason.children)
            if node.parent != None:
                self.unsat_push_up(node.parent)
    
    def unsat_push_down(self, node: ParallelNode):
        if node.status.is_unsat():
            return
        self.propagate_node_unsat(node, ParallelNodeSolvedReason.ancester)
        for child in node.children:
            self.unsat_push_down(child)
    
    def node_solved_unsat(self,
            node: ParallelNode,
            reason: ParallelNodeSolvedReason):
        self.update_node_status(node,
                ParallelNodeStatus.unsat,
                reason)
        # self.write_line_to_partitioner(f'unsat-node {t.id}')
        if node.parent != None:
            self.unsat_push_up(node.parent)
        if self.root.status.is_unsat():
            self.result = ParallelNodeStatus.unsat
            return
        for child in node.children:
            self.unsat_push_down(child)
    
    def node_solved_sat(self,
            node: ParallelNode,
            reason: ParallelNodeSolvedReason):
        self.update_node_status(node,
                ParallelNodeStatus.sat,
                reason)
        self.result = ParallelNodeStatus.sat
    
    def node_solved(self, 
            node: ParallelNode,
            status: ParallelNodeStatus,
            reason: ParallelNodeSolvedReason = ParallelNodeSolvedReason.itself):
        if status.is_sat():
            self.node_solved_sat(node, reason)
        elif status.is_unsat():
            self.node_solved_unsat(node, reason)
        else:
            assert(False)
    
    def assign_node(self, node: ParallelNode, p: subprocess.Popen):
        assert(node.assign_to == None)
        node.assign_to = p
        node.update_status(ParallelNodeStatus.solving,
                           ParallelNodeSolvedReason.itself,
                           self.get_current_time())
    
class DistributedNodeStatus(PartitionNodeStatus):
    pass

class DistributedNodeSolvedReason(PartitionNodeSolvedReason):
    # by
    original = 10

class DistributedNode(PartitionNode):
    partial_status = DistributedNodeStatus.unsolved
    def __init__(self, id, parent, make_time):
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
    
    def unsat_push_up(self, node: DistributedNode):
        assert(not node.status.is_unsat())
        if node.can_reason_unsat():
            self.update_node_status(node, 
                DistributedNodeStatus.unsat, 
                DistributedNodeSolvedReason.itself)
            if node.parent != None:
                self.unsat_push_up(node.parent)
    
    def node_partial_solved_unsat(self,
            node: DistributedNode):
        node.update_partial_status(DistributedNodeStatus.unsat)
        self.unsat_push_up(node)
        if self.root.status.is_unsat():
            self.result = DistributedNodeStatus.unsat
            return
    
    def node_partial_solved_sat(self,
            node: DistributedNode):
        node.update_partial_status(DistributedNodeStatus.sat)
        self.result = DistributedNodeStatus.sat
    
    def node_partial_solved(self, 
            node: DistributedNode,
            status: DistributedNodeStatus):
        if status.is_sat():
            self.node_partial_solved_sat(node)
        elif status.is_unsat():
            self.node_partial_solved_unsat(node)
        else:
            assert(False)
    
    # split node from {parent} to {coord_id}
    def split_node_from(self, parent: DistributedNode, coord_id: int):
        ret = self.make_node(parent)
        parent.children.append(ret)
        ret.assign_to = coord_id
        return ret
    
    
