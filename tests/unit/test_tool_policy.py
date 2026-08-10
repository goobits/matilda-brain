"""Tests for centralized tool safety and approval policy."""

import ipaddress

import pytest

from matilda_brain.core.types import RiskLevel
from matilda_brain.tools.executor import ToolExecutor
from matilda_brain.tools.policy import ExecutionConfig, InputSanitizer, ToolPolicy


class TestToolPolicy:
    def test_file_roots_are_explicitly_enforced(self, tmp_path):
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()
        allowed_file = allowed_root / "file.txt"
        outside_file = tmp_path / "outside.txt"

        assert InputSanitizer.sanitize_path(str(allowed_file), [allowed_root]) == allowed_file
        with pytest.raises(ValueError, match="outside allowed roots"):
            InputSanitizer.sanitize_path(str(outside_file), [allowed_root])

    def test_resolved_private_address_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            InputSanitizer,
            "_resolve_host",
            staticmethod(lambda hostname, port: {ipaddress.ip_address("10.0.0.10")}),
        )

        with pytest.raises(ValueError, match="not allowed"):
            InputSanitizer.validate_url_target("https://example.com")

    def test_python_policy_allows_computation_but_blocks_host_capabilities(self):
        ToolPolicy.validate_python("import math\nprint(math.sqrt(16))")

        for code in ("import os", "open('secret.txt')", "print((1).__class__)"):
            with pytest.raises(ValueError, match="not allowed"):
                ToolPolicy.validate_python(code)

    def test_risk_classification_is_action_aware(self):
        policy = ToolPolicy(ExecutionConfig(require_approval=True))

        assert policy.risk_level("read_file", {}) == RiskLevel.LOW
        assert policy.risk_level("http_request", {"method": "GET"}) == RiskLevel.MEDIUM
        assert policy.risk_level("http_request", {"method": "POST"}) == RiskLevel.HIGH
        assert policy.risk_level("write_file", {}) == RiskLevel.HIGH

    def test_proposals_redact_credentials(self):
        policy = ToolPolicy(ExecutionConfig(require_approval=True))
        proposal = policy.proposal(
            "http_request",
            {"method": "POST", "headers": {"Authorization": "Bearer secret"}, "api_key": "secret"},
        )

        assert proposal.params["headers"]["Authorization"] == "***"
        assert proposal.params["api_key"] == "***"

    @pytest.mark.asyncio
    async def test_high_risk_tool_returns_proposal_until_approved(self, tmp_path):
        target = tmp_path / "approved.txt"
        executor = ToolExecutor(
            ExecutionConfig(
                allowed_file_roots=[tmp_path],
                require_approval=True,
                approval_threshold=RiskLevel.HIGH,
                max_retries=1,
            )
        )

        proposed = await executor.execute_tool("write_file", {"file_path": str(target), "content": "safe"})

        assert not proposed.succeeded
        assert proposed.proposal is not None
        assert proposed.proposal.risk_level == RiskLevel.HIGH
        assert not target.exists()
        assert proposed.to_dict()["proposal"]["risk_level"] == "high"

        model_claimed_approval = await executor.execute_tools(
            [{"name": "write_file", "arguments": {"file_path": str(target), "content": "safe"}, "approved": True}]
        )
        assert model_claimed_approval.calls[0].proposal is not None
        assert not target.exists()

        approved = await executor.execute_tool(
            "write_file",
            {"file_path": str(target), "content": "safe"},
            approved=True,
        )

        assert approved.succeeded
        assert target.read_text() == "safe"
