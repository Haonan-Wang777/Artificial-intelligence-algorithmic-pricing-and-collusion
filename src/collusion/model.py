"""Logit Bertrand stage game, continuous benchmarks, and exact action lattice."""
from dataclasses import dataclass
from itertools import product
import numpy as np
from scipy.optimize import root, brentq


def demand(prices, quality, mu=0.25, outside=0.0):
    """Multinomial logit shares (including the outside option in denominator)."""
    z = (np.asarray(quality) - np.asarray(prices)) / mu
    shift = max(float(np.max(z)), outside / mu)
    e = np.exp(z - shift)
    return e / (np.sum(e) + np.exp(outside / mu - shift))


@dataclass
class Game:
    costs: tuple = (1.0, 1.0)
    quality: tuple = (2.0, 2.0)
    mu: float = 0.25
    outside: float = 0.0
    discount: float = 0.95
    m: int = 15
    xi: float = 0.1
    k: int = 1
    shock: float = 0.0

    def __post_init__(self):
        self.n = len(self.costs)
        if self.n != len(self.quality) or self.k not in (0, 1):
            raise ValueError("Equal parameter lengths and memory k in {0,1} required")
        if self.mu <= 0 or not 0 <= self.discount < 1 or self.m < 2:
            raise ValueError("Require mu>0, 0<=discount<1, m>=2")
        c, a = np.asarray(self.costs), np.asarray(self.quality)
        # FOC: p_i-c_i = mu/(1-q_i). Joint monopoly: common markup mu/q_0.
        def nash_foc(p):
            return p - c - self.mu / (1 - demand(p, a, self.mu, self.outside))
        solution = root(nash_foc, c + 2*self.mu)
        if not solution.success or np.max(np.abs(nash_foc(solution.x))) > 1e-9:
            raise RuntimeError("Continuous Nash benchmark solver failed")
        self.price_nash = solution.x
        def monopoly_foc(markup):
            shares = demand(c + markup, a, self.mu, self.outside)
            return markup * (1-shares.sum()) - self.mu
        markup = brentq(monopoly_foc, self.mu, float(max(a-c)+10))
        self.price_monopoly = c + markup
        self.profit_nash = (self.price_nash-c)*demand(self.price_nash,a,self.mu,self.outside)
        self.profit_monopoly = (self.price_monopoly-c)*demand(self.price_monopoly,a,self.mu,self.outside)
        gap = self.price_monopoly-self.price_nash
        self.prices = np.array([np.linspace(self.price_nash[i]-self.xi*gap[i],
                                            self.price_monopoly[i]+self.xi*gap[i],self.m)
                                for i in range(self.n)])
        self.profiles = np.array(list(product(range(self.m),repeat=self.n)),dtype=np.int64)
        self.states = self.m**self.n if self.k else 1
        self.rewards = np.empty((len(self.profiles),self.n))
        self.shock_rewards = np.empty((3,len(self.profiles),self.n))
        for j, actions in enumerate(self.profiles):
            p = self.prices[np.arange(self.n),actions]
            for h, shock in enumerate((-self.shock,0,self.shock)):
                self.shock_rewards[h,j] = (p-c)*demand(p,a,self.mu,self.outside+shock)
        self.rewards[:] = self.shock_rewards.mean(axis=0)

    def benchmark_dict(self):
        return {"price_nash":self.price_nash.tolist(),"price_monopoly":self.price_monopoly.tolist(),
                "profit_nash":self.profit_nash.tolist(),"profit_monopoly":self.profit_monopoly.tolist(),
                "price_grid":self.prices.tolist(),"states":self.states,
                "q_cells_per_agent":self.states*self.m}
