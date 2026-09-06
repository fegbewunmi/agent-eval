from app.adapters.stub_agent.adapter import StubAgentAdapter


def test_matches_known_keyword_to_root_cause():
    result = StubAgentAdapter().execute(
        {"alert": "disk usage at 95% on web-01", "hosts": ["web-01"]}, {}
    )
    assert result.status == "success"
    assert result.structured_output["root_cause"] == "disk_exhaustion"
    assert len(result.tool_calls) == 2
    assert [tc.tool_name for tc in result.tool_calls] == ["fetch_metrics", "fetch_logs"]


def test_unmatched_alert_returns_unknown():
    result = StubAgentAdapter().execute(
        {"alert": "checkout is flaky", "hosts": ["checkout"]}, {}
    )
    assert result.structured_output["root_cause"] == "unknown"


def test_inject_failure_error_is_caught_and_normalized():
    result = StubAgentAdapter().execute(
        {"alert": "cpu spike", "hosts": ["db-01"], "inject_failure": "error"}, {}
    )
    assert result.status == "error"
    assert result.error is not None
    assert "simulated agent failure" in result.error.message


def test_inject_failure_wrong_answer_does_not_error_but_is_wrong():
    result = StubAgentAdapter().execute(
        {"alert": "disk usage at 98% on web-05", "hosts": ["web-05"], "inject_failure": "wrong_answer"}, {}
    )
    assert result.status == "success"
    assert result.structured_output["root_cause"] == "unknown"
