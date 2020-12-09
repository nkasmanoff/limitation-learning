import torch
import torch.nn as nn

from models.seq2seq import Seq2Seq


class Actor(nn.Module):
    """
    Direct application of Sequence to Sequence Network. Input a state and reply. 
    
    """
    def __init__(self,  hidden_size, num_layers,
                 device='cuda', drop_prob=0, lstm=True, feature_norm=False,
                 input_size=300):
        super().__init__()
        self.seq2seq = Seq2Seq(hidden_size=hidden_size,num_layers=num_layers,device=device, drop_prob=drop_prob, lstm=lstm, feature_norm=feature_norm,
                          input_size = input_size)
    
    def forward(self,x):
        
        mu = self.seq2seq(x)
        logstd = torch.zeros_like(mu)
        std = torch.exp(logstd)
        return mu, .01*std # Kinda guessed. 

        #unit norm, 