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
        # split node with relative {path} to coordinator [src]
        send_path = auto()
        # coordinator [src] solved the assigned node
        notify_result = auto()
        
        def is_send_path(self):
            return self == ControlMessage.C2L.send_path
        
        def is_notify_result(self):
            return self == ControlMessage.C2L.notify_result
    
    # Coordinator To Coordinator
    class C2C(Enum):
        # send subnode file
        send_subnode = auto()
        
        def is_send_subnode(self):
            return self == ControlMessage.C2C.send_subnode
    