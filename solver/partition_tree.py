
import time
from enum import Enum



class PartitionNodeStatus(Enum):
    # unsolved = 0
    # unsat_by_itself   = 1
    # unsat_by_ancester = 2
    # unsat_by_children = 3
    # sat = 4
    # error = 5
    
    unsolved = 0
    sat = 1
    unsat = 2
    error = 3
    
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
    def __init__(self, id, parent, make_time):
        self.assign_to = None
        self.time_infos = {}
        self.children = []
        self.status: PartitionNodeStatus
        self.reason: PartitionNodeSolvedReason
        self.id = id
        self.parent = parent
        self.update_status(PartitionNodeStatus.unsolved, 
                           PartitionNodeSolvedReason.itself, 
                           make_time)

    def update_status(self, status, reason, current_time):
        self.time_infos[status] = current_time
        self.status = status
        self.reason = reason
    
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
            ret += f', children: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret

class PartitionTree:
    def __init__(self, start_time):
        # self.node_status_dict = {
        #     # 'waiting': [],
        #     # 'solving': [],
        #     # 'ended': [],
        # }
        # self.proxy_functions = []
        
        self.nodes = []
        
        self.start_time = start_time
        self.root = self.make_node(None)
        
    def get_current_time(self):
        return time.time() - self.start_time
    
    def make_node(self, parent):
        id = len(self.nodes)
        node = PartitionNode(id, parent, self.get_current_time())
        self.nodes.append(node)
        return node
    
    def is_done(self):
        return self.root.status.is_solved()
    
    def get_result(self):
        return self.root.status
    
    def update_node_status(self, node: PartitionNode, status, reason):
        current_time = self.get_current_time()
        node.update_status(status, reason, current_time)
        # if status == PartitionNodeStatus.unsat:
        #     for func in self.proxy_functions:
        #         func()
        # if status > PartitionNodeStatus.ended:
        #     status = PartitionNodeStatus.ended
            
    def unsat_push_up(self, node):
        if node == None:
            return
        assert(isinstance(node, PartitionNode))
        if node.status.is_unsat():
            return
        if node.can_reason_unsat():
            self.update_node_status(node, 
                                    PartitionNodeStatus.unsat, 
                                    PartitionNodeSolvedReason.children)
            self.unsat_push_up(node.parent)
    
    def unsat_push_down(self, node: PartitionNode):
        if node.status.is_unsat():
            return
        self.update_node_status(node, 
                                PartitionNodeStatus.unsat,
                                PartitionNodeSolvedReason.ancester)
        for child in node.children:
            self.unsat_push_down(child)
    
    def node_solved(self, node: PartitionNode, status: PartitionNodeStatus):
        self.update_node_status(node, status)
        if status.is_sat():
            if node != self.root:
                self.update_node_status(self.root, 
                                        PartitionNodeStatus.sat, 
                                        PartitionNodeSolvedReason.children)
        elif status.is_unsat():
            self.unsat_push_up(node.parent)
            if self.is_done():
                return
            for child in node.children:
                self.unsat_push_down(child)
        else:
            assert(False)
    
    def node_id_solved(self, node_id: int, status: PartitionNodeStatus):
        self.node_solved(self.nodes[node_id], status)

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
    
    # unsolved means waiting
    solving = 10
    terminated = 11

class ParallelNode(PartitionNode):
    def __init__(self, id, parent, make_time):
        super().__init__(id, parent, make_time)
        ### TBD ###
    
    def __repr__(self) -> str:
        ret = super().__repr__()
        ### TBD ###
        return ret


class ParallelTree(PartitionTree):
    def __init__(self, start_time):
        super().__init__(start_time)
        # self.node_status_dict = {
        #     PartitionNodeStatus.unsolved: [],
        #     PartitionNodeStatus.unsolved: [],
        #     PartitionNodeStatus.unsolved: [],
        #     PartitionNodeStatus.unsolved: [],
        #     unsat_by_itself   = 1
        #     unsat_by_ancester = 2
        #     unsat_by_children = 3
        #     sat = 4
        #     error = 5
        #     # 'waiting': [],
        #     # 'solving': [],
        #     # 'ended': [],
        # }
    
    
class DistributedNodeStatus(PartitionNodeStatus):
    pass

class DistributedNodeSolvedReason(Enum):
    # by
    original = 10

class DistributedNode(PartitionNode):
    pass

class DistributedTree(PartitionTree):
    
    pass
    
    
