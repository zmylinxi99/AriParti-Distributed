import select
import subprocess
from enum import Enum
from control_message import ControlMessage

class PartitionerStatus(Enum):
    running = 0
    sat = 1
    unsat = 2
    unknown = 3
    error = 4
    
    def is_running(self):
        return self == PartitionerStatus.running
    
    def is_sat(self):
        return self == PartitionerStatus.sat
    
    def is_unsat(self):
        return self == PartitionerStatus.unsat
    
    def is_unknown(self):
        return self == PartitionerStatus.unknown

class Partitioner:
    def __init__(self, p: subprocess.Popen):
        self.p: subprocess.Popen = p
        self.status = PartitionerStatus.running
        
    def send_message(self, msg: str):
        self.p.stdin.write(msg + '\n')
        self.p.stdin.flush()
    
    def receive_message(self):
        ready, _, _ = select.select([self.p.stdout], [], [], 0.05)
        if ready:
            return self.p.stdout.readline()
        return None
    
    def is_running(self):
        return self.status.is_running()
    
    def set_status(self, result: ControlMessage.P2C):
        if result.is_sat():
            self.status = PartitionerStatus.sat
        elif result.is_unsat():
            self.status = PartitionerStatus.unsat
        elif result.is_unknown():
            self.status = PartitionerStatus.unknown
        else:
            assert(False)