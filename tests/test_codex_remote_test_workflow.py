from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codex-remote-test-fix.yml"
ISSUE_TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "hermes-remote-test-failure.md"
DOCUMENTATION = ROOT / "docs" / "remote-testing-codex-loop.md"


def test_remote_test_workflow_has_a_narrow_trigger_and_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "issues:\n    types: [labeled]" in text
    assert "github.event.label.name == 'codex-fix'" in text
    assert "pull_request_target" not in text
    assert "permissions: {}" in text
    assert "persist-credentials: false" in text
    assert "openai/codex-action@v1" in text
    assert 'permission-profile: ":workspace"' in text
    assert "safety-strategy: drop-sudo" in text
    assert 'allow-users: "*"' not in text
    assert "allow-bots: true" not in text
    assert "OPENAI_API_KEY" in text


def test_remote_test_workflow_separates_codex_from_issue_write_access() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    codex_job = text.split("  analyze:", 1)[1].split("  comment:", 1)[0]
    comment_job = text.split("  comment:", 1)[1]

    assert "contents: read" in codex_job
    assert "issues: read" in codex_job
    assert "issues: write" not in codex_job
    assert "issues: write" in comment_job
    assert "OPENAI_API_KEY" not in comment_job
    assert "github.rest.issues.createComment" in comment_job


def test_remote_test_workflow_prepares_declared_python_test_environment() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    codex_job = text.split("  analyze:", 1)[1].split("  comment:", 1)[0]

    assert "actions/setup-python@v5" in codex_job
    assert 'python-version: "3.12"' in codex_job
    assert 'python -m pip install -e ".[dev,office]"' in codex_job
    assert codex_job.index("actions/setup-python@v5") < codex_job.index("openai/codex-action@v1")
    assert codex_job.index('python -m pip install -e ".[dev,office]"') < codex_job.index(
        "openai/codex-action@v1"
    )


def test_remote_test_contract_is_documented_and_templated() -> None:
    template = ISSUE_TEMPLATE.read_text(encoding="utf-8")
    documentation = DOCUMENTATION.read_text(encoding="utf-8")
    required_fields = (
        "Commit:",
        "Build:",
        "Machine:",
        "Test:",
        "Expected:",
        "Actual:",
        "Failure Stage:",
        "Reproducible:",
        "Artifacts:",
    )

    for field in required_fields:
        assert field in template
        assert field in documentation

    for heading in (
        "Codex Analysis",
        "Root Cause",
        "Changes",
        "Local Test Result",
        "Next Action",
    ):
        assert heading in documentation
