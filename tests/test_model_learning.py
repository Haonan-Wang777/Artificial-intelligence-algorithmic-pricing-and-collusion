import numpy as np
from collusion.model import Game, demand
from collusion.learning import run_session, _argmax_lowest


def test_benchmarks_and_stationarity():
    g=Game()
    np.testing.assert_allclose(g.price_nash,1.47292666,atol=1e-7)
    np.testing.assert_allclose(g.price_monopoly,1.92498092,atol=1e-7)
    assert g.states == 225 and g.rewards.shape == (225,2)
    q=demand(g.price_nash,g.quality)
    np.testing.assert_allclose(g.price_nash-np.array(g.costs),g.mu/(1-q),atol=1e-10)
    for i in range(2):
        for step in (-1e-4,1e-4):
            p=g.price_nash.copy();p[i]+=step
            assert (p[i]-g.costs[i])*demand(p,g.quality)[i] <= g.profit_nash[i]+1e-10
    assert np.sum(demand([1000,1000],g.quality)) < 1e-100


def test_symmetry_payoffs_and_lowest_tie():
    g=Game()
    np.testing.assert_allclose(g.rewards.reshape(15,15,2)[:,:,0],
                               g.rewards.reshape(15,15,2)[:,:,1].T)
    assert _argmax_lowest(np.array([2.,2.,1.])) == 0


def test_seed_replay_and_single_update_equation():
    g=Game(m=3)
    kwargs=dict(alpha=.15,beta=4e-6,seed=42,max_periods=1,stable_periods=100000)
    a=run_session(g,**kwargs);b=run_session(g,**kwargs)
    np.testing.assert_array_equal(a[0],b[0])
    q0=np.empty_like(a[0])
    for i in range(2):
        for action in range(3):
            q0[i,:,action]=g.rewards[g.profiles[:,i]==action,i].mean()/(1-g.discount)
    # Exactly one state-action cell per agent is updated; verify actual TD update.
    old_state=None
    for i in range(2):
        changed=np.argwhere(a[0][i]!=q0[i])
        assert changed.shape == (1,2)
        s,action=changed[0]
        if old_state is not None: assert old_state == s
        old_state=s
        j=a[2]
        expected=(1-.15)*q0[i,s,action]+.15*(g.rewards[j,i]+.95*q0[i,j].max())
        np.testing.assert_allclose(a[0][i,s,action],expected)
    assert a[3] == 1 and not a[4]


def test_memoryless_and_stochastic_shapes():
    g=Game(k=0,shock=.15)
    a=run_session(g,.15,4e-6,43,max_periods=20,stable_periods=100000,sample_every=10)
    assert a[0].shape == (2,1,15) and a[2]==0 and a[5].shape==(2,3)
