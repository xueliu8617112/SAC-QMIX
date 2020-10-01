import torch
import torch.nn as nn
import torch.nn.functional as F
from .mrnn_agent import RNNAgent
from .msg_hub import MessageHub



class MQAgent3(nn.Module):
    def __init__(self, args):
        super(MQAgent3, self).__init__()
        
        self.n_agents = args.n_agents
        self.msg_dim = args.msg_dim
        self.agent = RNNAgent(args)
        self.msg_hub = MessageHub(args)

    def init_hiddens(self, n_batch):
        hiddens = [self.agent.init_hidden(n_batch) for i in range(self.n_agents)]
        hiddens = torch.stack(hiddens,1)
        return hiddens

    def forward(self, states, actions_explore, actions_last, hiddens):
        
        
        n_batch = len(states)
        m_zero = states.new_zeros(n_batch, self.msg_dim)
        a_zero = torch.zeros_like(actions_explore[:,0])
        agent_ids = torch.arange(0,self.n_agents,dtype=torch.int64, device=states.device)        
        agent_ids = F.one_hot(agent_ids, self.n_agents).to(dtype=torch.float32)
        agent_ids = torch.stack([agent_ids]*n_batch, 0)

        qs = []
        hs_next = []
        ms_send = []

        for i in range(self.n_agents):
            ms_send.append(self.agent.forward(states[:,i], agent_ids[:,i],actions_explore[:,i],m_zero,actions_last[:,i] , hiddens[:,i])[1])        
        ms_send = torch.stack(ms_send,1)
        ms_recv = self.msg_hub.forward(ms_send)
        ms_recv = ms_recv.clone()
        for i in range(self.n_agents):
            if torch.nonzero(actions_explore[:,i]).shape[0]:   #explore agent            
                ms_send_i = ms_send.clone()
                ms_send_i[:,i] = self.agent.forward(states[:,i], agent_ids[:,i],a_zero,m_zero,actions_last[:,i] , hiddens[:,i])[1]
                ms_recv[:,i] = self.msg_hub.forward(ms_send_i)[:,i]

        for i in range(self.n_agents):            
            q,_,h_next = self.agent.forward(states[:,i], agent_ids[:,i],a_zero, ms_recv[:,i], actions_last[:,i] , hiddens[:,i])
            qs.append(q)
            hs_next.append(h_next)
        
        qs = torch.stack(qs,1)
        hs_next = torch.stack(hs_next,1)
        return qs, hs_next