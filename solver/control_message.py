from enum import Enum
from enum import auto

class ControlMessage:
    
    # Leader To Coordinator
    class L2C(Enum):
        
        # assign a node from coordinator {rank} to [current]
        assign_node = auto()
        # request split a subnode to coordinator {rank}
        request_split = auto()
        # terminate coordinator {rank}
        terminate_coordinator = auto()
        
        def is_assign_node(self):
            return self == ControlMessage.L2C.assign_node
        
        def is_request_split(self):
            return self == ControlMessage.L2C.request_split
        
        def is_terminate_coordinator(self):
            return self == ControlMessage.L2C.terminate_coordinator
    
        # # solve leader-0
        # initiate_leader_0 = auto()
        # def is_initiate_leader_0(self):
        #     return self == ControlMessage.L2C.initiate_leader_0
    
    # Coordinator To Leader
    class C2L(Enum):
        # split node to coordinator [src]
        split_succeed = auto()
        # split failed
        split_failed = auto()
        # coordinator [src] solved the assigned node
        notify_result = auto()
        
        def is_split_succeed(self):
            return self == ControlMessage.C2L.split_succeed
        
        def is_split_failed(self):
            return self == ControlMessage.C2L.split_failed
        
        def is_notify_result(self):
            return self == ControlMessage.C2L.notify_result
    
    # Coordinator To Coordinator
    class C2C(Enum):
        # send subnode file
        send_subnode = auto()
        
        def is_send_subnode(self):
            return self == ControlMessage.C2C.send_subnode
        
    # Coordinator To Partitioner
    class C2P(Enum):
        unsat_node = 0
        terminate_node = 1
        
        def is_unsat_node(self):
            return self == ControlMessage.C2P.unsat_node
        
        def is_terminate_node(self):
            return self == ControlMessage.C2P.terminate_node
    
    # Partitioner To Coordinator
    class P2C(Enum):
        debug_info = 0
        new_unknown_node = 1
        new_unsat_node = 2
        sat = 3
        unsat = 4
        unknown = 5
        
        def is_debug_info(self):
            return self == ControlMessage.P2C.debug_info
        
        def is_new_unknown_node(self):
            return self == ControlMessage.P2C.new_unknown_node
        
        def is_new_unsat_node(self):
            return self == ControlMessage.P2C.new_unsat_node
        
        def is_sat(self):
            return self == ControlMessage.P2C.sat
        
        def is_unsat(self):
            return self == ControlMessage.P2C.unsat
        
        def is_unknown(self):
            return self == ControlMessage.P2C.unknown
        
        def is_new_node(self):
            return self.is_new_unknown_node() or self.is_new_unsat_node()
        
        def is_solved_result(self):
            return self.is_sat() or self.is_unsat() or self.is_unknown()
    
        