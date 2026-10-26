"""Analytical checks distinguish a one-step diagnostic from full dynamic BR."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from collusion.analysis import analyze_session, evaluate_policy, policy_dynamics, reachable_cycle
from collusion.model import Game

spec = importlib.util.spec_from_file_location(
    "paper_diagnostics", Path(__file__).resolve().parents[1]/"experiments"/"paper_diagnostics.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


def test_memoryless_one_step_loss_matches_stage_loss_with_discount_scaling():
    game = Game(k=0, m=5, discount=0.8)
    policy = np.array([[4], [3]])
    result = diagnostics.one_step_diagnostic(game, policy, 0)
    for player in range(2):
        rival = policy[1-player, 0]
        indices = np.arange(game.m)*game.m+rival if player == 0 else rival*game.m+np.arange(game.m)
        stage = game.rewards[indices, player]
        own = stage[policy[player, 0]]
        own_value = own/(1-game.discount)
        maximum = stage.max()+game.discount*own_value
        expected = (maximum-own_value)/maximum
        assert result["paper_one_step_loss_on_path_by_player"][player] == pytest.approx(expected, abs=1e-12)


def test_on_path_one_step_condition_is_not_full_dynamic_nash():
    # From the learned absorbing state, deviating once is costly. Two successive
    # deviations reach a permanently profitable response to the frozen rival.
    game = SimpleNamespace(n=2, m=2, states=4, k=1, discount=.9,
                           prices=np.array([[1., 2.], [1., 2.]]),
                           rewards=np.array([[1., 1.], [0., 1.], [0., 1.], [2., 1.]]),
                           profit_nash=np.array([0., 0.]), profit_monopoly=np.array([2., 2.]))
    policy = np.array([[0, 0, 0, 0], [0, 0, 1, 1]])
    one_step = diagnostics.one_step_diagnostic(game, policy, 0)
    full = analyze_session(game, policy, 0)
    assert one_step["paper_one_step_no_profitable_deviation"]
    assert one_step["paper_one_step_loss_on_path"] == pytest.approx(0., abs=1e-14)
    assert not full["is_equilibrium"]
    # Player 0: learned value 10, optimal value 18. Player 1's value is always 10.
    assert full["q_loss_on_path"] == pytest.approx(((18-10)/18)/2, abs=1e-9)


def test_summaries_exclude_censored_and_keep_sample_standard_deviation():
    rows = [dict(converged=True, paper_one_step_loss_on_path=.1,
                 paper_one_step_loss_all_states=.2, paper_one_step_no_profitable_deviation=False),
            dict(converged=True, paper_one_step_loss_on_path=.3,
                 paper_one_step_loss_all_states=.4, paper_one_step_no_profitable_deviation=True),
            dict(converged=False, paper_one_step_loss_on_path=10.,
                 paper_one_step_loss_all_states=10., paper_one_step_no_profitable_deviation=False)]
    result = diagnostics.summarize_diagnostics(rows)
    assert result["sessions"] == 3
    assert result["converged"] == 2
    assert result["censored"] == 1
    assert result["paper_one_step_loss_on_path"] == pytest.approx(.2)
    assert result["paper_one_step_loss_on_path_std"] == pytest.approx(np.std([.1, .3], ddof=1))
    assert result["paper_one_step_no_profitable_deviation_frequency"] == .5


def test_reject_multi_firm_diagnostics():
    game = SimpleNamespace(n=3)
    with pytest.raises(ValueError):
        diagnostics.one_step_diagnostic(game, None, 0)


def test_author_compute_qcell_translation_matches_shared_policy_values():
    game = Game(m=3, discount=.85)
    policy = np.array([[2, 1, 0, 1, 0, 2, 0, 2, 1],
                       [2, 2, 1, 0, 1, 1, 2, 0, 0]])
    joint, successor, rewards = policy_dynamics(game, policy)
    values = evaluate_policy(successor, rewards, game.discount)
    _, cycle = reachable_cycle(successor, 0)
    off_path = sorted(set(range(game.states))-set(cycle))
    all_losses = []
    for player in range(2):
        losses = []
        for state in range(game.states):
            candidates = []
            for price in range(game.m):
                action = policy[:, state].copy()
                action[player] = price
                profile = action[0]*game.m+action[1]
                expected = game.rewards[profile, player]+game.discount*values[profile, player]
                reference = diagnostics.author_q_cell_reference(game, policy, state, price, player)
                assert reference == pytest.approx(expected, abs=1e-12)
                candidates.append(reference)
            maximum = max(candidates)
            losses.append((maximum-candidates[policy[player, state]])/abs(maximum))
        all_losses.append(losses)
    diagnosis = diagnostics.one_step_diagnostic(game, policy, 0)
    assert diagnosis["paper_one_step_loss_off_path"] == pytest.approx(np.asarray(all_losses)[:, off_path].mean(), abs=1e-12)
    assert diagnosis["paper_one_step_loss_all_states"] == pytest.approx(np.mean(all_losses), abs=1e-12)


def test_no_off_path_states_means_missing_off_path_loss():
    game = Game(k=0, m=3)
    diagnosis = diagnostics.one_step_diagnostic(game, np.array([[0], [1]]), 0)
    assert diagnosis["paper_one_step_loss_off_path"] is None
