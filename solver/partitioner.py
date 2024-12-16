import select
import logging
import subprocess
from enum import Enum, auto

class PartitionerResult(Enum):
    unsolved = auto()
    sat = auto()
    unsat = auto()
    unknown = auto()
    
    def is_unsolved(self):
        return self == PartitionerResult.unsolved
    
    def is_sat(self):
        return self == PartitionerResult.sat
    
    def is_unsat(self):
        return self == PartitionerResult.unsat
    
    def is_unknown(self):
        return self == PartitionerResult.unknown

class PartitionerStatus(Enum):
    running = auto()
    process_done = auto()
    receive_done = auto()
    # error = auto()
    
    def is_running(self):
        return self == PartitionerStatus.running
    
    def is_process_done(self):
        return self == PartitionerStatus.process_done
    
    def is_receive_done(self):
        return self == PartitionerStatus.receive_done
    
    # def is_error(self):
    #     return self == PartitionerStatus.error
    
class Partitioner:
    def __init__(self, p: subprocess.Popen):
        self.p: subprocess.Popen = p
        self.status = PartitionerStatus.running
        self.result = PartitionerResult.unsolved
    
    def is_running(self):
        if not self.status.is_running():
            return False
        self.check_p_status()
        return self.status.is_running()
    
    def is_process_done(self):
        return self.status.is_process_done()
    
    def is_receive_done(self):
        return self.status.is_receive_done()
    
    def set_result(self, result: str):
        if result == 'sat':
            self.result = PartitionerResult.sat
        elif result == 'unsat':
            self.result = PartitionerResult.unsat
        elif result == 'unknown':
            self.result = PartitionerResult.unknown
        else:
            assert(False)
    
    # True for p finished
    def check_p_status(self):
        if not self.is_running():
            return
        rc = self.p.poll()
        if rc == None:
            return
        logging.info(f'Partitioner is finished! return code: {rc}')
        if rc != 0:
            out_data, err_data = self.p.communicate()
            logging.error(f'Partitioner Crashed! return code: {rc}')
            logging.error(f'output: {out_data}')
            logging.error(f'error: {err_data}')
            assert(False)
        self.status = PartitionerStatus.process_done
        return
    
    def send_message(self, msg: str):
        self.p.stdin.write(msg + '\n')
        self.p.stdin.flush()
    
    def receive_message(self):
        ready, _, _ = select.select([self.p.stdout], [], [], 0.01)
        if ready:
            line: str = self.p.stdout.readline()
            if self.status.is_process_done() and line == '':
                logging.debug(f'partitioner receive_done')
                self.status = PartitionerStatus.receive_done
                return self.p.stdout.read()
            line = line.strip(' \n')
            # logging.debug(f'line: {line}')
            return line
        return None
