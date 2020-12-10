# limitation-learning

This repository houses the code for the NYU Deep Reinforcement Learning Fall 2020 Final Project by Rahul Zalkikar and Noah Kasmanoff, "Limitation Learning: Probing the Behavior of Large Language Models with Imitation Learning". 



## Introduction

The exponential popularity and implementation of artificial intelligence and machine learning owes much credit to the era "big data", and the feasibility of crafting algorithms with millions of parameters. In particular this has allowed the onset and implementation of deep learning models in the domain of natural language processing, with direct applications to companies such as chat-bots. Unfortunately, the rise of large language models present many problems, out of our expertise, but most notably, the fact that they are large means they are restrictive, and not easily understandable. The purpose of this work is to demonstrate the possible applications of imitation learning and inverse reinforcement learning as a means to probe large language models. 


In this work, we apply generative adversarial imitation learning (GAIL) to produce a proxy for the reward function present in a basic conversation, using data pulled from the Cornell Movie Corpus dataset (link). Our purpose is to show that by using GAIL, we can use imitation learning to craft an agent capable of formulating coherent responses, or actions, to the input utterance, or state. 

In particular, our focus is on an auxilary goal of GAIL, which is using a discriminator network as a proxy for a reward function that central to reinforcement learning. For more information on how exactly this reward function operates, please refer to our methodology + background. 

This proxy reward function is the crux of our contribution. We hope that after training the policy and discriminator networks to equilibrium, we may use this proxy reward function as a way to probe black box language models with direct feedback. Essentially given a state utterance and action utterance, our reward function allows the user to see how high or low this pair is, in comparison to similar state action pairs.


We feed inputs to conversational AI, extract responses, and pass this through the reward function to gain a better intuition that language model's performance. 


This work is just the beginning of a larger effort to probe language models. We emphasize that GAIL is a method of imitation, not inverse reinforcement learning. This distinction is important in that we cannot recover the underlying reward function of the system, but instead a proxy based on imitation. We consider the application of more advanced techniques such as guided cost learning a worthwhile next step if this technique succeeds.

## Methods

Data. For this work, we use conversations from the Cornell-Movie-Dialog corpus, which contains over xxx conversations. We first split this corpus into conversation pairs, and use those pairs for training. In terms of a reinforcement learning algorithm, we still aim to maximize an expected reward over a trajectory, however in all cases the trajectory, or conversation length, is 1. It is possible to extend this technique to conversations of varying length, but for the purposes of proof-of-concept we do not explore this approach. 

As a means to accelerate the development of this work, we use Spacy and it's embedding software to quickly transform the words/tokens of our dataset into vector embeddings. We should note this introduces some bias to our dataset, seeing as the embeddings originate from an outside source, Google News, but we attempt to mitigate this by fine-tuning our results. This phase of the project transforms our conversations into a vectorized, model-readable form which is then used for training. 


GAIL.

Gail is a technique that casts the objective of imitation learning, training policies via expert demonstrations, into a min max optimization problem analagous to a generative adversarial network.

To do so, GAIL uses a discriminator network, characterized by loss function EQN to distinguish between policy and expert generated actions given a state input, in the process creating a proxy for the reward function ubiquitous to RL, formulated as EQN


Using this proxy to the rewards, hereby expesssd as r psi, we are able to train a policy via model free reinforcement learning to better imitate the expert. The better the policy gets the more the discriminator must improve it’s proxy for the reward, and so on until convergence. 

In this research, we aim to deploy this technique in the context of dialog. We do so by undergoing the following 


In the reinforcement learning landscape, training a policy from expert demonstrations is an active area of research. GAIL is an attempt to bridge the gap between two popular techniques and draw similarities to other methods in machine learning unrelated to RL. Imitation learning parallels supervised learning, in that an agent's policy is trained to mimic the expert as closely as possible. Inverse reinforcement learning takes imitation one step further, in that it seeks to use expert data to infer the underlying dynamics of the system, most notably the reward function. This reward function is an essential tool for training abitrary reinforcement learning techniques, and provides valuable intuition. General Adversarial Imitation Learning, GAIL 


How do I motivate this?
There is a lot of background, but to summarize GAIL, is that it couples imitation learning with inverse reinforcement learning. It draws strong comparisons to GANs,

GAIL is a powerful technique for imitation/inverse reinforcement learning. While there are many ways to extract the intuition from it, the key insight we draw from GAIL's formulations is that ....

TODO
...



Networks. 
After discussing the specifics of GAIL, we now touch on the various architectures employed. 

For the policy network, we use a sequence-to-sequence architecture, which maps the input state, a matrix of size Nx300 where (N represents the number of tokens in the sequence, and 300 represents that each token is a 300 dimensional vector) to a similarly sized matrix of Nx300. 

Of this output, each element now corresponds to the mean of a gaussian distribution with standard deviation Y. This is to encourage exploration, while simultaneously allowing this to obey the policy gradient formulation, albeit in a slightly more sophisticated manner. 

TODO


Training:

For training we follow the method laid out in the original GAIL paper, with a few changes (given the fixed trajectory length of 1), and reflect those differences in the algorithm described: 


In our work, it is not straightforward how we would determine stopping criteria. 
Since we do not have access to an underlying reward function aside from our proxy, it is impossible to determine how close or not our training has gotten to achieving equilibrium between the networks. 

As an alternative, we draw conclusions on GAIL success by examining the resulting actions the policy selects. As an example of this evolution and determination to stop training, we present the following actions selected by the network at different phases of training:

Phase 1: Action  = asdlk;fa;lisdfjkl;as;dkf
Phase 21241: Action = I love you dear, how about a pizza. 

Once this network has met our standards, we extract the discriminator and use it's log to extract rewards for different samples. 



## Results

GAIL has a variety of hyper-parameters to tune. By choosing our trajectories to be a single timestep, we successfully reduce this by eliminating values such as discount factor gamma, and GAE factor lambda. Even so, we still faced many values to tune. To do so we train our model on NYU Greene using a V100 GPU, and log on tensorboard the corresponding average expert accuracies, example policy state action pairs (in comparison to their expert companions), and finally evaluate the reward of random actions and large language model actions. 



## Conclusion

By training GAIL, we achieve a policy capable of producing resonable responses to common utterances from movie dialog. Initializing our word embeddings from y. 

Additionally, we achieve a discriminator which serves as a proxy reward function for state-action pairs. Using this proxy reward function, we examine the topology of state-action pairs, and examine how an out of the box language model performs as a result of our proxy. 

This work is an important first step in better characterizing large language models from an outside perspective. By casting dialog as a reinforcement learning problem, we are able to acquire direct feedback in the form of a reward function which indicates how similar state-action pairs are received. 


## Next Steps

In future work, we hope to extend our task to extended conversations, acquire access to GPT3, and take a step farther than imitation and use inverse reinforcement learning as a more accurate representation of dialog reward dynamics. 



