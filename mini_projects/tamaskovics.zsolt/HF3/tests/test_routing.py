from agents.triage import heuristic_domain


def test_heuristic_domain():
    assert heuristic_domain("VPN nem működik") == "it"
    assert heuristic_domain("levelezőlista jogosultság") == "legal"
    assert heuristic_domain("szabadság igény") == "hr"
