"""Simultaneous tabular Q-learning. No approximation to the state/action space."""
import numpy as np
from numba import njit


@njit(cache=True)
def _argmax_lowest(row):
    best = 0
    for a in range(1,len(row)):
        if row[a] > row[best]:
            best = a
    return best


@njit(cache=True)
def train(rewards, shock_rewards, profiles, n, m, states, k, discount,
          alpha, beta, seed, stable_periods=100000, max_periods=1000000000,
          sample_every=10000, stochastic=False):
    """Return Q, greedy policy, last state, steps, convergence flag, block rewards.

    All agents act on old Q before any update. Lowest price breaks ties. Because
    only one Q row per player changes per period, comparing that row's greedy
    action is exactly equivalent to comparing *every* state's policy every period.
    NumPy/Numba MT19937 streams are independent per session; not authors' RNG.
    """
    np.random.seed(seed)
    q = np.zeros((n,states,m))
    for i in range(n):
        for a in range(m):
            total, count = 0.0, 0
            for j in range(len(profiles)):
                if profiles[j,i] == a:
                    total += rewards[j,i]
                    count += 1
            q[i,:,a] = total/count/(1-discount)
    policy = np.zeros((n,states),dtype=np.int64)
    for i in range(n):
        action = _argmax_lowest(q[i,0])
        policy[i,:] = action
    state = np.random.randint(states)
    actions = np.empty(n,dtype=np.int64)
    targets = np.empty(n)
    history = np.empty((max_periods//sample_every+1,n+1))
    block = np.zeros(n)
    recorded, stable = 0, 0
    for t in range(max_periods):
        epsilon = np.exp(-beta*t)
        joint = 0
        for i in range(n):
            if np.random.random() < epsilon:
                actions[i] = np.random.randint(m)
            else:
                actions[i] = policy[i,state]
            joint = joint*m+actions[i]
        next_state = joint if k else 0
        h = np.random.randint(3) if stochastic else 1
        for i in range(n):
            reward = shock_rewards[h,joint,i] if stochastic else rewards[joint,i]
            targets[i] = reward+discount*q[i,next_state,policy[i,next_state]]
            block[i] += reward
        changed = False
        for i in range(n):
            q[i,state,actions[i]] = (1-alpha)*q[i,state,actions[i]]+alpha*targets[i]
            best = _argmax_lowest(q[i,state])
            if best != policy[i,state]:
                changed = True
                policy[i,state] = best
        stable = 0 if changed else stable+1
        state = next_state
        if (t+1)%sample_every == 0:
            history[recorded,0] = t+1
            for i in range(n):
                history[recorded,i+1] = block[i]/sample_every
                block[i] = 0
            recorded += 1
        if stable >= stable_periods:
            return q,policy,state,t+1,True,history[:recorded]
    return q,policy,state,max_periods,False,history[:recorded]


def run_session(game, alpha, beta, seed, stable_periods=100000,
                max_periods=1000000000, sample_every=10000):
    if not 0 < alpha <= 1 or beta <= 0:
        raise ValueError("Require 0<alpha<=1 and beta>0")
    return train(game.rewards,game.shock_rewards,game.profiles,game.n,game.m,
                 game.states,game.k,game.discount,alpha,beta,seed,stable_periods,
                 max_periods,sample_every,game.shock>0)
