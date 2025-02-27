import os
import fcntl
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
        self.status = PartitionerStatus.running
        self.result = PartitionerResult.unsolved
        self.partial_line = ''
        self.buffer = None
        
        self.p: subprocess.Popen = p
        
        flags = fcntl.fcntl(self.p.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    
    def is_running(self):
        return self.status.is_running()
    
    def is_process_done(self):
        return self.status.is_process_done()
    
    def is_receive_done(self):
        return self.status.is_receive_done()
    
    def check_running(self):
        if not self.is_running():
            return False
        self.check_p_status()
        return self.is_running()
    
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
    
    def read_from_process(self):
        ready, _, _ = select.select([self.p.stdout], [], [], 0.1)
        if ready:
            data = self.p.stdout.read()
            # logging.debug(f'data {data}')
            if data == '' and not self.check_running():
                self.status = PartitionerStatus.receive_done
                return False
            self.buffer = data
            self.buffer_head = 0
            self.buffer_tail = len(self.buffer)
            return True
        return False
    
    def receive_message(self):
        if self.buffer is None:
            if not self.read_from_process():
                # None or partial line
                if not self.status.is_receive_done():
                    return None
                else:
                    return self.partial_line
        
        next_eol = self.buffer.find('\n', self.buffer_head)
        if next_eol != -1:
            ret = self.partial_line + self.buffer[self.buffer_head: next_eol]
            self.buffer_head = next_eol + 1
            self.partial_line = ''
            return ret
        else:
            self.partial_line += self.buffer[self.buffer_head: ]
            self.buffer = None
            return None
    