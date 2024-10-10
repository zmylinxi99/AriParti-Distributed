import select
import logging
import subprocess
from enum import Enum, auto


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
        return self.status.is_running()
    
    def is_done(self):
        return self.status.is_done()
    
    # True for p finished
    def check_p_status(self):
        if not self.is_running():
            return False
        rc = self.p.poll()
        if rc == None:
            return False
        if rc != 0:
            out_data, err_data = self.p.communicate()
            logging.error(f'Partitioner Crashed! return code: {rc}')
            logging.error(f'output: {out_data}')
            logging.error(f'error: {err_data}')
            assert(False)
        self.status = PartitionerStatus.wait_result
        return True
    
    def send_message(self, msg: str):
        if not self.is_running():
            return
        self.p.stdin.write(msg + '\n')
        self.p.stdin.flush()
    
    def receive_message(self):
        ready, _, _ = select.select([self.p.stdout], [], [], 0.01)
        if ready:
            return self.p.stdout.readline()
        return None
    
    def set_status(self, result: str):
        if result == 'sat':
            self.status = PartitionerStatus.sat
        elif result == 'unsat':
            self.status = PartitionerStatus.unsat
        elif result == 'unknown':
            self.status = PartitionerStatus.unknown
        else:
            assert(False)