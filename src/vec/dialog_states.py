# -*- coding: utf-8 -*-

import spacy
from tensor_helpers import np_to_var
import time
import torch
import numpy as np
from spacy_helpers import add_pipes_from_pretrained
from config import TOKENS_WITH_VECTOR_CUTOFF, TOKENS_RAW_CUTOFF
import gensim

from embeds_cust import processLine

def create_states(processed_txt_path, turn_limit=2):
    
    """We use a state function to compress the dialogue context and the words already generated in the current utterance
    to an intermediate representation, which will be regarded as the current state.
    For example, s0 = f(p) represents the state at time step 0 and it takes the dialogue context p as input.
    State st is given as st = f(p, a1, a2, . . . , at−1).
    For now, we limit the range of dialogue context to the utterances to 2 or 3 conversation turns."""

    dialog_sets = {}
    set_ind = 0
    dialog_sets[set_ind] = []
    with open(processed_txt_path, 'r', encoding='utf-8') as out:
        for line in out:
            line = line.replace("\n", "").replace("</s>","").replace("</d>","")
            dialog_sets[set_ind].append(processLine(line))
            if line.split(' ')[-1] == "</d>":
                set_ind += 1
                dialog_sets[set_ind] = []

    state_dict = {}  # state_dict[dialogue_context] = next state
    for dInd, turns in dialog_sets.items():
        if len(turns) == 2:
            state_dict[turns[0]] = turns[1]
        else:
            turns = list(reversed(turns))
            for i in range(len(turns)):
                if i + turn_limit > len(turns):
                    turn_range = len(turns)
                else:
                    turn_range = i + turn_limit
                rolling_turns = ''
                for j in range(i + 1, turn_range):
                    # print((i,j))
                    rolling_turns = turns[j] + " " + rolling_turns
                    state_dict[rolling_turns.strip()] = turns[i]
    return state_dict

def getTokIndices_fromDoc_gensim(w2v, doc):
    w2ind = {token: token_index for token_index, token in enumerate(w2v.index2word)} 
    v = []
    for tok in doc.split(' '):
        try:
            v.append(w2ind[tok])
        except KeyError:
            continue
    return np.array(v)

def getTokVect_fromDoc_gensim(w2v, doc): # doc is already processed from spacy #(doc: spacy.tokens.Doc):
    # document level token vectors (num_tokens, dim_tokens)
    v = []
    for tok in doc.split(' '):
        try:
            v.append(w2v[tok])
        except KeyError: # oov token, probably didnt appear much 
            continue
    return np.array(v)

def getTokVect_fromDoc_spacy(nlp, doc):
    v = []
    for tok in nlp(doc):
        if tok.has_vector:
            v.append(tok.vector)
        else:
            continue
    return np.array(v)


def create_state_vects(w2v, state_dict, no_pad = True):
    state_vects = {}
    dropped_vector_pairs = []
    for i, (k, v) in enumerate(state_dict.items()):
        # ignore pairs where raw tokens are above cutoff (assume processed)
        if ((len(k.split(' ')) > TOKENS_RAW_CUTOFF) or (len(v.split(' ')) > TOKENS_RAW_CUTOFF)):
            dropped_vector_pairs.append(i)
            continue

        #TokVectK = getTokVect_fromDoc_gensim(w2v, k) #getTokVect_fromDoc_spacy(w2v,k)
        #TokVectV = getTokVect_fromDoc_gensim(w2v, v) #getTokVect_fromDoc_spacy(w2v,v)
        
        TokVectK = getTokIndices_fromDoc_gensim(w2v, k)
        TokVectV = getTokIndices_fromDoc_gensim(w2v, v)
        
        # ignore pairs where initial_state or next_state are empty vectors, for now
        if ((len(TokVectK) == 0) or (len(TokVectV) == 0)):
            dropped_vector_pairs.append(i)
            continue
        # ignore pairs where either vectorized states are above cutoff
        if ((len(TokVectK) > TOKENS_WITH_VECTOR_CUTOFF) or (len(TokVectV) > TOKENS_WITH_VECTOR_CUTOFF)):
            dropped_vector_pairs.append(i)
            continue
        # ignore pairs where either vectorized states dont have assigned vectors for every 
        ## print(k.split(' '),len(TokVectK), len(k.split(' ')))
        ## print(v.split(' '),len(TokVectV), len(v.split(' ')))
        ## print("\n")
        if ((no_pad) and ((len(TokVectK) != len(k.split(' '))) or (len(TokVectV) != len(v.split(' '))))):
            dropped_vector_pairs.append(i)
            continue

        state_vects[i] = [
            TokVectK, 
            TokVectV
            ]
    return state_vects, dropped_vector_pairs


