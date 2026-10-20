"""The Skills that come with the Windows bundle (owner 2026-10-15/16,
`docs/phases/HERMES_SKILL_PACK.md`): AEP's in-use Skills switched on, the
Hermes skill pack switched off, and nothing a person chose is undone by an
update. Coding-agent copies of pack skills follow the Skill's switch. Every
test uses a temporary home and workspace."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_host_wiring import host_json, ready

from agent.skills import SkillManifest, SkillRegistry
from capabilities.business_cards.manifest import CARDS_SKILL
from common.assets import AssetIdentity
from host_runtime import agent_setup, asset_shelf, memory_spaces, skill_packs
from host_runtime.agent_setup import MARKER_FILE, SKILLS, Environment
from host_runtime.assets import personal, shipped
from host_runtime.business_cards_tools import business_cards_tools
from host_runtime.cli import main
from host_runtime.contracts import HostLayout
from host_runtime.host import build_runtime
from scripts.build_windows_preview import HERMES_PACK, copy_hermes_pack

REPO = Path(__file__).resolve().parents[1]
IN_USE = REPO / "deploy" / "windows-preview" / skill_packs.BUNDLE_IN_USE
PACK = REPO / HERMES_PACK
DOCX = AssetIdentity(namespace="hermes", name="docx", version="1.1.0")
KNOWLEDGE = AssetIdentity(namespace="engineering", name="knowledge-query", version="1.0.1")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The bundle's skill folders, laid out as the builder lays them out."""
    root = tmp_path_factory.mktemp("bundle")
    shutil.copytree(IN_USE, root / skill_packs.BUNDLE_IN_USE)
    copy_hermes_pack(PACK, root / skill_packs.BUNDLE_PACK)
    return root


def _file(identity: AssetIdentity) -> str:
    return f"{identity.namespace}__{identity.name}__{identity.version}.json"


def _names(folder: Path) -> set[str]:
    return {path.name for path in folder.glob("*.json")}


def _install(layout: HostLayout, bundle: Path, environment: Environment | None = None) -> None:
    skill_packs.install_bundle(layout, bundle, shipped=shipped(), environment=environment)


def _home(tmp_path: Path, *, aep_for: tuple[str, ...] = ("claude-code",)) -> Environment:
    """A temporary home where AEP's own setup is in the named agents."""
    home = tmp_path / "home"
    environment = Environment(home, {}, which=lambda _: None)
    for agent in aep_for:
        skills_dir = agent_setup.places(agent, environment).skills_dir  # type: ignore[arg-type]
        for name in SKILLS:
            (skills_dir / name).mkdir(parents=True, exist_ok=True)
            (skills_dir / name / MARKER_FILE).write_text(
                json.dumps({"managed_by": "aep", "skill": name, "version": "x"}), encoding="utf-8"
            )
    return environment


