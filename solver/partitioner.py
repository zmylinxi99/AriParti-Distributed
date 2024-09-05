import select
import subprocess
from enum import Enum
from enum import auto
from control_message import ControlMessage

class PartitionerStatus(Enum):
    running = auto()
    wait_result = auto()
    sat = auto()
    unsat = auto()
    unknown = auto()
    error = auto()
    
    def is_running(self):
        return self == PartitionerStatus.running
    
    def is_wait_result(self):
        return self == PartitionerStatus.wait_result
    
    def is_sat(self):
        return self == PartitionerStatus.sat
    
    def is_unsat(self):
        return self == PartitionerStatus.unsat
    
    def is_unknown(self):
        return self == PartitionerStatus.unknown
    
    def is_done(self):
        return self.is_sat() or self.is_unsat() or self.is_unknown()

class Partitioner:
    def __init__(self, p: subprocess.Popen):
        self.status = PartitionerStatus.running
        self.p: subprocess.Popen = p
    
    def is_running(self):
        if not self.status.is_running():
            return False
        rc = self.p.poll()
        if rc == None:
            return True
        assert(rc == 0)
        self.status = PartitionerStatus.wait_result
        return False
    
    def send_message(self, msg: str):
        if not self.is_running():
            return
        self.p.stdin.write(msg + '\n')
        self.p.stdin.flush()
    
    def receive_message(self):
        ready, _, _ = select.select([self.p.stdout], [], [], 0.05)
        if ready:
            return self.p.stdout.readline()
        return None
    
    def is_running(self):
        return self.status.is_running()
    
    def set_status(self, result: str):
        if result == 'sat':
            self.status = PartitionerStatus.sat
        elif result == 'unsat':
            self.status = PartitionerStatus.unsat
        elif result == 'unknown':
            self.status = PartitionerStatus.unknown
        else:
            assert(False)