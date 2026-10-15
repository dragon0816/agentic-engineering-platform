"""AEP for the person's own coding agents, by default (owner 2026-10-15).

`docs/phases/EXTERNAL_AUTHORING.md` "Default user-level setup". Every test
uses a temporary home: the real ~/.claude, ~/.codex and ~/.copilot are never
read or written.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from host_runtime import agent_setup
from host_runtime.agent_setup import (
    ASSISTANT_SERVER,
    AUTHORING_SERVER,
    MARKER_FILE,
    SKILLS,
    Environment,
    Launch,
    apply,
    bundle_version,
    install,
    remove,
    skill_text,
    status,
)
from host_runtime.cli import main

PYTHON = "C:/aep/.venv/Scripts/python.exe"


def env(tmp_path: Path, *found: str, **variables: str) -> Environment:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return Environment(home, variables, which=lambda name: f"C:/bin/{name}.exe"
                       if name in found else None)


def launch(tmp_path: Path, python: str = PYTHON) -> Launch:
    return Launch(python, tmp_path / "host.json")


def backups(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.aep-backup-*"))


def test_claude_code_gets_skills_and_both_servers_beside_its_own(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude")
    home = environment.home
    own = {"numStartups": 7, "mcpServers": {"github": {"type": "http", "url": "https://x"}}}
    (home / ".claude.json").write_text(json.dumps(own), encoding="utf-8")
    first = install("claude-code", environment, launch(tmp_path))
    assert first.changed and len(first.backups) == 1
    for name in SKILLS:
        folder = home / ".claude" / "skills" / name
        assert (folder / "SKILL.md").read_text(encoding="utf-8") == skill_text(name)
        marker = json.loads((folder / MARKER_FILE).read_text(encoding="utf-8"))
        assert marker == {"managed_by": "aep", "skill": name, "version": bundle_version()}
    config = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert config["numStartups"] == 7 and config["mcpServers"]["github"] == own["mcpServers"][
        "github"]
    authoring = config["mcpServers"][AUTHORING_SERVER]
    assert authoring["command"] == PYTHON and authoring["type"] == "stdio"
    assert authoring["args"][:3] == ["-m", "host_runtime.cli", "mcp"]
    assert authoring["args"][-2:] == ["--agent", "claude-code"]
    assistant = config["mcpServers"][ASSISTANT_SERVER]
    assert assistant["args"][:3] == ["-m", "host_runtime.cli", "assistant-mcp"]
    # The backup is the file as it was.
    assert json.loads(first.backups[0].read_text(encoding="utf-8")) == own
    # Idempotent: nothing changes and no second backup is made.
    again = install("claude-code", environment, launch(tmp_path))
    assert not again.changed and backups(home) == first.backups
    report = status("claude-code", environment)
    assert report["detected"] and report["current"] and report["servers"] == {
        AUTHORING_SERVER: True, ASSISTANT_SERVER: True}


def test_the_persons_own_skill_or_server_of_the_same_name_is_kept(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude")
    home = environment.home
    mine = home / ".claude" / "skills" / "aep-knowledge"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("my own", encoding="utf-8")
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {
        "aep": {"type": "http", "url": "https://mine"}}}), encoding="utf-8")
    changes = install("claude-code", environment, launch(tmp_path))
    assert (mine / "SKILL.md").read_text(encoding="utf-8") == "my own"
    servers = json.loads((home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]
    assert servers["aep"] == {"type": "http", "url": "https://mine"}
    assert ASSISTANT_SERVER in servers
    assert any("kept your own skill" in line for line in changes.lines)
    assert any("kept your own MCP server 'aep'" in line for line in changes.lines)
    assert status("claude-code", environment)["skills"]["aep-knowledge"] == "yours"
    remove("claude-code", environment)
    servers = json.loads((home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]
    assert servers == {"aep": {"type": "http", "url": "https://mine"}}
    assert (mine / "SKILL.md").is_file()
    assert not (home / ".claude" / "skills" / "aep-skill-creator").exists()


def test_codex_gets_a_marked_toml_block_that_updates_and_removes_cleanly(
    tmp_path: Path,
) -> None:
    environment = env(tmp_path, "codex")
    codex = environment.home / ".codex"
    codex.mkdir()
    own = 'model = "gpt-5"\n\n[mcp_servers.github]\ncommand = "gh-mcp"\n'
    (codex / "config.toml").write_text(own, encoding="utf-8")
    install("codex", environment, launch(tmp_path))
    text = (codex / "config.toml").read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert parsed["model"] == "gpt-5" and parsed["mcp_servers"]["github"]["command"] == "gh-mcp"
    assert parsed["mcp_servers"]["aep"]["args"][-1] == "codex"
    assert parsed["mcp_servers"]["aep-assistant"]["command"] == PYTHON
    for name in SKILLS:  # Codex reads personal skills from ~/.agents/skills
        assert (environment.home / ".agents" / "skills" / name / "SKILL.md").is_file()
    # An update with another Python replaces the block, never duplicates it.
    install("codex", environment, launch(tmp_path, "D:/other/python.exe"))
    text = (codex / "config.toml").read_text(encoding="utf-8")
    assert text.count(agent_setup.TOML_BEGIN) == 1
    assert tomllib.loads(text)["mcp_servers"]["aep"]["command"] == "D:/other/python.exe"
    assert status("codex", environment)["current"]
    remove("codex", environment)
    after = (codex / "config.toml").read_text(encoding="utf-8")
    assert agent_setup.TOML_BEGIN not in after and tomllib.loads(after) == tomllib.loads(own)
    assert not (environment.home / ".agents" / "skills" / "aep-knowledge").exists()


def test_codex_with_its_own_aep_server_is_left_alone(tmp_path: Path) -> None:
    environment = env(tmp_path, "codex")
    codex = environment.home / ".codex"
    codex.mkdir()
    own = '[mcp_servers.aep]\ncommand = "mine"\n'
    (codex / "config.toml").write_text(own, encoding="utf-8")
    changes = install("codex", environment, launch(tmp_path))
    assert (codex / "config.toml").read_text(encoding="utf-8") == own
    assert any("kept your own MCP server" in line for line in changes.lines)


def test_copilot_follows_copilot_home_and_takes_tools_star(tmp_path: Path) -> None:
    moved = tmp_path / "copilot-home"
    environment = env(tmp_path, "copilot", COPILOT_HOME=str(moved))
    install("copilot", environment, launch(tmp_path))
    servers = json.loads((moved / "mcp-config.json").read_text(encoding="utf-8"))["mcpServers"]
    assert servers["aep"]["type"] == "local" and servers["aep"]["tools"] == ["*"]
    assert servers["aep-assistant"]["args"][2] == "assistant-mcp"
    assert (moved / "skills" / "aep-workflow-creator" / "SKILL.md").is_file()
    assert not (environment.home / ".copilot").exists()


def test_claude_config_dir_moves_both_places(tmp_path: Path) -> None:
    moved = tmp_path / "claude-config"
    environment = env(tmp_path, "claude", CLAUDE_CONFIG_DIR=str(moved))
    install("claude-code", environment, launch(tmp_path))
    assert (moved / ".claude.json").is_file() and (moved / "skills" / "aep-knowledge").is_dir()
    assert not (environment.home / ".claude.json").exists()


def test_all_skips_agents_that_are_not_here_and_says_so(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude")
    lines = apply("install", agent_setup.AGENT_NAMES, environment, launch(tmp_path))
    assert "Claude Code: installed/updated" in lines
    assert "Codex: not found on this computer; skipped" in lines
    assert "GitHub Copilot CLI: not found on this computer; skipped" in lines
    assert not (environment.home / ".codex").exists()
    assert "Claude Code: already up to date" in apply(
        "install", agent_setup.AGENT_NAMES, environment, launch(tmp_path))
    # A configuration folder counts as installed even when the command is not on PATH.
    (environment.home / ".copilot").mkdir()
    assert "GitHub Copilot CLI: installed/updated" in apply(
        "install", ("copilot",), environment, launch(tmp_path))


def test_an_outdated_skill_is_reported_and_rewritten(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude")
    install("claude-code", environment, launch(tmp_path))
    folder = environment.home / ".claude" / "skills" / "aep-workflow-creator"
    (folder / MARKER_FILE).write_text(json.dumps({"managed_by": "aep", "version": "old"}),
                                      encoding="utf-8")
    (folder / "SKILL.md").write_text("old text", encoding="utf-8")
    report = status("claude-code", environment)
    assert report["skills"]["aep-workflow-creator"] == "old" and not report["current"]
    install("claude-code", environment, launch(tmp_path))
    assert (folder / "SKILL.md").read_text(encoding="utf-8") == skill_text(
        "aep-workflow-creator")
    assert status("claude-code", environment)["current"]


def test_an_unreadable_config_is_not_changed(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude")
    (environment.home / ".claude.json").write_text("{broken", encoding="utf-8")
    lines = apply("install", ("claude-code",), environment, launch(tmp_path))
    assert lines[0].startswith("Claude Code: not changed (")
    assert (environment.home / ".claude.json").read_text(encoding="utf-8") == "{broken"


def test_the_cli_installs_reports_and_removes_for_every_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    environment = env(tmp_path, "claude", "copilot")
    monkeypatch.setattr(Environment, "current", classmethod(lambda cls: environment))
    config = str(tmp_path / "host.json")
    assert main(["assets", "--config", config, "connect", "--for", "all", "--user"]) == 0
    printed = capsys.readouterr().out
    assert "Claude Code: installed/updated" in printed and "Codex: not found" in printed
    assert main(["assets", "--config", config, "connect", "--for", "all", "--user",
                 "--status"]) == 0
    report = {item["agent"]: item for item in json.loads(capsys.readouterr().out)}
    assert report["claude-code"]["current"] and report["copilot"]["current"]
    assert not report["codex"]["installed"]
    assert main(["assets", "--config", config, "connect", "--for", "all", "--user",
                 "--remove"]) == 0
    assert "Claude Code: removed" in capsys.readouterr().out
    assert not status("claude-code", environment)["installed"]
    # --remove belongs to --user.
    assert main(["assets", "--config", config, "connect", "--for", "codex", "--project",
                 str(tmp_path), "--remove"]) == 2


def test_no_token_is_written_into_an_agents_configuration(tmp_path: Path) -> None:
    environment = env(tmp_path, "claude", "codex", "copilot")
    apply("install", agent_setup.AGENT_NAMES, environment, launch(tmp_path))
    written = "".join(path.read_text(encoding="utf-8") for path in environment.home.rglob("*")
                      if path.is_file())
    # The assistant bridge reads the token at call time; no configuration carries it.
    assert "Bearer" not in written and "Authorization" not in written


# -- the installer and updater ---------------------------------------------------

TEMPLATE = Path(__file__).resolve().parents[1] / "deploy" / "windows-preview"


def test_install_and_update_set_up_the_agents_unless_asked_not_to() -> None:
    installer = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    assert "[switch]$NoAgentSkills" in installer
    assert "connect --for all --user" in installer and "if ($NoAgentSkills)" in installer
    update = (TEMPLATE / "update.ps1").read_text(encoding="utf-8")
    assert "[switch]$NoAgentSkills" in update and "-NoAgentSkills:$NoAgentSkills" in update
    uninstall = (TEMPLATE / "uninstall.ps1").read_text(encoding="utf-8")
    assert "connect --for all --user --remove" in uninstall


def _powershell() -> str | None:
    import shutil

    return shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(_powershell() is None, reason="PowerShell is not installed")
def test_the_scripts_parse_and_declare_the_switch() -> None:
    import subprocess

    script = (
        "$names = @(); foreach ($f in 'install.ps1','update.ps1','uninstall.ps1') {"
        " $e = $null; $t = $null;"
        " $a = [System.Management.Automation.Language.Parser]::ParseFile("
        f"(Join-Path '{TEMPLATE}' $f), [ref]$t, [ref]$e);"
        " if ($e.Count) { throw \"$f has $($e.Count) parse errors\" };"
        " $names += ($f + '=' + ($a.ParamBlock.Parameters.Name.VariablePath.UserPath -join ',')) };"
        " $names -join ';'")
    done = subprocess.run([str(_powershell()), "-NoProfile", "-Command", script],
                          capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stderr
    params = dict(item.split("=", 1) for item in done.stdout.strip().split(";"))
    assert "NoAgentSkills" in params["install.ps1"].split(",")
    assert "NoAgentSkills" in params["update.ps1"].split(",")
