"""The Knowledge page's Skill assistant (owner, 2026-10-12).

A domain expert describes in plain words how their data should be processed
or how questions should be answered; the company model, given the writing
guide, the matching template, the skill as it is now and a sample source of
its category, asks what it needs and proposes a complete new SKILL.md. The
assistant only proposes: nothing is written until the person puts the
proposal in the editor and saves it, in their sandbox.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from common.base import Contract
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest

MAX_TURNS = 20
MAX_TEXT = 12_000
SAMPLE_CHARS = 3000
FENCE = re.compile(r"```(?:markdown|md)?\s*\n(---\n.*?)\n```", re.DOTALL)

SYSTEM = """You help a domain expert write one rule file (SKILL.md) for a company knowledge
base. Ingest skills (mode: procedure) decide how raw sources become wiki pages; answer
skills (mode: answer) decide how questions are judged and answered. Follow the writing
guide and template below.

How to work:
- Reply in the expert's language. Be brief.
- If the request is unclear, ask at most three short questions before proposing.
- When you propose a change, explain it in two or three sentences, then give the
  COMPLETE new file in one ```markdown fenced block, starting with its frontmatter.
- Keep the frontmatter valid: name, description, mode, and applies_to (ingest) or
  optional topics (answer). Keep every existing rule unless the expert asked to change
  it; say which rules you changed or removed.
- Write rules with a reason and an example. Never write facts about what data
  exists today. Never ask answers to include uncited sections (follow-up questions,
  reading lists): every answer line must cite evidence.

===== writing guide =====
{guide}

===== template =====
{template}"""


class Turn(Contract):
    role: Literal["user", "assistant"]
    text: str


class AssistReply(Contract):
    reply: str
    proposal: str | None = None  # the complete proposed SKILL.md, when there is one
    warnings: tuple[str, ...] = ()  # what the Host found missing in the proposal


def check_proposal(text: str) -> tuple[str, ...]:
    """Frontmatter a rule file needs before it can be saved and used."""
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return ("the proposal has no frontmatter",)
    head = text[4:].split("\n---\n", 1)[0]
    fields = {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
              for line in head.splitlines() if ":" in line and not line.startswith(" ")}
    found = []
    if not fields.get("name"):
        found.append("frontmatter has no name")
    mode = fields.get("mode", "")
    if mode not in ("procedure", "answer"):
        found.append("mode should be procedure (ingest) or answer")
    if mode == "procedure" and not fields.get("applies_to", "").startswith("raw/"):
        found.append("an ingest rule needs applies_to: raw/<category>")
    return tuple(found)


def proposal_of(text: str) -> str | None:
    found = FENCE.findall(text)
    return found[-1].strip() + "\n" if found else None


def assist(model: ModelClient, alias: str, *, guide: str, template: str, path: str,
           current: str, sample: str | None, turns: list[Turn],
           trace: TraceIdentifiers,
           on_state: Callable[[str], None] | None = None) -> AssistReply:
    """`on_state` hears `asking` and `checking`, so a page can show progress."""
    report = on_state or (lambda _state: None)
    if not turns or turns[-1].role != "user":
        raise ValueError("the last turn is the expert's")
    context = (f"The file being edited: {path}\n\n===== current file =====\n"
               f"{current[:MAX_TEXT] or '(new file)'}"
               + (f"\n\n===== a sample source of this category (excerpt) =====\n"
                  f"{sample[:SAMPLE_CHARS]}" if sample else ""))
    # replace(), not format(): a guide or template may contain braces.
    system = SYSTEM.replace("{guide}", guide).replace("{template}", template)
    messages = [ModelMessage(role="system", text=system),
                ModelMessage(role="user", text=context),
                ModelMessage(role="assistant", text="I have the file. What should change?")]
    messages += [ModelMessage(role=turn.role, text=turn.text[:MAX_TEXT])
                 for turn in turns[-MAX_TURNS:]]
    report("asking")
    response = model.generate(ModelRequest(trace=trace, model_alias=alias,
                                           messages=tuple(messages), max_output_tokens=6000))
    if response.failure is not None:
        raise RuntimeError(response.failure.code)
    report("checking")
    text = (response.text or "").strip()
    proposal = proposal_of(text)
    return AssistReply(reply=text, proposal=proposal,
                       warnings=check_proposal(proposal) if proposal else ())
