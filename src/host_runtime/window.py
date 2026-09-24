"""A window to talk to the resident Agent, for people who are not at a shell.

This is an ingress and nothing more. It builds the same `LocalAgentRequest`
the command line and the Telegram channel build, hands it to the same Agent,
and shows what came back. No routing, no policy and no capability lives here:
an ingress that decided anything would be a second answer to a question the
platform already answers once.

Tkinter, because it is in the standard library. A window that cost the
offline bundle another forty megabytes of wheels would be a window most
company machines never got.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from collections.abc import Callable
from typing import Any

from common.execution import TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgentOutcome
from host_runtime.host import HostRuntime

#: What the window says it cannot do, so nobody waits for it to.
LIMITATIONS = (
    "This window asks the Agent on this computer. It is the same Agent the "
    "command line and Telegram reach, and it can do no more and no less."
)


def _trace() -> TraceIdentifiers:
    value = uuid.uuid4().hex
    return TraceIdentifiers(
        trace_id=f"trace-{value}", request_id=f"request-{value}", span_id=f"span-{value}"
    )


def readable(outcome: LocalAgentOutcome) -> str:
    """What to show a person.

    A workflow's last step often carries a rendering meant for reading --
    the weekly report's plan is the whole dry run in words. Where there is
    one it is shown, because the alternative is a person reading JSON to
    find out what a run would do. Where there is not, the step's own data is
    shown as it stands rather than summarised into something that might be
    wrong.
    """
    if outcome.refusal is not None:
        return f"Refused: {outcome.refusal}"
    lines: list[str] = []
    decision = outcome.decision
    if decision is not None and decision.target is not None:
        target = decision.target
        lines.append(f"{decision.kind}: {target.namespace}/{target.name}@{target.version}")
    if outcome.capability is not None:
        lines.append(f"capability: {outcome.capability.status}")
    if outcome.workflow is not None:
        run = outcome.workflow.run
        lines.append(f"{run.status}, {run.completed_steps} step(s)")
        if run.failure is not None:
            lines.append(f"failure: {run.failure.code}")
        results = outcome.workflow.step_results
        if results:
            data = results[-1].data
            if isinstance(data, dict):
                shown = data.get("preview")
                if isinstance(shown, str) and shown.strip():
                    lines.append("")
                    lines.append(shown)
                else:
                    lines.append("")
                    lines.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    if outcome.unrecorded is not None:
        lines.append(f"the run record could not be written: {outcome.unrecorded}")
    return "\n".join(lines) or "nothing came back"


class AgentWindow:
    """One window over one host.

    The Agent is asked on a worker thread and the answer arrives through a
    queue the window drains: a request that takes a minute -- and a week's
    report does -- must not freeze the window it was typed into.
    """

    def __init__(
        self,
        runtime: HostRuntime,
        namespace: str,
        *,
        actor: str | None = None,
        ask: Callable[[LocalAgentRequest], LocalAgentOutcome] | None = None,
    ) -> None:
        self.runtime = runtime
        self.namespace = namespace
        self.actor = actor if actor is not None else runtime.actor
        self._ask = ask if ask is not None else self._ask_the_agent
        self._answers: queue.Queue[tuple[str, str]] = queue.Queue()

    # -- the part that has nothing to do with a window -----------------

    def _ask_the_agent(self, request: LocalAgentRequest) -> LocalAgentOutcome:
        import asyncio

        return asyncio.run(self.runtime.agent.handle(request))

    def request_for(self, message: str) -> LocalAgentRequest:
        return LocalAgentRequest(
            ingress="local",
            actor=self.actor,
            bridge_id=self.runtime.config.device.bridge_id,
            namespace=self.namespace,
            message=message,
            trace=_trace(),
        )

    def answer_for(self, message: str) -> str:
        """Ask, and turn whatever happens into something to read. A failure
        here is shown in the window: a traceback in a console nobody has open
        is not an answer."""
        try:
            return readable(self._ask(self.request_for(message)))
        except Exception as failure:  # noqa: BLE001 - a window shows everything
            return f"The request did not finish: {type(failure).__name__}: {failure}"

    # -- the window ----------------------------------------------------

    def run(self) -> int:  # pragma: no cover - a window needs a person
        import tkinter as tk
        from tkinter import scrolledtext

        root = tk.Tk()
        root.title(f"Agent on {self.runtime.config.device.bridge_id}")
        root.geometry("900x620")

        header = tk.Label(
            root,
            text=f"as {self.actor} · namespace {self.namespace} · {LIMITATIONS}",
            anchor="w",
            justify="left",
            wraplength=880,
            fg="#555555",
        )
        header.pack(fill="x", padx=10, pady=(10, 4))

        transcript = scrolledtext.ScrolledText(root, wrap="word", state="disabled")
        transcript.pack(fill="both", expand=True, padx=10, pady=4)
        transcript.tag_configure("you", foreground="#0b5394", spacing1=8)
        transcript.tag_configure("waiting", foreground="#888888")

        row = tk.Frame(root)
        row.pack(fill="x", padx=10, pady=(4, 10))
        entry = tk.Entry(row)
        entry.pack(side="left", fill="x", expand=True)
        entry.focus_set()

        def show(text: str, tag: str = "") -> None:
            transcript.configure(state="normal")
            transcript.insert("end", text + "\n", tag)
            transcript.see("end")
            transcript.configure(state="disabled")

        def busy(waiting: bool) -> None:
            """One request at a time, and the window says which state it is in.

            Not a nicety. Two runs at once would be two runs against the one
            workbook, and the second would be refused for a lock the first
            holds. Serialising here is also what keeps the waiting line
            unambiguous: there is only ever one."""
            entry.configure(state="disabled" if waiting else "normal")
            button.configure(state="disabled" if waiting else "normal")
            if not waiting:
                entry.focus_set()

        def send(_event: Any = None) -> None:
            message = entry.get().strip()
            if not message:
                return
            entry.delete(0, "end")
            show(f"> {message}", "you")
            show("working...", "waiting")
            busy(True)

            def work() -> None:
                self._answers.put((message, self.answer_for(message)))

            threading.Thread(target=work, daemon=True).start()

        def drain() -> None:
            while True:
                try:
                    _asked, answer = self._answers.get_nowait()
                except queue.Empty:
                    break
                transcript.configure(state="normal")
                # Replace the "working..." line with the answer.
                transcript.delete("end-2l", "end-1l")
                transcript.configure(state="disabled")
                show(answer)
                busy(False)
            root.after(120, drain)

        button = tk.Button(row, text="Send", command=send)
        button.pack(side="left", padx=(8, 0))
        entry.bind("<Return>", send)
        show(
            "Type a command, for example  weekly.preview 2026_39W\n"
            "Nothing is written unless the command says so."
        )
        root.after(120, drain)
        root.mainloop()
        return 0
