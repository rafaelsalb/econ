from econ.diagnostics import Defect
from econ.loop import _decide, _modeler_view
from econ.specs import hash_card, load_card, validate_card


def test_card_is_valid():
    card = load_card("new_keynesian")
    assert validate_card(card) == []


def test_card_hash_stable():
    h1 = hash_card("new_keynesian")
    h2 = hash_card("new_keynesian")
    assert h1 == h2
    assert len(h1) == 64


def test_gate_clean_pass():
    assert _decide([], 1, 3)["status"] == "PASS"


def test_gate_core_failure_revises():
    d = [Defect("D5", "high", "core", {"target": "ipca_12m", "horizon": 12})]
    out = _decide(d, 1, 3)
    assert out["status"] == "REVISE"


def test_gate_core_failure_rejects_at_last_round():
    d = [Defect("D5", "high", "core", {"target": "ipca_12m", "horizon": 12})]
    assert _decide(d, 3, 3)["status"] == "REJECTED"


def test_gate_gdp_defect_selects_r2():
    d = [Defect("D5", "medium", "gdp", {"target": "gdp_qq", "horizon": 1})]
    out = _decide(d, 1, 3)
    assert out["status"] == "REVISE"
    assert out["next"] == "R2"


def test_gate_selic_defect_selects_r3():
    d = [Defect("D5", "medium", "selic", {"target": "selic", "horizon": 12})]
    out = _decide(d, 2, 3)
    assert out["next"] == "R3"


def test_gate_aux_limitation_after_ladder():
    d = [Defect("D5", "medium", "selic", {"target": "selic", "horizon": 12})]
    assert _decide(d, 3, 3)["status"] == "PASS_WITH_LIMITATIONS"


def test_gate_medium_defects_pass_with_limitations():
    d = [Defect("D4", "medium", "autocorrelation", {"equation": "taylor"})]
    assert _decide(d, 1, 3)["status"] == "PASS_WITH_LIMITATIONS"


def test_gate_high_defect_blocks():
    d = [Defect("D3", "high", "leak", {})]
    assert _decide(d, 1, 3)["status"] == "REVISE"
    assert _decide(d, 3, 3)["status"] == "REJECTED"


def test_modeler_view_redacts_scores():
    d = [
        Defect(
            "D5",
            "medium",
            "gdp_qq h=1 loses to random walk (Theil U=1.164)",
            {"target": "gdp_qq", "horizon": 1, "theil_u": 1.164},
        )
    ]
    view = _modeler_view(d)[0]
    assert view["evidence"] == {"target": "gdp_qq", "horizon": 1, "gate": "fail"}
    assert "1.164" not in view["message"]
