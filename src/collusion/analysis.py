"""Exact diagnostics of frozen policies; exploration and learning are disabled.

All cycle statistics average every phase once, so a session is one observation.
The main ``q_loss`` is (V* - V_policy) / V*: both continuation policies are
evaluated against the same frozen opponents. This follows the payoff definition
in Appendix Figure A4. The separate ``action_loss`` compares Q*(s, a_policy)
with max_a Q*(s, a), which allows optimal play *after* the current action; it is
not the loss from following the learned policy forever. Neither numerical
roundoff rules nor unpublished author aggregation conventions are assumed exact.
"""
from __future__ import annotations

import numpy as np


BELLMAN_TOLERANCE = 1e-11
OPTIMALITY_TOLERANCE = 1e-8  # Absolute discounted-profit units, not percentages.


def _checked_policy(game, policy):
    values = np.asarray(policy)
    if values.shape != (game.n, game.states):
        raise ValueError("Policy must have shape (players, states)")
    if not np.all(np.isfinite(values)) or not np.all(values == values.astype(np.int64)):
        raise ValueError("Policy actions must be finite integers")
    values = values.astype(np.int64, copy=False)
    if np.any(values < 0) or np.any(values >= game.m):
        raise ValueError("Policy actions must belong to the price grid")
    return values


def _joint_indices(actions, m):
    """Encode profiles in the same lexicographic order as Game.profiles."""
    actions = np.asarray(actions, dtype=np.int64)
    weights = m ** np.arange(actions.shape[-1] - 1, -1, -1)
    return actions @ weights


def policy_dynamics(game, policy):
    """Return joint-profile index, successor state, and reward at every state."""
    policy = _checked_policy(game, policy)
    joint = _joint_indices(policy.T, game.m)
    successor = joint if game.k else np.zeros(game.states, dtype=np.int64)
    return joint, successor, game.rewards[joint]


def reachable_cycle(successor, initial_state):
    """Find the exact eventual orbit, retaining its transient separately."""
    successor = np.asarray(successor, dtype=np.int64)
    if not 0 <= initial_state < len(successor):
        raise ValueError("Initial state is outside the state space")
    visited, path = {}, []
    state = int(initial_state)
    while state not in visited:
        visited[state] = len(path)
        path.append(state)
        state = int(successor[state])
    split = visited[state]
    return np.asarray(path[:split], dtype=np.int64), np.asarray(path[split:], dtype=np.int64)


def evaluate_policy(successor, rewards, discount):
    """Evaluate a deterministic discounted policy by its functional graph.

    For a cycle of length L, V(s_0) = sum_t gamma**t r(s_t) /
    (1 - gamma**L). Values at other cycle phases and preceding states follow by
    backward substitution. This avoids a truncated finite-horizon approximation
    and a potentially expensive dense linear solve.
    """
    successor = np.asarray(successor, dtype=np.int64)
    rewards = np.asarray(rewards, dtype=float)
    if rewards.shape[0] != len(successor) or not 0 <= discount < 1:
        raise ValueError("Incompatible dynamics or discount")
    scalar = rewards.ndim == 1
    if scalar:
        rewards = rewards[:, None]
    values = np.empty_like(rewards)
    solved = np.zeros(len(successor), dtype=bool)
    for initial in range(len(successor)):
        if solved[initial]:
            continue
        visited, path = {}, []
        state = initial
        while not solved[state] and state not in visited:
            visited[state] = len(path)
            path.append(state)
            state = int(successor[state])
        if not solved[state]:
            split = visited[state]
            cycle = path[split:]
            powers = discount ** np.arange(len(cycle))
            # expm1 protects 1-gamma**L for discount factors near one.
            denominator = (1.0 if discount == 0 else -np.expm1(len(cycle) * np.log(discount)))
            values[state] = np.sum(powers[:, None] * rewards[cycle], axis=0) / denominator
            solved[state] = True
            for node in reversed(cycle[1:]):
                values[node] = rewards[node] + discount * values[successor[node]]
                solved[node] = True
            path = path[:split]
        for node in reversed(path):
            values[node] = rewards[node] + discount * values[successor[node]]
            solved[node] = True
    return values[:, 0] if scalar else values