def test_in_use_skills_go_on_and_the_hermes_pack_goes_off(tmp_path: Path, bundle: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    _install(layout, bundle)
    active = _names(layout.skills)
    shelved = _names(layout.skills / "disabled")
    shipped_skills = {_file(m.metadata.identity) for m in shipped() if isinstance(m, SkillManifest)}
    in_use = _names(IN_USE / "skills")
    # The newer company Knowledge Skill sets the shipped 1.0.0 aside.
    assert active == (shipped_skills | in_use) - {"company-agent__knowledge-query__1.0.0.json"}
    assert "company-agent__knowledge-query__1.0.0.json" in shelved
    pack = _names(PACK / "manifests")
    assert len(pack) == 51 and pack <= shelved and not pack & active
    workflows = {_file(m.metadata.identity) for m in shipped() if not isinstance(m, SkillManifest)}
    assert _names(layout.workflows) == workflows
    store = skill_packs.store_dir(layout)
    assert {p.name for p in store.iterdir()} == {
        f"hermes-{json.loads(p.read_text(encoding='utf-8'))['metadata']['identity']['name']}"
        for p in (PACK / "manifests").glob("*.json")
    }
    marker = json.loads((store / "hermes-docx" / MARKER_FILE).read_text(encoding="utf-8"))
    assert marker["managed_by"] == "aep" and marker["pack"] == "hermes"
    # Every Skill switched on registers: no two share an alias in a namespace.
    registry = SkillRegistry()
    for path in layout.skills.glob("*.json"):
        registry.register(SkillManifest.model_validate_json(path.read_text(encoding="utf-8")))


def test_the_in_use_knowledge_skills_are_team_owned_and_valid() -> None:
    for path in (IN_USE / "skills").glob("*.json"):
        manifest = SkillManifest.model_validate_json(path.read_text(encoding="utf-8"))
        assert manifest.metadata.owner.type == "team"
        assert manifest.metadata.owner.id == "engineering"
        assert "leo" not in path.read_text(encoding="utf-8").lower()
    engineering = SkillManifest.model_validate_json(
        (IN_USE / "skills" / _file(KNOWLEDGE)).read_text(encoding="utf-8")
    )
    assert engineering.metadata.visibility == "organization"


def test_a_host_starts_with_the_bundled_skills(tmp_path: Path, bundle: Path) -> None:
    config, layout = ready(tmp_path)
    _install(layout, bundle)
    runtime = build_runtime(config, layout=layout)
    offered = {
        m.metadata.identity for m in runtime.agent.gateway.router.commands.skills.manifests()
    }
    assert KNOWLEDGE in offered and DOCX not in offered


def test_business_cards_are_on_by_default_and_the_hermes_copy_stays_off(
    tmp_path: Path, bundle: Path
) -> None:
    """Owner 2026-10-20: the native business-cards Skill is switched on in every
    install, and its tools are offered; the Hermes pack's business-cards Skill
    stays a switched-off backup (docs/phases/BUSINESS_CARDS.md)."""
    config, layout = ready(tmp_path)
    _install(layout, bundle)
    hermes = AssetIdentity(namespace="hermes", name="business-cards", version="1.0.0")
    assert (layout.skills / _file(CARDS_SKILL)).exists()
    assert (layout.skills / "disabled" / _file(hermes)).exists()
    assert not (layout.skills / _file(hermes)).exists()
    runtime = build_runtime(config, layout=layout)
    offered = {
        m.metadata.identity for m in runtime.agent.gateway.router.commands.skills.manifests()
    }
    assert CARDS_SKILL in offered and hermes not in offered
    names = {item.tool.name for item in business_cards_tools(runtime.agent.gateway)}
    assert {"cards__add_card", "cards__org_chart", "cards__set_status", "cards__undo"} <= names


def test_an_update_keeps_what_the_person_chose(tmp_path: Path, bundle: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    _install(layout, bundle)
    # Switched off, switched on, removed, edited.
    asset_shelf.switch_off(layout, "skill", KNOWLEDGE)
    asset_shelf.switch_on(layout, "skill", DOCX)
    removed = AssetIdentity(namespace="hermes", name="arxiv", version="1.0.0")
    asset_shelf.remove(layout, "skill", removed, now=datetime.now(UTC), actor="someone")
    coding = layout.skills / "engineering__coding__1.8.0.json"
    coding.write_text(coding.read_text(encoding="utf-8") + " ", encoding="utf-8")
    edited = coding.read_text(encoding="utf-8")

    report = skill_packs.install_bundle(layout, bundle, shipped=shipped())

    assert report.switched_on == [] and report.switched_off == []
    assert not (layout.skills / _file(KNOWLEDGE)).exists()
    assert (layout.skills / "disabled" / _file(KNOWLEDGE)).exists()
    assert (layout.skills / _file(DOCX)).exists()
    assert not (layout.skills / "disabled" / _file(DOCX)).exists()
    assert not (layout.skills / _file(removed)).exists()
    assert not (layout.skills / "disabled" / _file(removed)).exists()
    assert any("you removed it" in line for line in report.lines)
    assert coding.read_text(encoding="utf-8") == edited


def _skill(identity: AssetIdentity, alias: str) -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": identity.model_dump(),
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "organization",
                "lifecycle": "published",
            },
            "alias": alias,
            "instructions": "Do the thing.",
        }
    )


