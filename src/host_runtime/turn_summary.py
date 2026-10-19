"""A compact record of the tools one conversation turn used (owner, 2026-10-07).

Agent Web keeps each turn's text; without this, a turn that stopped at its
tool budget left the next turn no idea what had been done. The summary keeps
only what a continuation needs: which tool, whether it worked, the files it
wrote and the identifiers of drafts, approvals and runs. It never carries a
page's text, a file's content or a script, so it cannot smuggle source
content into later turns.
"""

from __future__ import annotations

import json
from typing import Any

from agent.gateway import ConversationToolExecution, GatewayConversationResult

MAX_SUMMARY_CHARS = 2_500
_KEEP = (
    "candidate_id",
    "workflow",
    "revision",
    "digest",
    "read_only",
    "approval_id",
    "run_id",
    "status",
    "url",
    "downloads",
    "installed_as",
    "app",
)


def _host(data: Any) -> str:
    if isinstance(data, list):
        listed = [
            {key: item.get(key) for key in ("candidate_id", "workflow", "status")}
            for item in data[:5]
            if isinstance(item, dict)
        ]
        return f"{len(data)} item(s) {json.dumps(listed, ensure_ascii=False)}"
    if not isinstance(data, dict):
        return ""
    kept = {key: data[key] for key in _KEEP if data.get(key) not in (None, "", [], ())}
    if isinstance(data.get("data"), dict) and data["data"]:
        kept["read"] = sorted(data["data"])[:10]
    if isinstance(data.get("items"), dict) and data["items"]:
        kept["items"] = len(data["items"])
    if isinstance(data.get("problems"), list):
        kept["problems"] = data["problems"][:3]
    return json.dumps(kept, ensure_ascii=False)


def _line(item: ConversationToolExecution) -> str:
    if item.failure is not None:
        return f"- {item.name}: refused ({item.failure.code})"
    if item.host is not None:
        failure = f" ({item.host.failure.code})" if item.host.failure else ""
        return f"- {item.name}: {item.host.status}{failure} {_host(item.host.data)}".rstrip()
    if item.capability is not None:
        failure = f" ({item.capability.failure.code})" if item.capability.failure else ""
        return f"- {item.name}: {item.capability.status}{failure}"
    if item.workflow is not None:
        run = item.workflow.run
        line = f"- {item.name}: {run.status}"
        steps = item.workflow.step_results
        data = steps[0].data if steps else None
        if isinstance(data, dict):
            files = data.get("files")
            details = {
                "exit_code": data.get("exit_code"),
                "files": [f.get("path") for f in files[:10] if isinstance(f, dict)]
                if isinstance(files, list)
                else None,
                "script": data.get("script_path"),
            }
            line += " " + json.dumps(
                {k: v for k, v in details.items() if v not in (None, [])}, ensure_ascii=False
            )
        return line
    return f"- {item.name}"


def tool_summary(result: GatewayConversationResult | None) -> str | None:
    """None when the turn used no tool."""
    if result is None or not result.tools:
        return None
    lines = [_line(item) for item in result.tools]
    if result.failure is not None:
        lines.append(f"(turn stopped: {result.failure.code})")
    text = "\n".join(lines)
    return text if len(text) <= MAX_SUMMARY_CHARS else text[:MAX_SUMMARY_CHARS] + "\n…"


def stop_reply(
    code: str, tool_calls: int, time_limit_minutes: int | None, *, recorded: bool
) -> str | None:
    """What the person is told when a guard stopped the turn (owner 2026-10-19),
    or None for any other outcome. `recorded`: the channel keeps the turn's
    steps in the conversation (Agent Web says so)."""
    if code == "tool_loop_limit":
        head = f"這個回合已用完 {tool_calls} 次工具呼叫，工作還沒完成"
    elif code == "turn_time_limit":
        minutes = f" {time_limit_minutes} 分鐘的" if time_limit_minutes else ""
        head = f"這個回合已用完{minutes}時間上限，工作還沒完成（用了 {tool_calls} 次工具呼叫）"
    elif code == "tool_repeat_limit":
        head = (
            "同一個工具用相同的內容重複呼叫，沒有新的進展，所以先停下來"
            f"（用了 {tool_calls} 次工具呼叫）；可以補充說明或換個做法"
        )
    else:
        return None
    if recorded:
        return f"{head}。目前做到的步驟已記錄在這段對話中；回覆「繼續」我會接著做。"
    return f"{head}；回覆「繼續」我會接著做。"
