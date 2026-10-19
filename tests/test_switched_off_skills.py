"""A Skill that is installed but switched off is described as such to the
Gateway model, never as missing (live test 2026-10-20: the model offered to
"install" hermes/business-cards and asked for its name and version)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from test_bundled_skills import _install, bundle  # noqa: F401 - the bundle fixture
from test_gateway import _host_gateway, _text, request
from test_host_wiring import ready

from host_runtime.host import build_runtime
from models.contracts import ModelMessage


def _system(built: object) -> str:
    model = built.router.model  # type: ignore[attr-defined]
    return str(model.calls[-1].messages[0].text)


def test_the_model_is_told_which_skills_are_switched_off_and_where_to_switch_them_on() -> None:
    built, model = _host_gateway([], [_text("ok")])
    built.switched_off_skills = lambda: ("hermes/business-cards", "hermes/docx")
    asyncio.run(built.converse(request("存名片"), (ModelMessage(role="user", text="存名片"),)))
    system = model.calls[0].messages[0].text
    assert "hermes/business-cards, hermes/docx" in system
    assert "installed but switched off" in system
    assert "Agent Web > Capabilities" in system
    assert "never offer to install" in system


def test_no_switched_off_skills_add_nothing_and_a_switched_on_name_is_not_listed() -> None:
    built, model = _host_gateway([], [_text("ok"), _text("ok")])
    asyncio.run(built.converse(request("go"), (ModelMessage(role="user", text="go"),)))
    assert "switched off" not in model.calls[0].messages[0].text
    on = built.router.commands.skills.manifests()
    assert on, "the test gateway has a Skill switched on"
    identity = on[0].metadata.identity
    built.switched_off_skills = lambda: (f"{identity.namespace}/{identity.name}",)
    asyncio.run(built.converse(request("go"), (ModelMessage(role="user", text="go"),)))
    # Another version of it is switched on: it is not "switched off".
    assert "switched off" not in model.calls[1].messages[0].text


def test_the_host_lists_its_switched_off_skills_by_name(
    tmp_path: Path,
    bundle: Path,  # noqa: F811
) -> None:
    config, layout = ready(tmp_path)
    _install(layout, bundle)
    runtime = build_runtime(config, layout=layout)
    gateway = runtime.agent.gateway
    assert gateway.switched_off_skills is not None
    names = list(gateway.switched_off_skills())
    assert "hermes/business-cards" in names
    # Names only: no versions.
    assert all("@" not in name and name.count("/") == 1 for name in names)
