"""Diagnostics tests use analytically solvable policies and independent equations."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from collusion.analysis import (analyze_session, best_response, evaluate_policy,
                               impulse_response, policy_dynamics, reachable_cycle)
from collusion.model import Game


def test_functional_graph_values_match_independent_linear_equations():
    # Two separate cycles, plus a transient chain and a self-loop.
    successor = np.array([1, 2, 1, 4, 4, 0])
    rewards = np.array([[1, 3], [2, 7], [4, 1], [5, 2], [9, 4], [6, 8.]])
    discount = 0.91
    transition = np.eye(len(successor))[successor]
    expected = np.linalg.solve(np.eye(len(successor))-discount*transition, rewards)
    actual = evaluate_policy(successor, rewards, discount)
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-13)
    np.testing.assert_allclose(evaluate_policy(successor, rewards[:, 0], 0), rewards[:, 0])
    transient, cycle = reachable_cycle(successor, 5)
    assert transient.tolist() == [5, 0]
    assert cycle.tolist() == [1, 2]


def test_memoryless_best_response_and_payoff_loss_are_analytic():
    game = Game(k=0, m=5, discount=0.8)
    policy = np.array([[4], [3]])
    result = analyze_session(game, policy, 0)
    for i in range(2):
        own = int(policy[i, 0])
        opponent = int(policy[1-i, 0])
        candidates = np.arange(game.m)*game.m+opponent if i == 0 else opponent*game.m+np.arange(game.m)
        stage = game.rewards[candidates, i]
        maximum = stage.max()
        expected_loss = (maximum-stage[own])/maximum
        assert result["best_response"][i]["q_loss_on_path"] == pytest.approx(expected_loss, abs=1e-10)
        # One-action error permits optimal continuation, so the gap is 1-gamma times smaller.
        assert result["best_response"][i]["action_loss_on_path"] == pytest.approx((1-game.discount)*expected_loss, abs=1e-10)
    json.dumps(result)


def test_bellman_equations_against_fixed_rival_not_joint_optimization():
    game = Game(m=3, discount=0.7)
    # Opponent reacts to lagged action; optimal response needs forward planning.
    policy = np.array([[2, 1, 0, 1, 0, 2, 0, 2, 1],
                       [2, 2, 1, 0, 1, 1, 2, 0, 0]])
    for i in range(game.n):
        result = best_response(game, policy, i)
        for state in range(game.states):
            alternatives = []
            for action in range(game.m):
                profile = policy[:, state].copy()
                profile[i] = action
                joint = int(profile[0]*game.m+profile[1])
                alternatives.append(game.rewards[joint, i]+game.discount*result["value"][joint])
            assert result["value"][state] == pytest.approx(max(alternatives), abs=1e-10)
            np.testing.assert_allclose(result["q_star"][state], alternatives)
        assert result["bellman_residual"] <= 1e-11


def test_cycle_statistics_exclude_transient_and_include_all_phases():
    game = Game(m=3)
    policy = np.zeros((game.n, game.states), dtype=int)
    policy[:, 0] = [0, 1]  # 0 -> 1 -> 8 -> 1.
    policy[:, 1] = [2, 2]
    policy[:, 8] = [0, 1]
    result = analyze_session(game, policy, 0)
    assert result["transient_states"] == [0]
    assert result["cycle_states"] == [1, 8]
    assert result["cycle_length"] == 2
    assert result["cycle_class"] == "2"
    np.testing.assert_allclose(result["mean_profit"], game.rewards[[8, 1]].mean(axis=0))
    expected_delta = ((game.rewards[[8, 1]].mean(axis=0)-game.profit_nash)/
                      (game.profit_monopoly-game.profit_nash)).mean()
    assert result["mean_delta"] == pytest.approx(expected_delta)


def test_zero_discount_optimal_static_game_is_equilibrium():
    # An artificial dominant-action game makes exact assertions possible.
    game = SimpleNamespace(n=2, m=2, states=4, k=1, discount=0.,
                           prices=np.array([[1., 2.], [1., 2.]]),
                           rewards=np.array([[1., 1.], [1., 0.], [0., 1.], [0., 0.]]),
                           profit_nash=np.array([0., 0.]), profit_monopoly=np.array([2., 2.]))
    policy = np.zeros((2, 4), dtype=int)
    result = analyze_session(game, policy, 3)
    assert result["is_equilibrium"]
    assert result["is_subgame_perfect"]
    assert result["q_loss_on_path"] == 0
    assert result["cycle_class"] == "1-Sym."


def test_impulse_exact_gain_and_cycle_phase_weighting():
    game = Game(m=3, discount=0.8)
    policy = np.zeros((2, game.states), dtype=int)
    policy[:, 0] = [0, 1]
    policy[:, 1] = [2, 2]
    policy[:, 8] = [0, 1]
    result = impulse_response(game, policy, 0, horizon=15)
    assert result["time"] == list(range(16))
    assert result["phases"] == 2
    # Independently sum a very long paired trajectory from each cycle phase.
    gains, paths, baseline_paths = [], [], []
    for start in [1, 8]:
        state = baseline_state = start
        trajectory, baseline_trajectory = [], []
        gain = np.zeros(2)
        rival_predeviation_action = policy[1, start]
        forced = np.argmax(game.rewards[np.arange(game.m)*game.m+rival_predeviation_action, 0])
        for t in range(500):
            action = policy[:, state].copy()
            baseline_action = policy[:, baseline_state]
            if t == 1:
                action[0] = forced
            joint = action[0]*game.m+action[1]
            baseline_joint = baseline_action[0]*game.m+baseline_action[1]
            if t:
                gain += game.discount**(t-1)*(game.rewards[joint]-game.rewards[baseline_joint])
            trajectory.append(game.prices[np.arange(2), action])
            baseline_trajectory.append(game.prices[np.arange(2), baseline_action])
            state, baseline_state = joint, baseline_joint
        gains.append(gain)
        paths.append(trajectory[:16])
        baseline_paths.append(baseline_trajectory[:16])
    np.testing.assert_allclose(result["discounted_gain"], np.mean(gains, axis=0), atol=1e-12)
    np.testing.assert_allclose(result["prices"], np.mean(paths, axis=0))
    np.testing.assert_allclose(result["baseline_prices"], np.mean(baseline_paths, axis=0))
    np.testing.assert_allclose(result["prices"][0], result["baseline_prices"][0])
    json.dumps(result)


def test_impulse_memoryless_return_and_no_horizon_truncation():
    game = Game(k=0, m=5)
    policy = np.array([[4], [4]])
    short = impulse_response(game, policy, 0, horizon=1)
    long = impulse_response(game, policy, 0, horizon=15)
    assert short["discounted_gain"] == long["discounted_gain"]
    np.testing.assert_allclose(np.array(long["prices"])[2:], np.tile(long["baseline_prices"][0], (14, 1)))
    assert long["discounted_gain"][0] > 0
    assert not long["incentive_compatible"]


def test_reject_invalid_policy_and_impulse_dimensions():
    game = Game(m=3)
    with pytest.raises(ValueError):
        analyze_session(game, np.zeros((2, 1)), 0)
    with pytest.raises(ValueError):
        analyze_session(game, np.full((2, game.states), 0.5), 0)
    with pytest.raises(ValueError):
        impulse_response(game, np.zeros((2, game.states)), 0, horizon=0)
