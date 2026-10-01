from pathlib import Path

from validation.contracts import DeploymentArtifact

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hermes-deployment-company-agent.yml"
DOCUMENTATION = ROOT / "docs" / "deployment-validation-loop.md"


def test_deployment_artifact_pins_a_successful_build_to_one_commit() -> None:
    artifact = DeploymentArtifact(
        repository="dragon0816/agentic-engineering-platform",
        package_commit="a" * 40,
        workflow_run_id=123,
        artifact_id=456,
        artifact_name="aep-windows-preview-" + "a" * 40,
    )

    assert artifact.artifact_name.endswith(artifact.package_commit)
    assert artifact.model_dump(mode="json")["workflow_run_id"] == 123


def test_deployment_artifact_rejects_a_name_for_another_commit() -> None:
    try:
        DeploymentArtifact(
            repository="dragon0816/agentic-engineering-platform",
            package_commit="a" * 40,
            workflow_run_id=123,
            artifact_id=456,
            artifact_name="aep-windows-preview-" + "b" * 40,
        )
    except ValueError as error:
        assert "package commit" in str(error)
    else:  # pragma: no cover - makes the required failure explicit
        raise AssertionError("artifact for another commit was accepted")


def test_company_agent_deployment_workflow_is_narrow_and_machine_readable() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert "Platform verification" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "HERMES_DEPLOYMENT_BRIDGE" in text
    assert "HERMES_DEPLOYMENT_ACTOR" in text
    assert 'test_profile: "aep-company-agent-integration-v1"' in text
    assert 'action: "install_and_company_agent_integration"' in text
    assert 'schema: "hermes-validation/v1"' in text
    assert "aep-windows-preview-${commit}" in text
    assert 'name: "personal-proof-fixture-read"' in text
    assert 'name: "draft"' in text
    assert 'name: "ask"' in text
    assert 'model_routing: "hermes-validation-loopback"' in text
    assert 'name: "company-agent-guide"' in text
    assert 'profile_path: "validation/company-agent-integration-v1/profile.json"' in text
    assert 'namespace: "platform", name: "filesystem.read"' not in text
    assert "github.rest.actions.listWorkflowRunArtifacts" in text
    assert "github.rest.issues.createComment" in text
    assert "source_issue: issue.data.number" in text
    assert "Owner download and manual test" in text
    assert "Personal Agent + Bridge artifact" in text
    assert "run.html_url" in text
    assert "START-HERE.md" in text
    assert text.index("github.rest.issues.createComment") < text.index(
        "github.rest.issues.addLabels"
    )
    assert "hermes-preflight-requested" in text
    assert "github.rest.pulls.merge" not in text
    assert "actions/checkout" not in text


def test_deployment_loop_documentation_explains_the_fixed_company_profile() -> None:
    text = DOCUMENTATION.read_text(encoding="utf-8")

    for value in (
        "personal.proof",
        "workflow.draft",
        "knowledge.ask",
        "aep-company-agent-integration-v1",
        "HERMES_DEPLOYMENT_BRIDGE",
        "HERMES_DEPLOYMENT_ACTOR",
        "artifact_id",
        "package_commit",
        "does not execute Issue text",
    ):
        assert value in text
