
from enum import Enum

class TaskStatus(Enum):
    waiting = 1
    solving = 2
    unknown = 10
    sat = 11
    unsat = 12

# Task maintained by the Leader and Coordinator
class Task():
    def __init__(self, p, id, parent, make_time):
        self.p = p
        self.id = id
        self.parent = parent
        self.time_infos = {'make': make_time}
        # waiting solving sat unsat unknown
        # waiting -> solving BY (run task)
        #         -> unsat   BY (ancester, children, partitioner)
        #         -> unknown BY (children)
        # solving -> sat BY (solver)
        #         -> unsat BY (solver, ancester, children, partitioner)
        #         -> unknown BY (solver, children)
        self.status = TaskStatus.waiting
        self.reason = -3
        self.subtasks = []
        
    def __str__(self) -> str:
        pid = -1
        if (self.parent != None):
            pid = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {pid}'
        ret += f', status: {self.status}'
        if self.reason != -3:
            ret += f', reason: {self.reason}'
        if len(self.subtasks) > 0:
            stid = [self.subtasks[0].id, self.subtasks[1].id]
            ret += f', subtasks: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret
