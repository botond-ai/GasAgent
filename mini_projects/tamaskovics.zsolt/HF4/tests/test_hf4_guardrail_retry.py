from tools.retry import with_retry
from agents.guardrail import validate_plan
from app.state import KRState


def test_with_retry_eventually_succeeds():
    n = {"i": 0}
    def fn():
        n["i"] += 1
        if n["i"] < 3:
            raise RuntimeError("fail")
        return "ok"
    assert with_retry(fn, attempts=5) == "ok"
    assert n["i"] == 3


def test_guardrail_blocks_invalid_plan_for_route():
    # rag_only route cannot include open_meteo
    assert validate_plan("rag_only", ["open_meteo"]) is False
    assert validate_plan("rag_only", ["rag"]) is True


def test_state_has_run_id():
    s = KRState(query="x")
    assert s.run_id