def test_a_new_version_respects_the_earlier_ones_state(tmp_path: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    old = AssetIdentity(namespace="lab", name="check", version="1.0.0")
    new = AssetIdentity(namespace="lab", name="check", version="1.1.0")
    skill_packs.install(layout, switched_on=[_skill(old, "check")])
    asset_shelf.switch_off(layout, "skill", old)
    skill_packs.install(layout, switched_on=[_skill(new, "check")])
    assert (layout.skills / "disabled" / _file(new)).exists()
    assert not any(layout.skills.glob("*.json"))
    # With the earlier one on, the new one goes on and sets it aside.
    other = HostLayout.under(tmp_path / "other")
    skill_packs.install(other, switched_on=[_skill(old, "check")])
    skill_packs.install(other, switched_on=[_skill(new, "check")])
    assert _names(other.skills) == {_file(new)}
    assert _names(other.skills / "disabled") == {_file(old)}
    # An older version never goes on over a newer one.
    skill_packs.install(
        other,
        switched_on=[
            _skill(AssetIdentity(namespace="lab", name="check", version="0.9.0"), "check")
        ],
    )
    assert _names(other.skills) == {_file(new)}


def test_an_alias_already_in_use_keeps_the_new_skill_off(tmp_path: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    first = AssetIdentity(namespace="lab", name="first", version="1.0.0")
    second = AssetIdentity(namespace="lab", name="second", version="1.0.0")
    report = skill_packs.install(
        layout, switched_on=[_skill(first, "same"), _skill(second, "same")]
    )
    assert _names(layout.skills) == {_file(first)}
    assert _names(layout.skills / "disabled") == {_file(second)}
    assert any("alias" in line for line in report.lines)


def test_switching_a_pack_skill_on_copies_it_to_the_coding_agents(
    tmp_path: Path, bundle: Path
) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    environment = _home(tmp_path, aep_for=("claude-code",))
    _install(layout, bundle, environment)
    claude = agent_setup.places("claude-code", environment).skills_dir
    copilot = agent_setup.places("copilot", environment).skills_dir
    # Installed switched off: nothing in the agents' folders yet.
    assert not (claude / "hermes-docx").exists()

    moved = asset_shelf.switch_on(layout, "skill", DOCX, environment)
    assert (claude / "hermes-docx" / "SKILL.md").is_file()
    assert (claude / "hermes-docx" / MARKER_FILE).is_file()
    assert any("hermes-docx" in line for line in moved.agent_lines)
    # Copilot has no AEP setup here (-NoAgentSkills, or removed): untouched.
    assert not copilot.exists()

    asset_shelf.switch_off(layout, "skill", DOCX, environment)
    assert not (claude / "hermes-docx").exists()

    # A same-named folder of the person's own is never replaced or removed.
    own = claude / "hermes-docx"
    own.mkdir()
    (own / "SKILL.md").write_text("mine", encoding="utf-8")
    moved = asset_shelf.switch_on(layout, "skill", DOCX, environment)
    assert (own / "SKILL.md").read_text(encoding="utf-8") == "mine"
    assert any("kept your own skill" in line for line in moved.agent_lines)
    shutil.rmtree(own)

    # An update refreshes the copies of switched-on pack skills only.
    _install(layout, bundle, environment)
    assert (claude / "hermes-docx" / "SKILL.md").is_file()
    assert not (claude / "hermes-pdf").exists()

    # Removing the Skill takes the copy out; removing AEP's setup takes all.
    asset_shelf.remove(
        layout, "skill", DOCX, now=datetime.now(UTC), actor="someone", environment=environment
    )
    assert not (claude / "hermes-docx").exists()
    asset_shelf.switch_on(
        layout, "skill", AssetIdentity(namespace="hermes", name="pdf", version="1.1.0"), environment
    )
    assert (claude / "hermes-pdf").is_dir()
    agent_setup.remove("claude-code", environment)
    assert not (claude / "hermes-pdf").exists()


def test_without_agent_skills_nothing_reaches_the_agents(tmp_path: Path, bundle: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    environment = _home(tmp_path)
    _install(layout, bundle, None)
    asset_shelf.switch_on(layout, "skill", DOCX)
    skill_packs.install_bundle(layout, bundle, shipped=shipped(), environment=None)
    claude = agent_setup.places("claude-code", environment).skills_dir
    assert not (claude / "hermes-docx").exists()


def test_the_cli_installs_the_bundle(
    tmp_path: Path, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    code = main(
        [
            "assets",
            "--config",
            str(path),
            "install-bundled",
            "--bundle",
            str(bundle),
            "--no-agent-skills",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Installed switched off" in out
    assert (layout.skills / "disabled" / _file(DOCX)).exists()
    assert (layout.skills / _file(KNOWLEDGE)).exists()
    # Extra switched-off sources (this PC's internal skills) without the shipped ones.
    extra = tmp_path / "extra"
    (extra / "manifests").mkdir(parents=True)
    lab = AssetIdentity(namespace="hermes", name="lab-only", version="1.0.0")
    (extra / "manifests" / _file(lab)).write_text(
        _skill(lab, "lab_only").model_dump_json(), encoding="utf-8"
    )
    code = main(
        [
            "assets",
            "--config",
            str(path),
            "install-bundled",
            "--no-shipped",
            "--off",
            str(extra / "manifests"),
            "--no-agent-skills",
        ]
    )
    assert code == 0
    assert (layout.skills / "disabled" / _file(lab)).exists()


def test_the_installer_and_manual_describe_the_bundled_skills() -> None:
    preview = REPO / "deploy" / "windows-preview"
    installer = (preview / "install.ps1").read_text(encoding="utf-8")
    assert '"install-bundled", "--bundle", $BundleRoot' in installer
    assert '$BundledArguments += "--no-agent-skills"' in installer
    guide = (preview / "USER_GUIDE.zh-TW.md").read_text(encoding="utf-8")
    assert "### 13.4 安裝包附帶的 Skills" in guide
    assert "Switch on" in guide and "hermes\\NOTICE.md" in guide


def test_a_folder_from_another_pack_is_not_replaced(tmp_path: Path) -> None:
    """This PC's own internal copy of a skill (pack `hermes-personal`) keeps
    its store folder when the bundle brings a scrubbed one of the same name."""
    layout = HostLayout.under(tmp_path / "workspace")
    mine = tmp_path / "mine" / "hermes-business-cards"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("internal", encoding="utf-8")
    skill_packs.install(layout, agent_stores=[(mine.parent, "hermes-personal")])
    report = skill_packs.install(
        layout, agent_stores=[(PACK / "skills" / "vendor", skill_packs.BUNDLE_PACK)]
    )
    stored = skill_packs.store_dir(layout) / "hermes-business-cards" / "SKILL.md"
    assert stored.read_text(encoding="utf-8") == "internal"
    assert any("from the hermes-personal pack" in line for line in report.lines)


# --- the weekly report is personal, not bundled (owner 2026-10-16) ---------------

WEEKLY_FILES = {
    "skills": "engineering__weekly-report__2.0.0.json",
    "workflows": "engineering__sde-weekly-report__1.0.0.json",
}


def test_the_weekly_report_is_personal_and_not_shipped() -> None:
    shipped_names = {item.metadata.identity.name for item in shipped()}
    personal_names = {item.metadata.identity.name for item in personal()}
    assert personal_names == {"weekly-report", "sde-weekly-report"}
    assert not shipped_names & personal_names
    assert not any("weekly" in name for name in shipped_names)
    # Not shipped, so a colleague may remove one an earlier bundle installed.
    for item in personal():
        kind = "skill" if isinstance(item, SkillManifest) else "workflow"
        assert not asset_shelf.is_shipped(kind, item.metadata.identity)


def _install_cli(path: Path, bundle: Path, *extra: str) -> int:
    return main(
        [
            "assets",
            "--config",
            str(path),
            "install-bundled",
            "--bundle",
            str(bundle),
            "--no-agent-skills",
            *extra,
        ]
    )


def test_a_colleague_install_gets_no_weekly_report_and_the_owner_can_ask_for_it(
    tmp_path: Path, bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AEP_INCLUDE_PERSONAL_ASSETS", raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    assert _install_cli(path, bundle) == 0
    assert not (layout.skills / WEEKLY_FILES["skills"]).exists()
    assert not (layout.workflows / WEEKLY_FILES["workflows"]).exists()
    assert not any("weekly-report" in p.name for p in layout.workspace_root.rglob("*.json"))
    # The owner's computer: the flag or the environment variable.
    assert _install_cli(path, bundle, "--include-personal") == 0
    assert (layout.skills / WEEKLY_FILES["skills"]).exists()
    assert (layout.workflows / WEEKLY_FILES["workflows"]).exists()
    other_config, other = ready(tmp_path / "owner")
    other_path = host_json(tmp_path / "owner", other_config)
    monkeypatch.setenv("AEP_INCLUDE_PERSONAL_ASSETS", "1")
    assert _install_cli(other_path, bundle) == 0
    assert (other.workflows / WEEKLY_FILES["workflows"]).exists()


def test_an_update_leaves_earlier_weekly_assets_alone_and_never_brings_them_back(
    tmp_path: Path, bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A colleague who got the weekly report from an earlier bundle keeps it
    as it is (an update removes nothing); once they remove it, no update
    adds it again."""
    monkeypatch.delenv("AEP_INCLUDE_PERSONAL_ASSETS", raising=False)
    config, layout = ready(tmp_path)
    path = host_json(tmp_path, config)
    # What an earlier bundle installed, edited since by the person.
    skill_packs.install(layout, switched_on=personal())
    workflow = layout.workflows / WEEKLY_FILES["workflows"]
    workflow.write_text(workflow.read_text(encoding="utf-8") + " ", encoding="utf-8")
    before = workflow.read_bytes()
    assert _install_cli(path, bundle) == 0
    assert workflow.read_bytes() == before
    assert (layout.skills / WEEKLY_FILES["skills"]).exists()
    # Removed by the person (allowed: it is not shipped), then updated twice.
    for kind, name in (("skill", "weekly-report"), ("workflow", "sde-weekly-report")):
        identity = next(i.metadata.identity for i in personal() if i.metadata.identity.name == name)
        asset_shelf.remove(layout, kind, identity, now=datetime.now(UTC), actor="me")  # type: ignore[arg-type]
    assert _install_cli(path, bundle) == 0
    assert _install_cli(path, bundle) == 0
    assert not (layout.skills / WEEKLY_FILES["skills"]).exists()
    assert not workflow.exists()
    assert not list((layout.skills / "disabled").glob("*weekly-report*"))


# -- a shipped manifest changed after it was installed (live check 2026-10-21) --


def _stale_cards() -> bytes:
    """The business-cards Skill as an earlier install wrote it: same identity,
    no memory_spaces (installed on 10/20, before M1)."""
    (manifest,) = [m for m in shipped() if m.metadata.identity == CARDS_SKILL]
    old = manifest.model_copy(update={"memory_spaces": (), "instructions": "Old procedure."})
    return (json.dumps(old.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _shipped_cards() -> bytes:
    (manifest,) = [m for m in shipped() if m.metadata.identity == CARDS_SKILL]
    return (
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def test_a_stale_shipped_manifest_from_before_the_ledger_is_refreshed(
    tmp_path: Path, bundle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config, layout = ready(tmp_path)
    _install(layout, bundle)
    cards = layout.skills / _file(CARDS_SKILL)
    # An install from before the ledger: the old bytes, and no record.
    cards.write_bytes(_stale_cards())
    (layout.workspace_root / skill_packs.LEDGER).unlink()
    assert memory_spaces.manager_states(layout)["engineering/business-cards"] == "outdated"
    path = host_json(tmp_path, config)
    args = ["assets", "--config", str(path), "install-bundled", "--bundle", str(bundle)]
    assert main([*args, "--no-agent-skills"]) == 0
    out = capsys.readouterr().out
    assert "updated skill engineering/business-cards@1.0.0" in out
    assert cards.read_bytes() == _shipped_cards()
    manifest = SkillManifest.model_validate_json(cards.read_text(encoding="utf-8"))
    assert manifest.memory_spaces
    assert memory_spaces.manager_states(layout)["engineering/business-cards"] == "on"
    # The earlier bytes are kept, in case someone had edited them.
    (backup,) = (layout.workspace_root / skill_packs.REPLACED).rglob(_file(CARDS_SKILL))
    assert backup.read_bytes() == _stale_cards()
    assert backup.parent.name == "skills"
    # Idempotent: a second run changes nothing and keeps no further copy.
    ledger = skill_packs.read_ledger(layout)
    again = skill_packs.install_bundle(layout, bundle, shipped=shipped())
    assert again.updated == [] and again.switched_on == [] and again.switched_off == []
    assert skill_packs.read_ledger(layout) == ledger
    assert len(list((layout.workspace_root / skill_packs.REPLACED).rglob("*.json"))) == 1
    assert cards.read_bytes() == _shipped_cards()


def test_a_refresh_keeps_a_switched_off_skill_off(tmp_path: Path, bundle: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    _install(layout, bundle)
    asset_shelf.switch_off(layout, "skill", CARDS_SKILL)
    shelved = layout.skills / "disabled" / _file(CARDS_SKILL)
    # AEP wrote the older content (recorded), and nobody changed it since.
    shelved.write_bytes(_stale_cards())
    ledger = skill_packs.read_ledger(layout)
    ledger[f"skill/{_file(CARDS_SKILL)}"] = skill_packs._digest(_stale_cards())
    skill_packs._write_ledger(layout, ledger)

    report = skill_packs.install_bundle(layout, bundle, shipped=shipped())

    assert report.updated == ["skill engineering/business-cards@1.0.0"]
    assert report.switched_on == [] and report.switched_off == []
    assert shelved.read_bytes() == _shipped_cards()
    assert not (layout.skills / _file(CARDS_SKILL)).exists()
    # Recorded, so no backup copy was needed.
    assert not (layout.workspace_root / skill_packs.REPLACED).exists()
    assert memory_spaces.manager_states(layout)["engineering/business-cards"] == "off"


def test_an_edited_or_own_asset_is_never_overwritten(tmp_path: Path, bundle: Path) -> None:
    layout = HostLayout.under(tmp_path / "workspace")
    own = AssetIdentity(namespace="lab", name="mine", version="1.0.0")
    skill_packs.install(layout, switched_on=[_skill(own, "mine")])
    mine = layout.skills / _file(own)
    mine.write_text(mine.read_text(encoding="utf-8").replace("Do the thing.", "Mine."), "utf-8")
    own_bytes = mine.read_bytes()
    _install(layout, bundle)
    cards = layout.skills / _file(CARDS_SKILL)
    # Edited on this PC after AEP installed it: the ledger says AEP wrote other bytes.
    edited = cards.read_bytes().replace(b"Business cards and org chart", b"My cards")
    cards.write_bytes(edited)

    report = skill_packs.install_bundle(layout, bundle, shipped=shipped())

    assert report.updated == []
    assert cards.read_bytes() == edited
    assert any(
        "business-cards@1.0.0: changed on this PC since it was installed" in line
        for line in report.lines
    )
    assert mine.read_bytes() == own_bytes
    assert not (layout.workspace_root / skill_packs.REPLACED).exists()


def test_a_shipped_identity_taken_from_the_platform_is_left_as_it_is(
    tmp_path: Path, bundle: Path
) -> None:
    from common.authorization import DeviceAssetSelection, DeviceAuthorization

    layout = HostLayout.under(tmp_path / "workspace")
    _install(layout, bundle)
    cards = layout.skills / _file(CARDS_SKILL)
    cards.write_bytes(_stale_cards())
    (layout.workspace_root / skill_packs.LEDGER).unlink()
    now = datetime.now(UTC)
    decided = DeviceAuthorization(
        bridge_id="bridge-a",
        issued_at=now,
        selections=(
            DeviceAssetSelection(
                bridge_id="bridge-a", actor="alice", kind="skill", asset=CARDS_SKILL, decided_at=now
            ),
        ),
    )
    layout.platform_selections.write_text(decided.model_dump_json(), encoding="utf-8")

    report = skill_packs.install_bundle(layout, bundle, shipped=shipped())

    assert report.updated == [] and cards.read_bytes() == _stale_cards()
    assert any("taken from the Shared Platform" in line for line in report.lines)
