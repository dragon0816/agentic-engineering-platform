"""Driving the BI area of Agent Web in a real (headless) browser, for the tests."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from integrations.browser import Browser, BrowserError, browser_path

#: Keeps what a failed wait reports: requests under way or failed, and page errors.
_WATCH = """
(() => {
  const watch = window.__aepWatch = {open: [], failed: [], errors: []};
  const keep = (list, item) => { list.push(item); if (list.length > 40) list.shift(); };
  window.addEventListener("error", (e) => keep(watch.errors, String(e.message)));
  window.addEventListener("unhandledrejection", (e) => keep(watch.errors, String(e.reason)));
  const original = window.fetch;
  window.fetch = async (...args) => {
    const name = String(args[0]).split("?")[0];
    watch.open.push(name);
    try {
      const reply = await original(...args);
      if (!reply.ok) keep(watch.failed, name + " " + reply.status);
      return reply;
    } catch (failure) {
      keep(watch.failed, name + " " + failure);
      throw failure;
    } finally { watch.open.splice(watch.open.indexOf(name), 1); }
  };
})();
"""
_NOTICE = "(document.getElementById('bi-notice') || {}).textContent"
_PAGE_STATE = (
    "({url: location.pathname, ready: document.readyState, "
    "send: (document.getElementById('send') || {disabled: 'absent'}).disabled, "
    "text: document.body ? document.body.innerText.slice(0, 300) : ''})"
)


def browser_missing() -> bool:
    return browser_path() is None


class BiPage:
    def __init__(self, folder: Path, address: str, shots: Path | None = None) -> None:
        self.browser = Browser(folder, timeout_s=60)
        self.address = address
        self.shots = shots

    def __enter__(self) -> BiPage:
        self.browser.start()
        self.browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1366,
            height=1000,
            deviceScaleFactor=1,
            mobile=False,
        )
        self.browser.page().call("Page.enable")
        self.browser.page().call("Page.addScriptToEvaluateOnNewDocument", source=_WATCH)
        self.browser.navigate(self.address)
        self.wait('!document.getElementById("send").disabled')
        self.click("#nav-knowledge")
        self.click("#kn-tabs [data-kn=bi]")
        self.wait("document.getElementById('bi-status-bar').hidden")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.browser.close()

    def run(self, expression: str) -> Any:
        return self.browser._evaluate(expression)

    def wait(self, expression: str, seconds: float = 240) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = self.run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(f"{expression}\n{self.diagnosis()}")

    def diagnosis(self) -> str:
        """What the page was doing, for a failed wait to explain itself. It must not
        replace the failure with its own: each part that cannot be read says so."""

        def read(expression: str) -> Any:
            try:
                return self.run(expression)
            except Exception as failure:  # noqa: BLE001 - see above
                return f"<unreadable: {type(failure).__name__}>"

        return (
            f"notice: {read(_NOTICE)!r}\n"
            f"visible stage: {read(_VISIBLE_STAGE)!r}\n"
            f"steps shut: {read(_SHUT_STEPS)!r}, source: {read('bi.build.sourceId')!r}\n"
            f"page: {read(_PAGE_STATE)!r}\n"
            f"requests still open: {read('window.__aepWatch && window.__aepWatch.open')!r}\n"
            f"requests failed: {read('window.__aepWatch && window.__aepWatch.failed')!r}\n"
            f"page errors: {read('window.__aepWatch && window.__aepWatch.errors')!r}"
        )

    def click(self, selector: str) -> None:
        self.run(f"document.querySelector({json.dumps(selector)}).click()")

    def click_text(self, scope: str, label: str) -> None:
        self.run(
            f"[...document.querySelectorAll({json.dumps(scope + ' button')})]"
            f".find(b => b.textContent.includes({json.dumps(label)})).click()"
        )

    def text_of(self, element_id: str) -> str:
        return str(self.run(f"document.getElementById({json.dumps(element_id)}).textContent"))

    def set_value(self, element_id: str, value: str) -> None:
        self.run(f"document.getElementById({json.dumps(element_id)}).value = {json.dumps(value)}")

    def shows(self, element_id: str, text: str) -> str:
        """An expression for `wait`: the element's text contains `text`."""
        return (
            f"document.getElementById({json.dumps(element_id)})"
            f".textContent.includes({json.dumps(text)})"
        )

    def see(self, element_id: str, text: str) -> None:
        """Wait until the element's text contains `text`; a failure says what it held."""
        try:
            self.wait(self.shows(element_id, text))
        except AssertionError as failure:
            held = self.text_of(element_id)
            raise AssertionError(f"{failure}\n{element_id}: {held!r}") from None

    def notice(self, text: str) -> None:
        self.wait(self.shows("bi-notice", text))

    def stage(self, name: str) -> None:
        """Open a step, or a sub-step of step 2, and wait until it shows."""
        self.click(f"#bi-build-steps [data-stage={name}]")
        self.wait(f"!document.querySelector('#bi-view-build .kp-stage[data-stage={name}]').hidden")

    def upload(self, name: str, text: str, media_type: str) -> None:
        self.run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(text)}], {json.dumps(name)},"
            f" {{type: {json.dumps(media_type)}}}));"
            " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )
        self.click("#bi-b-upload")
        self.wait(self.shows("bi-b-sources", name))
        self.wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 1")

    def shoot(self, name: str) -> None:
        if self.shots is not None:
            self.shots.mkdir(parents=True, exist_ok=True)
            time.sleep(0.25)
            self.browser.screenshot(self.shots / f"{name}.png")


_SHUT_STEPS = (
    "[...document.querySelectorAll('#bi-build-steps [data-stage]')]"
    ".filter(b => b.disabled).map(b => b.dataset.stage).join(',')"
)
_VISIBLE_STAGE = (
    "[...document.querySelectorAll('#bi-view-build .kp-stage')]"
    ".filter(s => !s.hidden).map(s => s.dataset.stage).join(',')"
)
