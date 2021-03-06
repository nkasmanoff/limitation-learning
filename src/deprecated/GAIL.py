"""
Main and helper functions used for running Generative Adversarial Imitation Learning


"""

from collections import deque
import torch
import numpy as np

import sys
#sys.path.append('../src')
from models import *
import torch.optim as optim
import math
import torch
from torch.distributions import Normal

import gensim

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


#model = gensim.models.KeyedVectors.load_word2vec_format("/scratch/nsk367/limitation-learning/apps/dat/preprocess/GoogleNews-vectors-negative300.bin.gz", binary=True)
#model = gensim.models.Word2Vec.load("/scratch/nsk367/deepRL/limitation-learning/apps/dat/preprocess/custom_w2v")
model = gensim.models.Word2Vec.load("../models/custom_w2v_intersect_GoogleNews")
model.init_sims(replace=True) #precomputed l2 normed vectors in-place – saving the extra RAM

def get_action(mu, std):
    """
    L2 norm is equal to 1 across the embedding dimension for all tokens.
    """
    action = torch.normal(mu, std)
    

    action = action.detach().cpu().numpy()

    return action


def get_raw_action(action, 
                   type = 'greedy',
                   metric = 'cosine',
                   cutoff = None,
                   N_vocab = None):

    raw_action = []

    if metric != 'cosine':
        raise NotImplementedError

    if type == 'average':
        raise NotImplementedError

    elif type == 'greedy':
        
        for token_vector in action:

            if isinstance(token_vector, torch.Tensor):
                token_vector = token_vector.cpu().numpy()

            # https://tedboy.github.io/nlps/_modules/gensim/models/word2vec.html#Word2Vec.similar_by_vector
            # computes cosine similarity between a simple mean of the projection
            # weight vectors of the given words and the vectors for each word in the model
            # the vocab should be pre-sorted,  model.vocabulary.sorted_vocab should be True
            sims = model.similar_by_vector(token_vector, topn=1, restrict_vocab=N_vocab)
            
            raw_token = sims[0][0]
            sim_score = sims[0][1]
            if (cutoff and (sim_score < cutoff)):
                continue
            
            raw_action.append(raw_token.replace('_',' '))

    return ' '.join(raw_action)

def get_cosine_sim(expert, action,
                   type = None,
                   seq_len = 5,
                   dim = 300):

    if type == 'greedy':
        action = [model.wv[tok] for tok in get_raw_action(action).split(' ')]

    expertV = np.zeros((dim, ), dtype='float32')
    actionV = np.zeros((dim, ), dtype='float32')
    for v in expert: 
        if isinstance(v, torch.Tensor):
            v = v.cpu().numpy()
        expertV = np.add(expertV, v)
    for v in action:
        if isinstance(v, torch.Tensor):
            v = v.cpu().numpy()
        actionV = np.add(actionV, v)
    # assume there is atleast one vector in sentence
    expertV = np.divide(expertV, seq_len)
    actionV = np.divide(actionV, seq_len)
    return np.dot(expertV, actionV)/(np.linalg.norm(expertV)*np.linalg.norm(actionV))


def get_entropy(mu, std):
    dist = Normal(mu, std)
    entropy = dist.entropy().mean()
    return entropy

def log_prob_density(x, mu, std):
    #TODO: Sanity check a few of these.. 
    log_prob_density = -(x - mu).pow(2) / (2 * std.pow(2)) \
                     - 0.5 * math.log(2 * math.pi)
    return log_prob_density.sum(2, keepdim=True).sum(1, keepdim=True) # I think this fixed it. 

def get_reward(discrim, state, action,args):
    """
    The reward function according to irl. It's log D(s,a). 
    
    Reward is higher the closer this is to 0, because the more similar it is to an expert action. :
    Is quite close to imitation learning, but hope here is that with such a large number of expert demonstrations and entropy bonuses etc. it learns more than direct imitation. 
    """

    action = torch.Tensor(action).to(device)# turn state into a tensor if not already

    with torch.no_grad():
        #TODO: better resize
        return -math.log(discrim(state.resize(1,args.seq_len,args.input_size),action.resize(1,args.seq_len,args.input_size))[0].item())