def best_response(game, policy, player, tolerance=BELLMAN_TOLERANCE):
    """Solve the finite MDP against fixed opponent strategies by value iteration.

    Returned Bellman residual bounds the absolute V* error by residual/(1-gamma).
    In the stochastic-demand treatment rewards are the exact three-shock mean;
    shocks do not change the price-memory transition.
    """
    policy = _checked_policy(game, policy)
    if not 0 <= player < game.n or tolerance <= 0:
        raise ValueError("Invalid player or tolerance")
    joint = _joint_indices(policy.T, game.m)
    weight = game.m ** (game.n - 1 - player)
    candidates = joint[:, None] + weight * (np.arange(game.m)[None, :] - policy[player, :, None])
    successor = candidates if game.k else np.zeros_like(candidates)
    reward = game.rewards[candidates, player]
    # A constant value below all attainable returns provides monotone iteration.
    value = np.full(game.states, np.min(reward) / (1 - game.discount))
    for iteration in range(1, 1000001):
        q_star = reward + game.discount * value[successor]
        updated = q_star.max(axis=1)
        residual = float(np.max(np.abs(updated - value)))
        value = updated
        if residual <= tolerance:
            break
    else:
        raise RuntimeError("Best-response Bellman iteration did not reach tolerance")
    q_star = reward + game.discount * value[successor]
    residual = float(np.max(np.abs(q_star.max(axis=1) - value)))
    return dict(value=value, q_star=q_star, policy=q_star.argmax(axis=1),
                bellman_residual=residual, iterations=iteration)


def _relative_loss(optimal, actual):
    """A fraction of optimal discounted profit, with explicit zero handling."""
    gap = np.maximum(np.asarray(optimal) - np.asarray(actual), 0.0)
    scale = np.abs(optimal)
    return np.divide(gap, scale, out=np.zeros_like(gap), where=scale > 1e-15)


def analyze_session(game, policy, final_state):
    """JSON-ready cycle, profit, and exact equilibrium diagnostics for one session.

    ``q_loss_*`` and ``action_loss_*`` are fractions (0.002 means 0.2 percent).
    Both average equally over agents and, respectively, cycle phases or all
    states. ``is_equilibrium`` checks every player at every on-path state using
    absolute discounted value loss <= 1e-8. This tolerance exceeds the certified
    Bellman numerical error, and is saved with the output.
    """
    policy = _checked_policy(game, policy)
    joint, successor, rewards = policy_dynamics(game, policy)
    transient, cycle = reachable_cycle(successor, final_state)
    actions = policy[:, cycle].T
    prices = game.prices[np.arange(game.n)[None, :], actions]
    profits = rewards[cycle]
    mean_profit = profits.mean(axis=0)
    delta = (profits - game.profit_nash) / (game.profit_monopoly - game.profit_nash)
    cycle_length = len(cycle)
    symmetric = bool(np.all(actions == actions[:, :1]))
    cycle_class = ("1-Sym." if symmetric else "1-Asym.") if cycle_length == 1 else ("2" if cycle_length == 2 else ">=3")
    summary = dict(cycle_length=cycle_length, cycle_class=cycle_class,
                   cycle_symmetric=symmetric, transient_length=len(transient),
                   transient_states=transient.tolist(), cycle_states=cycle.tolist(),
                   cycle_actions=actions.tolist(), cycle_prices=prices.tolist(),
                   cycle_profits=profits.tolist(), mean_profit=mean_profit.tolist(),
                   mean_price=prices.mean(axis=0).tolist(), mean_delta=float(delta.mean()),
                   delta_by_player=delta.mean(axis=0).tolist())
    # Multi-firm robustness runs report exact cycle profits only. A missing
    # equilibrium diagnostic must not silently become a positive equilibrium.
    if game.n > 2:
        return dict(summary, q_loss_on_path=None, q_loss_all_states=None,
                    action_loss_on_path=None, action_loss_all_states=None,
                    is_equilibrium=None, is_subgame_perfect=None,
                    bellman_residual=None, best_response=[],
                    best_response_omitted_reason="Budgeted multi-firm robustness: cycle profits only")
    policy_values = evaluate_policy(successor, rewards, game.discount)
    players, q_losses, action_losses, optimal_flags, residuals = [], [], [], [], []
    for player in range(game.n):
        result = best_response(game, policy, player)
        optimal = result["value"]
        own_value = policy_values[:, player]
        value_gap = np.maximum(optimal - own_value, 0.0)
        q_loss = _relative_loss(optimal, own_value)
        q_optimal = result["q_star"].max(axis=1)
        chosen_q = result["q_star"][np.arange(game.states), policy[player]]
        action_loss = _relative_loss(q_optimal, chosen_q)
        flags = value_gap <= OPTIMALITY_TOLERANCE
        players.append(dict(player=player,
                            q_loss_on_path=float(q_loss[cycle].mean()),
                            q_loss_all_states=float(q_loss.mean()),
                            action_loss_on_path=float(action_loss[cycle].mean()),
                            action_loss_all_states=float(action_loss.mean()),
                            is_optimal_on_path=bool(flags[cycle].all()),
                            optimal_state_fraction=float(flags.mean()),
                            bellman_residual=result["bellman_residual"],
                            value_error_bound=result["bellman_residual"] / (1-game.discount),
                            iterations=result["iterations"],
                            mean_optimal_value_on_path=float(optimal[cycle].mean()),
                            mean_policy_value_on_path=float(own_value[cycle].mean()),
                            mean_value_gap_on_path=float(value_gap[cycle].mean())))
        q_losses.append(q_loss)
        action_losses.append(action_loss)
        optimal_flags.append(flags)
        residuals.append(result["bellman_residual"])
    return dict(summary,
                q_loss_on_path=float(np.asarray(q_losses)[:, cycle].mean()),
                q_loss_all_states=float(np.mean(q_losses)),
                action_loss_on_path=float(np.asarray(action_losses)[:, cycle].mean()),
                action_loss_all_states=float(np.mean(action_losses)),
                is_equilibrium=bool(np.asarray(optimal_flags)[:, cycle].all()),
                is_subgame_perfect=bool(np.asarray(optimal_flags).all()),
                bellman_residual=max(residuals),
                bellman_tolerance=BELLMAN_TOLERANCE,
                optimality_tolerance=OPTIMALITY_TOLERANCE, best_response=players)


