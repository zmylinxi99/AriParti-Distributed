
import time
import queue
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

    # def _update_status(self, status, reason, current_time):
    def update_status(self, status, reason, current_time):
        self.time_infos[status] = current_time
        self.status = status
        self.reason = reason
    
    # def set_unsat(self, reason, current_time):
    #     self._update_status(PartitionNodeStatus.unsat,
    #                        reason, current_time)
    
    # def set_sat(self, reason, current_time):
    #     self._update_status(PartitionNodeStatus.sat,
    #                        reason, current_time)
    
    def can_reason_unsat(self):
        if len(self.children) == 0:
            return False
        for child in self.children:
            child: PartitionNode
            if not child.status.is_unsat():
                return False
        return True
    
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
    nodes = []
    def __init__(self, start_time):
        # self.node_status_dict = {
        #     # 'waiting': [],
        #     # 'solving': [],
        #     # 'ended': [],
        # }
        # self.proxy_functions = []
        
        self.start_time = start_time
        self.root: ParallelNode = self.make_node(None)
        
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
    
    def update_node_status(self, node: PartitionNode,
                           status: PartitionNodeStatus,
                           reason: PartitionNodeSolvedReason):
        current_time = self.get_current_time()
        
        node.update_status(status, reason, current_time)
        # if status == PartitionNodeStatus.unsat:
        #     for func in self.proxy_functions:
        #         func()
        # if status > PartitionNodeStatus.ended:
        #     status = PartitionNodeStatus.ended
            
    def unsat_push_up(self, node: PartitionNode):
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
    
    def node_solved(self, 
            node: PartitionNode, status: PartitionNodeStatus,
            reason: PartitionNodeSolvedReason = PartitionNodeSolvedReason.itself):
        self.update_node_status(node, status, reason)
        if status.is_sat():
            if node != self.root:
                self.update_node_status(self.root, 
                                        PartitionNodeStatus.sat, 
                                        PartitionNodeSolvedReason.children)
        elif status.is_unsat():
            if node.parent != None:
                self.unsat_push_up(node.parent)
            self.unsat_push_up(node.parent)
            if self.is_done():
                return
            for child in node.children:
                self.unsat_push_down(child)
            ### TBD ###
            # if node.parent != None and \
            #    not node.parent.status.is_unsat():
            #     self.unsat_push_up(node.parent)
            # if self.is_done():
            #     return
            # for child in node.children:
            #     if not child.status.is_unsat():
            #         self.unsat_push_down(child)
        else:
            assert(False)
    
    # ### TBD ### ParallelNodeStatus
    # def node_id_solved(self, node_id: int, status: PartitionNodeStatus):
    #     self.node_solved(self.nodes[node_id], status)

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

class ParallelNode(PartitionNode):
    status: ParallelNodeStatus
    reason: ParallelNodeSolvedReason
    unsat_percentage = 0.0
    
    def __init__(self, id, parent, make_time):
        super().__init__(id, parent, make_time)
        ### TBD ###
    
    def update_unsat_percentage(self):
        self.unsat_percentage = 0.0
        for child in self.children:
            child: ParallelNode
            self.unsat_percentage += child.unsat_percentage


class ParallelTree(PartitionTree):
    solvings = []
    waitings = queue.Queue()
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
    
    def get_next_waiting_node(self):
        while not self.waitings.empty():
            node: ParallelNode = self.waitings.get()
            if node.status.is_unsolved():
                return node
        return None
    
    def set_node_split(self, node):
        pass
        
    def select_split_node(self):
        pass
    
    # if sta.is_sat():
    #     self.result = ParallelNodeStatus.sat
    #     # self.reason = t.id
    #     self.write_line_to_log(f'sat-task {node.id}')
    #     return False
    # elif sta.is_unsat():
    #     self.write_line_to_partitioner(f'unsat-node {node.id}')
    #     self.tree.unsat_push_down()
    #     if t.parent != None:
    #         self.push_up(t.parent, t.id)
    #     root_task: Task = self.tasks[0]
    #     if root_task.status == 'unsat':
    #         self.result = ParallelNodeStatus.unsat
    #         self.reason = root_task.reason
    #         self.write_line_to_log(f'unsat-root-task {root_task.reason}')
    #         return False
    #     for st in t.subtasks:
    #         self.push_down(st, t.id)
    # else:
    #     assert(False)
    # return False
    
    def solve_node(self, node: ParallelNode, p):
        assert(node.assign_to == None)
        node.assign_to = p
        node.update_status(ParallelNodeStatus.solving,
                           ParallelNodeSolvedReason.itself,
                           self.get_current_time())
        pass
    
    def node_solved(self, 
            node: ParallelNode, status: ParallelNodeStatus,
            reason: ParallelNodeSolvedReason = ParallelNodeSolvedReason.itself):
        super().node_solved()
        
    
    def get_path(self, node: ParallelNode):
        ret = []
        current = node
        while True:
            if current.parent == None:
                break
            assert(isinstance(current.parent, ParallelNode))
            ret.append(current.parent.children.index(current))            
            current = current.parent
        ret.reverse()
        return ret
    
    # def make_task(self, id, pid, is_unsat):
    #     parent: Task = None
    #     if (pid != -1):
    #         parent = self.id2task[pid]
    #     t = Task(None, id, parent, self.get_current_time())
        
    #     if is_unsat:
    #         self.update_task_status(t, 'unsat')
    #         t.reason = -1
    #         if parent != None:
    #             self.push_up(parent, t.id)
    #     else:
    #         self.update_task_status(t, 'waiting')
        
    #     if parent != None:
    #         if t.status != 'unsat' and parent.status == 'unsat':
    #             self.propagate_unsat(t, parent.reason)
    #         parent.subtasks.append(t)
        
    #     # self.write_line_to_log(f'make-task {t}')
        
    #     self.id2task[id] = t
    #     self.tasks.append(t)
    #     ### TBD ###
    #     pass
        
    
class DistributedNodeStatus(PartitionNodeStatus):
    pass

class DistributedNodeSolvedReason(Enum):
    # by
    original = 10

class DistributedNode(PartitionNode):
    dependency_children = []
    dependency_parent = None
    def __init__(self, id, parent, make_time):
        super().__init__(id, parent, make_time)
        ### TBD ###
    
    def update_status(self, status, reason, current_time):
        super().update_status(status, reason, current_time)
        ### TBD ###

class DistributedTree(PartitionTree):
    def __init__(self, start_time):
        super().__init__(start_time)
    
    def assign_node(self, node: DistributedNode, coordinator_id: int):
        node.assign_to = coordinator_id
    
    def select_split_node(self):
        ### TBD ###
        pass
    
    def update_with_path(self, relative_root: DistributedNode, path: list, coordinator_id: int):
        current = relative_root
        for index in path:
            if len(current.children) == 0:
                current.children.append(self.make_node(current))
                current.children.append(self.make_node(current))
            current = current.children[index]
            
        self.assign_node(current, coordinator_id)
        return current
    