def save_checkpoint(state, filename):
    torch.save(state, filename)
    

def train_discrim(discrim, memory, discrim_optim, args):
    """
    Training the discriminator. 

    Use binary cross entropy to classify whether 
    or not a sequence was predicted by the expert (real data) or actor. 
    """
    states = torch.stack([memory[i][0] for i in range(len(memory))])
    actions = torch.stack([memory[i][1] for i in range(len(memory))])
   # rewards = [memory[i][2] for i in range(len(memory))]

    masks = [memory[i][2] for i in range(len(memory))]
    expert_actions = torch.stack([memory[i][4] for i in range(len(memory))])

    criterion = torch.nn.BCELoss() # classify

    for _ in range(args.discrim_update_num):

        learner = discrim(states, actions) #pass (s,a) through discriminator
       # demonstrations = torch.Tensor([states, expert_actions]) # pass (s,a) of expert through discriminator
        expert = discrim(states,expert_actions) #discrimator "guesses" whether or not these 
        # actions came from expert or learner
        discrim_loss = criterion(learner, torch.ones((states.shape[0], 1)).to(device)) + \
                        criterion(expert, torch.zeros((states.shape[0], 1)).to(device))
                # discrim loss: predict agent is all wrong, get as close to 0, and predict expert is 1, getting as close to 1 as possible. 
        discrim_optim.zero_grad() # gan loss, it tries to always get it right. 
        discrim_loss.backward()
        discrim_optim.step()
            # take these steps, do it however many times specified. 
        #return discrim(states,expert_actions) , discrim(states,actions)
    expert_acc = ((discrim(states,expert_actions) < 0.5).float()).mean() #how often it realized the fake examples were fake
    learner_acc = ((discrim(states,actions) > 0.5).float()).mean() #how often if predicted expert correctly. 

    return expert_acc, learner_acc # accuracy, it's the same kind, but because imbalanced better to look at separately. 


