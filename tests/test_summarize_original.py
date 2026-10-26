"""Official-format parsing and rounded-input reconstruction checks."""
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "summarize_original", Path(__file__).resolve().parents[1]/"experiments"/"summarize_original.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def test_official_info_parser_preserves_agent_major_cycles_and_state_major_policy(monkeypatch):
    # Two-phase cycle: states (1,2), then (2,1), with an asymmetric policy table.
    text = "\n".join(["1", "1", "1.25", "2", "2 3", "1 2 2 1", ".4 .6 .8 .9",
                      "1 1", "2 1", "1 2", "2 2", ""])
    path = Path("InfoExperiment_1.txt")
    monkeypatch.setattr(Path, "open", lambda self, *args, **kwargs: io.StringIO(text))
    session = list(original.read_original_sessions(path, SimpleNamespace(n=2, m=2, states=4), 1))[0]
    np.testing.assert_array_equal(session["cycle_states"], [1, 2])
    np.testing.assert_array_equal(session["cycle_actions"], [[0, 1], [1, 0]])
    np.testing.assert_allclose(session["printed_profits"], [[.4, .8], [.6, .9]])
    np.testing.assert_array_equal(session["policy"], [[0, 1, 0, 1], [0, 0, 1, 1]])


def test_native_table_reader_keeps_author_numeric_fields_and_rejects_wrong_shapes(monkeypatch):
    path = Path("A_convResults.txt")
    text = "Experiment type avgPrGain sePrGain\n1 O 0.84872 0.11198\n"
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: text)
    result = original.read_native_table(path)
    assert result["avgPrGain"] == .84872
    assert result["type"] == "O"
    text = "Experiment avgPrGain\n1 0.84872 0.2\n"
    with pytest.raises(ValueError, match="column mismatch"):
        original.read_native_table(path)


def test_rounded_author_input_is_used_without_continuous_resolving():
    settings = dict(agents=2, memory=1, prices=15,
                    model=dict(NashP1="1.47293", NashP2="1.47293", CoopP1="1.92498", CoopP2="1.92498",
                               a1="2", a2="2", c1="1", c2="1", a0="0", mu=".25",
                               extend1=".1", extend2=".1", Delta=".95"))
    game = original.reconstruct_original_game(settings)
    np.testing.assert_array_equal(game.price_nash, [1.47293, 1.47293])
    assert game.prices[0, 0] == pytest.approx(1.427725)
    assert game.prices[0, -1] == pytest.approx(1.970185)
    assert game.profit_nash[0] == pytest.approx(.22292806391717349, abs=1e-15)
    assert game.rewards.shape == (225, 2)
