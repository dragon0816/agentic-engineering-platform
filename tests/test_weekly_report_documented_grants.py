"""The grants the preview's README tells an operator to write have to be the
grants the capabilities actually accept.

Documentation drift here is not a typo: a grant that the policy rejects reads
to the operator as a broken install, because the run stops with
`permission_denied` and names nothing. The README's own JSON is therefore
parsed and put through the real policy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from capabilities.runtime import CapabilityGrant, LocalPolicy
from capabilities.weekly_report.handlers import (
    APPLY_SPEC,
    JIRA_SEARCH_SPEC,
    PLAN_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    RESOLVE_WINDOW_SPEC,
)
from common.execution import RequestContext, TraceIdentifiers

README = Path(__file__).resolve().parents[1] / "deploy" / "windows-preview" / "README.md"
#: The five the weekly report runs: four reads and the one write.
SPECS = (
    RESOLVE_WINDOW_SPEC,
    JIRA_SEARCH_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    PLAN_SPEC,
    APPLY_SPEC,
)


def documented_grants() -> tuple[CapabilityGrant, ...]:
    """Every grant the README shows, wherever it shows it: the preview's four
    in one block and the write in its own."""
    blocks = re.findall(r"```json\n(.*?)```", README.read_text(encoding="utf-8"), re.DOTALL)
    grants: list[CapabilityGrant] = []
    for block in blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            # The README also shows fragments of `host.json`, which are not
            # documents on their own.
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        grants.extend(
            CapabilityGrant.model_validate(item)
            for item in items
            if isinstance(item, dict) and "asset" in item
        )
    return tuple(grants)


def context(actor: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor=actor,
        namespace="engineering",
        message="weekly.preview",
        channel="local",
    )


def test_the_readme_documents_a_grant_for_every_capability() -> None:
    """An operator who writes what the README shows can run the whole thing.
    A capability missing from the page is a run that stops without saying
    which grant is absent."""
    documented = {grant.asset.key for grant in documented_grants()}
    assert documented == {spec.identity.key for spec in SPECS}


def test_every_documented_grant_is_one_the_policy_accepts() -> None:
    """The defect this test exists for: the README said only the write needed
    an approval reference, while all five capabilities declare that they need
    one. Following the page produced `permission_denied` at the first step."""
    grants = documented_grants()
    policy = LocalPolicy(grants)
    actor = grants[0].actor
    for spec in SPECS:
        authorization = policy.authorize(context(actor), spec)
        assert authorization.allowed, spec.identity.key


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.identity.key[1])
def test_a_documented_grant_without_its_approval_is_refused(spec: object) -> None:
    """Why the page has to say so: dropping the reference is not a weaker
    grant, it is no grant at all."""
    grants = tuple(grant.model_copy(update={"approval_ref": None}) for grant in documented_grants())
    policy = LocalPolicy(grants)
    for candidate in SPECS:
        assert not policy.authorize(context(grants[0].actor), candidate).allowed