def pad_state_indices(w2v, vects, size =TOKENS_RAW_CUTOFF):
    w2ind = {token: token_index for token_index, token in enumerate(w2v.index2word)} 
    padded_vects = []

    doc_vects = list(vects.values())
    doc_inds = [[i, i] for i in list(vects.keys())]
    # flattened list of matrices from (initial_state,next_state) matrix pairs
    # of document vectors
    doc_vects_flatten = [np.array(v) for subv in doc_vects for v in subv]
    doc_inds_flatten = [i for subi in doc_inds for i in subi]
    assert len(doc_vects_flatten) == len(doc_inds_flatten) == 2 * len(vects)

    for v in doc_vects_flatten:
        t = size - len(v)
        padded = np.pad(v, pad_width=(w2ind["."], t), mode='constant') # ****pad with index of "." from pretrained embeddings for now
        padded_vects.append(padded)
    data = np_to_var(np.array(padded_vects), cuda=False) # not using gpu for now
    # re-create state dictionary
    padded_state_vects = {i: [] for i in list(vects.keys())}
    for i in range(len(doc_vects_flatten)):
        padded_state_vects[doc_inds_flatten[i]].append(data[i])
    assert len(padded_state_vects) == len(vects)

    return padded_state_vects


def pad_state_vects(vects, token_padding=False):

    doc_vects = list(vects.values())
    doc_inds = [[i, i] for i in list(vects.keys())]

    # flattened list of matrices from (initial_state,next_state) matrix pairs
    # of document vectors
    doc_vects_flatten = [np.array(v) for subv in doc_vects for v in subv]
    doc_inds_flatten = [i for subi in doc_inds for i in subi]
    assert len(doc_vects_flatten) == len(doc_inds_flatten) == 2 * len(vects)

    # Document level Padding
    lengths = np.array([v.shape[0] for v in doc_vects_flatten])
    max_length = max(lengths)
    dim = doc_vects_flatten[0].shape[1]
    data = np.zeros([len(doc_vects_flatten), max_length, dim])
    for i, seq in enumerate(doc_vects_flatten):
        # each vector in doc_vects_flatten is (N, D) where N is num. tokens and
        # D is vector dim (300 for google news vectors)
        seq_length = seq.shape[0]
        data[i, 0:seq_length, :] = seq
    data = np_to_var(data, cuda=False) # not using gpu for now
    print(data.shape)

    # re-create state dictionary
    padded_state_vects = {i: [] for i in list(vects.keys())}
    for i in range(len(doc_vects_flatten)):
        padded_state_vects[doc_inds_flatten[i]].append(data[i])
    assert len(padded_state_vects) == len(vects)

    return padded_state_vects


def run_dialog_states():

    """
    Given an initial state s0 representing the history of previous dialogues, a well-trained dialogue system should reply
        with a reasonable sentence hw0, w1, . . . , wti generated by selecting a specific word at different time steps.
        The length t is automatically decided by the policy network.
        We aim to find the optimal policy π(at|st) that selects the most appropriate word at each time step.
    """

    state_dict = create_states('./dat/processed/formatted_movie_lines.txt')

    torch.save(state_dict, './dat/processed/raw_states_v3.pt')

    """ # example print
    dist_print = 60
    print('='*200)
    for cs in list(state_dict.keys())[-20:-14]:
        sep = '-' * (dist_print - len(cs)) + '>'
        print(f'current state = {cs} {sep} next state = {state_dict[cs]}')
    """

    #nlp = spacy.load('./models/custom-GoogleNews/')
    #nlp = add_pipes_from_pretrained(nlp)

    model = gensim.models.Word2Vec.load("./models/custom_w2v_intersect_GoogleNews") # ("./models/custom_w2v")
    model.init_sims(replace=True) #precomputed l2 normed vectors in-place – saving the extra RAM

    #nlp = spacy.load('en_core_web_lg')

    state_vects,no_vector_pairs = create_state_vects(model.wv, state_dict)
    #state_vects,no_vector_pairs = create_state_vects(nlp, state_dict)
    assert len(state_dict)-len(no_vector_pairs) == len(state_vects)
    torch.save(state_vects, './dat/processed/vectorized_states_v3.pt')

    #padded_vects = pad_state_vects(state_vects)
    padded_vects = pad_state_indices(model.wv, state_vects)
    assert len(state_dict)-len(no_vector_pairs) == len(padded_vects)
    torch.save(padded_vects, './dat/processed/padded_vectorized_states_v3.pt')


if __name__ == "__main__":
    run_dialog_states()