def impulse_response(game, policy, final_state, horizon=15):
    """One-period forced static best response, averaging all cycle phases.

    t=0 is a cycle outcome. At t=1, player 0 uses the discrete static best
    response to player 1's t=0 price (lowest-price tie break). The rival follows
    its frozen policy at t=1; from t=2 both follow frozen policies. The paired
    baseline always follows frozen policies from the same phase. For cycles,
    the rival's actual t=1 price can differ from its t=0 price, as explicitly
    prescribed by the paper's predeviation-price convention.

    The reported discounted gain starts at t=1 and includes the infinite tail
    evaluated exactly; it does not truncate at ``horizon``. Paths are first
    averaged within a session; a caller must weight sessions equally.
    """
    if game.n != 2 or not isinstance(horizon, (int, np.integer)) or horizon < 1:
        raise ValueError("Impulse response requires two players and horizon>=1")
    policy = _checked_policy(game, policy)
    joint, successor, rewards = policy_dynamics(game, policy)
    _, cycle = reachable_cycle(successor, final_state)
    values = evaluate_policy(successor, rewards, game.discount)
    baseline_prices = np.empty((len(cycle), horizon+1, game.n))
    baseline_profits = np.empty_like(baseline_prices)
    deviation_prices = np.empty_like(baseline_prices)
    deviation_profits = np.empty_like(baseline_prices)
    gains = np.empty((len(cycle), game.n))
    baseline_values = np.empty_like(gains)
    deviation_values = np.empty_like(gains)
    deviation_actions, changed = [], []
    for phase, start in enumerate(cycle):
        baseline_state = deviation_state = int(start)
        predeviation = policy[:, start]
        candidate_joint = np.arange(game.m) * game.m + predeviation[1]
        forced_action = int(np.argmax(game.rewards[candidate_joint, 0]))
        deviation_actions.append(forced_action)
        for time in range(horizon+1):
            baseline_action = policy[:, baseline_state]
            deviation_action = policy[:, deviation_state].copy()
            if time == 1:
                deviation_action[0] = forced_action
                changed.append(bool(forced_action != baseline_action[0]))
            baseline_joint = int(_joint_indices(baseline_action, game.m))
            deviation_joint = int(_joint_indices(deviation_action, game.m))
            baseline_prices[phase, time] = game.prices[np.arange(game.n), baseline_action]
            deviation_prices[phase, time] = game.prices[np.arange(game.n), deviation_action]
            baseline_profits[phase, time] = game.rewards[baseline_joint]
            deviation_profits[phase, time] = game.rewards[deviation_joint]
            next_baseline = baseline_joint if game.k else 0
            next_deviation = deviation_joint if game.k else 0
            if time == 1:
                baseline_values[phase] = values[baseline_state]
                deviation_values[phase] = game.rewards[deviation_joint] + game.discount * values[next_deviation]
                gains[phase] = deviation_values[phase] - baseline_values[phase]
            baseline_state, deviation_state = next_baseline, next_deviation
    return dict(time=list(range(horizon+1)), deviating_player=0,
                prices=deviation_prices.mean(axis=0).tolist(),
                profits=deviation_profits.mean(axis=0).tolist(),
                baseline_prices=baseline_prices.mean(axis=0).tolist(),
                baseline_profits=baseline_profits.mean(axis=0).tolist(),
                price_changes=(deviation_prices-baseline_prices).mean(axis=0).tolist(),
                profit_changes=(deviation_profits-baseline_profits).mean(axis=0).tolist(),
                discounted_gain=gains.mean(axis=0).tolist(),
                discounted_baseline_value=baseline_values.mean(axis=0).tolist(),
                discounted_deviation_value=deviation_values.mean(axis=0).tolist(),
                phase_discounted_gains=gains.tolist(),
                incentive_compatible=bool(np.all(gains[:, 0] <= OPTIMALITY_TOLERANCE)),
                incentive_compatible_phase_fraction=float(np.mean(gains[:, 0] <= OPTIMALITY_TOLERANCE)),
                actually_changed_phase_fraction=float(np.mean(changed)),
                deviation_actions=deviation_actions, phases=len(cycle),
                discount_start_time=1, infinite_tail_evaluated=True)