def train_actor_critic(actor, critic, memory, actor_optim, critic_optim, args):
    """
    Take a PPO step or two to improve the actor critic model,  using GAE to estimate returns. 
    
    In our case each trajectory it most one step, so the value function will have to do. 
    
    
    """
    # tuple of a regular old RL problem, but now reward is what the discriminator says. 
    states = torch.stack([memory[i][0] for i in range(len(memory))])
    actions = torch.stack([memory[i][1] for i in range(len(memory))])
    rewards = torch.stack([torch.Tensor([memory[i][2]]) for i in range(len(memory))]).to(device)
    masks = [memory[i][2] for i in range(len(memory))]
    # compute value of what happened, see if what we can get us better. 
    old_values = critic(states)

    #GAE aka estimate of Value + actual return roughtly 
    #returns, advants = get_gae(rewards, masks, old_values, args)
    
    # pass states through actor, get corresponding actions
    mu, std = actor(states)
    # new mus and stds? 
    old_policy = log_prob_density(actions, mu, std) # sum of log probability
    # of old actions

    criterion = torch.nn.MSELoss()
    n = len(states)
    arr = np.arange(n)

    for _ in range(args.actor_critic_update_num):
        np.random.shuffle(arr)

        for i in range(n // args.batch_size): 
            batch_index = arr[args.batch_size * i : args.batch_size * (i + 1)]
            #batch_index = torch.LongTensor(batch_index)
            
            inputs = states[batch_index]
            actions_samples = actions[batch_index]
           # returns_samples = returns.unsqueeze(1)[batch_index].to(device)
           # advants_samples = advants.unsqueeze(1)[batch_index].to(device)
            # oldvalue_samples = old_values[batch_index].detach()
        
        
            #values = critic(inputs) #
            #clipped_values = oldvalue_samples + \
            #                 torch.clamp(values - oldvalue_samples,
            #                             -args.clip_param, 
            #                             args.clip_param)
           # critic_loss1 = criterion(clipped_values, returns_samples)
            #critic_loss2 = criterion(values, returns_samples)
            #critic_loss = torch.max(critic_loss1, critic_loss2).mean()

            loss, ratio, entropy = surrogate_loss(actor, rewards, inputs,
                                         old_policy.detach(), actions_samples,
                                         batch_index)
            clipped_ratio = torch.clamp(ratio,
                                        1.0 - args.clip_param,
                                        1.0 + args.clip_param)
            clipped_loss = clipped_ratio * rewards#.unsqueeze(dim=1)
            actor_loss = -torch.min(loss, clipped_loss).mean()
            #print(actor_loss,critic_loss,entropy)
           # return actor_loss, critic_loss, entropy
            loss = actor_loss - 0.001 * entropy # + 0.5 * critic_loss  #entropy bonus to promote exploration.

            actor_optim.zero_grad()
            loss.backward()
            actor_optim.step()

           # critic_optim.zero_grad()
           # loss.backward() 
           # critic_optim.step()


def train_policy(actor, memory, actor_optim,, args):
    """
    Take a Policy Gradient step or two to improve the actor  model,  using the single step returns to optimize objective. 
    
    
    
    """
    # tuple of a regular old RL problem, but now reward is what the discriminator says. 
    states = torch.stack([memory[i][0] for i in range(len(memory))])
    actions = torch.stack([memory[i][1] for i in range(len(memory))])
    rewards = torch.stack([torch.Tensor([memory[i][2]]) for i in range(len(memory))]).to(device)
    masks = [memory[i][2] for i in range(len(memory))]
    # compute value of what happened, see if what we can get us better. 
    #GAE aka estimate of Value + actual return roughtly 
    #returns, advants = get_gae(rewards, masks, old_values, args)
    
    # pass states through actor, get corresponding actions
    action, action_probs = actor(states)
    # new mus and stds? 
    log_probs = log_prob_density(action, action_probs) # all log probabilities over these trajectories
    # of old actions

    n = len(states)
    arr = np.arange(n)
    entropy = get_entropy(action_probs)

    for _ in range(args.actor_critic_update_num):
        np.random.shuffle(arr)

        for i in range(n // args.batch_size): 
            batch_index = arr[args.batch_size * i : args.batch_size * (i + 1)]
            #batch_index = torch.LongTensor(batch_index)
            
            inputs = states[batch_index]
            actions_samples = actions[batch_index]
            policy_loss = -log_probs[batch_index] * rewards[batch_index]

            loss = policy_loss # + 0.5 * critic_loss  #entropy bonus to promote exploration.

            actor_optim.zero_grad()
            loss.backward()
            actor_optim.step()


def get_gae(rewards, masks, values, args):
    """
    How much better a particular action is in a particular state. 
    
    Uses reward of current action + value function of that state-action pair, discount factor gamma, and then lamda to compute. 
    """
    rewards = torch.Tensor(rewards)
    masks = torch.Tensor(masks)
    returns = torch.zeros_like(rewards)
    advants = torch.zeros_like(rewards)
    
    running_returns = 0
    previous_value = 0
    running_advants = 0

    for t in reversed(range(0, len(rewards))): #for LL, only ever one step :-)
        running_returns = rewards[t] + (args.gamma * running_returns * masks[t])
        returns[t] = running_returns

        running_delta = rewards[t] + (args.gamma * previous_value * masks[t]) - \
                                        values.data[t]
        previous_value = values.data[t]
        
        running_advants = running_delta + (args.gamma * args.lamda * \
                                            running_advants * masks[t])
        advants[t] = running_advants

    advants = (advants - advants.mean()) / advants.std()
    return returns, advants

def surrogate_loss(actor, advants, states, old_policy, actions, batch_index):
    """
    The loss for PPO. Re-run through network, recomput policy from states
    and see if this surrogate ratio is better. If it is, use as proximal policy update. It's very close to prior policy, but def better. 
    
    Not sure this actually works though. Should not the new mu and stds be used to draw,
    
        When do we use get_action? Only once in main, I think it should be for all? 
    """
    mu, std = actor(states)
    new_policy = log_prob_density(actions, mu, std)
    old_policy = old_policy[batch_index]

    ratio = torch.exp(new_policy - old_policy)
    surrogate_loss = ratio * advants#.unsqueeze(dim=1)
    entropy = get_entropy(mu, std)

    return surrogate_loss, ratio, entropy


if __name__ == "__main__":
    
    action = torch.rand(size=(30, 300))

    print(get_raw_action(action))
