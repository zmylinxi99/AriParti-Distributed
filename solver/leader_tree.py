
import time
from enum import Enum

class PartitionNodeStatus(Enum):
    unsolved = 0
    unsat_by_itself   = 1
    unsat_by_ancester = 2
    unsat_by_children = 3
    sat = 4
    error = 5
    
    def is_unsat(self):
        return self in [PartitionNodeStatus.unsat_by_itself, 
                        PartitionNodeStatus.unsat_by_ancester, 
                        PartitionNodeStatus.unsat_by_children]

class PartitionNode:
    def update_status(self, status, current_time):
        self.time_infos[status] = current_time
        self.status = status
    
    def __init__(self, id, parent, make_time):
        self.assign_to = None
        self.time_infos = {}
        self.children = []
        self.status: PartitionNodeStatus
        
        self.id = id
        self.parent = parent
        self.update_status(PartitionNodeStatus.unsolved, make_time)

    def can_reason_unsat(self):
        if len(self.children) == 0:
            return False
        for child in self.children:
            child: PartitionNode
            if not child.status.is_unsat():
                return False
        return True
    
    def __repr__(self) -> str:
        pid = -1
        if (self.parent != None):
            pid = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {pid}'
        ret += f', status: {self.status}'
        if len(self.children) > 0:
            stid = [child.id for child in self.children]
            ret += f', subtasks: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret

class PartitionTree:
    
    def __init__(self, start_time):
        self.node_status_dict = {
            # 'waiting': [],
            # 'solving': [],
            # 'ended': [],
        }
        
        self.proxy_functions = []
        
        self.start_time = start_time
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def update_node_status(self, node: PartitionNode, status):
        current_time = self.get_current_time()
        node.update_status(status, current_time)
        if status == PartitionNodeStatus.unsat:
            for func in self.proxy_functions:
                func()
        if status > PartitionNodeStatus.ended:
            status = PartitionNodeStatus.ended
            
    def unsat_push_up(self, t):
        if t == None:
            return
        assert(isinstance(t, PartitionNode))
        if t.status.is_unsat():
            return
        if t.can_reason_unsat():
            self.update_node_status(t, PartitionNodeStatus.unsat_by_children)
            self.unsat_push_up(t.parent)
    
    def unsat_push_down(self, t: PartitionNode):
        if t.status.is_unsat():
            return
        self.update_node_status(t, PartitionNodeStatus.unsat_by_ancester)
        for child in t.children:
            self.unsat_push_down(child)

# ParallelNodeStatus
# waiting solving sat unsat unknown
# waiting -> solving BY (run task)
#         -> unsat   BY (ancester, children, partitioner)
#         -> unknown BY (children)
# solving -> sat BY (solver)
#         -> unsat BY (solver, ancester, children, partitioner)
#         -> unknown BY (solver, children)
class ParallelNodeStatus(PartitionNodeStatus):
    # unsolved = 0
    # unsat_by_itself   = 1
    # unsat_by_ancester = 2
    # unsat_by_children = 3
    # sat = 4
    # error = 5
    
    # unended
    unended = 0
    
    waiting = 10
    solving = 11
    terminated = 12
    # ended
    ended = 10

    unsat             = 11 # by itself
    unsat_by_ancester = 12
    unsat_by_children = 13
    
    sat = 21
    
    # unknown     = 31
    terminated  = 32
    error       = 33
    
class ParallelNode:
    def update_status(self, status, current_time):
        self.time_infos[status] = current_time
        self.status = status
    
    def __init__(self, id, parent, make_time):
        self.assign_to = None
        self.time_infos = {}
        self.children = []
        self.status: PartitionNodeStatus
        
        self.id = id
        self.parent = parent
        self.update_status(PartitionNodeStatus.waiting, make_time)

    def can_reason_unsat(self):
        if len(self.children) == 0:
            return False
        for child in self.children:
            child: PartitionNode
            if not child.status.is_unsat():
                return False
        return True
    
    def __repr__(self) -> str:
        pid = -1
        if (self.parent != None):
            pid = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {pid}'
        ret += f', status: {self.status}'
        if len(self.children) > 0:
            stid = [child.id for child in self.children]
            ret += f', subtasks: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret

class ParallelTree:
    
    def __init__(self, start_time):
        self.node_status_dict = {
            # 'waiting': [],
            # 'solving': [],
            # 'ended': [],
        }
        
        self.proxy_functions = []
        
        self.start_time = start_time
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def update_node_status(self, node: PartitionNode, status):
        current_time = self.get_current_time()
        node.update_status(status, current_time)
        if status == PartitionNodeStatus.unsat:
            for func in self.proxy_functions:
                func()
        if status > PartitionNodeStatus.ended:
            status = PartitionNodeStatus.ended
            
    def unsat_push_up(self, t):
        if t == None:
            return
        assert(isinstance(t, PartitionNode))
        if t.status.is_unsat():
            return
        if t.can_reason_unsat():
            self.update_node_status(t, PartitionNodeStatus.unsat_by_children)
            self.unsat_push_up(t.parent)
    
    def unsat_push_down(self, t: PartitionNode):
        if t.status.is_unsat():
            return
        self.update_node_status(t, PartitionNodeStatus.unsat_by_ancester)
        for child in t.children:
            self.unsat_push_down(child)
    