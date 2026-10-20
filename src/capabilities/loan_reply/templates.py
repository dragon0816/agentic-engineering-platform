"""Editable message templates for the loan flow (workflows 06 / 06b).

The wording of a customer-facing reply changes far more often than the logic
that decides which reply to send, and the people who want it changed are not
the people who deploy Python. So the text lives in files that can be edited in
Notepad, and the code only decides *which* message and *what* goes in it.

Three decisions worth knowing:

**Overrides are optional; the defaults live here in code.** A fresh install has
no template files at all and works. Drop `config/loan-templates/blocked-reply.txt`
in and that one message changes -- the others keep their defaults. Nothing has
to be created, copied or migrated first, which is the whole point: changing a
reply must not require a deployment.

**Every render re-reads the file.** Save the file, the next mail uses it. Job
modules are cached by the long-lived Bridge process (D59), but that guard is
about *code*; treating text as data means an edit does not need a restart.

**Plain text, one file per message, not a config format.** A `.txt` that someone
mangles is still a slightly odd mail. One malformed JSON file would take every
message with it, including the notice that would have reported the problem.

Placeholders are `{name}`. An unknown one is an error naming the file and
listing what is available -- a silently blank line in a customer's mail is
worse than a run that stops.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The folder relative override paths resolve against, and that ships the
#: source installation's `config/loan-templates` files (AEP port).
REPO_ROOT = Path(__file__).resolve().parent

#: Where overrides are looked for. Not created by anything -- its absence is
#: the normal state and simply means "use the defaults".
DEFAULT_TEMPLATE_DIR = REPO_ROOT / "loan-templates"

SIGNATURE = "台灣羅德史瓦茲"
NO_VALUE = "（詳見附件截圖）"


class TemplateError(RuntimeError):
    """A template exists but cannot be rendered."""


# ---------------------------------------------------------------------------
# The built-in text
# ---------------------------------------------------------------------------
# Kept byte-for-byte from the original workflow so the team's mail reads exactly
# as it did before the port. Change these only to change the *default*; an
# installation that wants different wording overrides the file instead.

DEFAULTS: dict[str, str] = {
    "blocked-reply": (
        "您好，\n\n"
        "您的儀器借用訂單（{borrowNo}）目前無法配送，原因如下：\n"
        "- 分類配送限制 (Classification Delivery Block)：{classificationDeliveryBlock}\n"
        "- 配送限制 (Delivery Block)：{deliveryBlock}\n\n"
        "詳細資訊請見附件截圖。請與我們聯繫以協助解除限制。\n\n"
        "{signature}"
    ),
    "shipping-reply": (
        "您好，\n\n"
        "您的儀器借用訂單（{borrowNo}）審核通過，儀器正在配送中，"
        "本公司人員將盡速為您安排寄送。\n\n"
        "詳細資訊請見附件截圖。\n\n"
        "{signature}"
    ),
    "customer-not-found-subject": "{reasonHeadline} - {borrowNo} (customerId {customerId})",
    "customer-not-found-body": (
        "自動化流程通知（需人工處理）\n\n"
        "借用單號：{borrowNo}\n"
        "出借系統客戶名稱：{customerRaw}\n"
        "取得的 customerId：{customerId}\n\n"
        "{reasonDetail}\n\n"
        "出借系統單據連結：{loanUrl}"
    ),
    "failure-subject": "[自動化失敗] 儀器借出單 {borrowNoOrUnknown} 需人工處理",
    "failure-body": (
        "儀器借出單自動化流程失敗，請人工處理。\n\n"
        "借用單號：{borrowNo}\n"
        "出借系統連結：{loanUrl}\n"
        "錯誤訊息：{error}\n\n"
        "（此單已標記為 failed，不會自動重試；"
        "處理完可從 state/loan-queue/failed/ 移除該檔以便重跑。）"
    ),
}

#: What each template may use, for the error message and for the README that
#: `dump_defaults` writes. Every template also gets the common keys.
COMMON_KEYS = (
    "borrowNo", "category", "customerRaw", "customerId", "customerName",
    "customerEmail", "loanUrl", "signature",
)

EXTRA_KEYS: dict[str, tuple[str, ...]] = {
    "blocked-reply": ("classificationDeliveryBlock", "deliveryBlock"),
    "customer-not-found-subject": ("reasonHeadline", "reasonDetail", "reason"),
    "customer-not-found-body": ("reasonHeadline", "reasonDetail", "reason"),
    "failure-subject": ("error", "borrowNoOrUnknown"),
    "failure-body": ("error", "borrowNoOrUnknown"),
}


def keys_for(name: str) -> tuple[str, ...]:
    return tuple(sorted(set(COMMON_KEYS) | set(EXTRA_KEYS.get(name, ()))))


# ---------------------------------------------------------------------------
# Loading and rendering
# ---------------------------------------------------------------------------


def template_dir(override: str | Path | None = None) -> Path:
    if not override:
        return DEFAULT_TEMPLATE_DIR
    p = Path(override).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p)


def template_path(name: str, override: str | Path | None = None) -> Path:
    return template_dir(override) / f"{name}.txt"


def load(name: str, override: str | Path | None = None) -> tuple[str, str]:
    """``(text, source)``. ``source`` is ``"default"`` or the file it came from.

    Read fresh every time on purpose -- see the module docstring. These are a
    few hundred bytes each and at most a handful per mail.
    """
    if name not in DEFAULTS:
        raise TemplateError(
            f"unknown template {name!r}. Known: {', '.join(sorted(DEFAULTS))}"
        )
    path = template_path(name, override)
    if path.is_file():
        try:
            # utf-8-sig: Notepad writes a BOM, and this is a file we are
            # explicitly inviting people to edit in Notepad.
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise TemplateError(f"cannot read {path}: {exc}") from exc
        # A trailing newline from the editor is not part of the message.
        return text.rstrip("\n"), str(path)
    return DEFAULTS[name], "default"


def render(name: str, context: Mapping[str, Any],
           override: str | Path | None = None) -> str:
    """Fill ``name`` from ``context``, or explain exactly what is wrong."""
    text, source = load(name, override)
    values = {k: ("" if v is None else str(v)) for k, v in context.items()}
    try:
        return text.format_map(values)
    except KeyError as exc:
        bad = str(exc).strip("'\"")
        raise TemplateError(
            f"{source}: no such placeholder {{{bad}}}. "
            f"Available here: {', '.join('{' + k + '}' for k in keys_for(name))}"
        ) from exc
    except (ValueError, IndexError) as exc:
        # A literal brace in the text, or {0}-style positional formatting.
        raise TemplateError(
            f"{source}: the text could not be filled in ({exc}). "
            "A literal { or } must be written twice: {{ or }}."
        ) from exc


def render_or_default(name: str, context: Mapping[str, Any],
                      override: str | Path | None = None) -> tuple[str, str | None]:
    """Render, falling back to the built-in text if an override is broken.

    Only for the failure notice. That notice is how a broken template gets
    reported, so it must not itself be able to fail for the same reason --
    otherwise the one message that would have explained the problem is the one
    message that cannot be produced. Returns ``(text, warning)``.
    """
    try:
        return render(name, context, override), None
    except TemplateError as exc:
        fallback = DEFAULTS[name].format_map(
            {k: ("" if v is None else str(v)) for k, v in context.items()}
        )
        return fallback, f"template override ignored ({exc})"


# ---------------------------------------------------------------------------
# Getting started
# ---------------------------------------------------------------------------

README = """\
儀器借出單回信範本
==================

這個資料夾裡的 .txt 檔會【覆寫】程式內建的信件文字。

  * 檔案不存在 = 用內建預設。刪掉檔案就回到預設，不會壞掉。
  * 只想改一封信，就只留那一個檔，其他刪掉。
  * 存檔後【立即生效】，不需要重啟 Host Bridge、也不需要重新安裝。
  * 用 Notepad 編輯就可以，存成 UTF-8（有沒有 BOM 都可以）。

placeholder 寫成 {{名稱}}，會被實際內容取代。打錯名字時 job 會停下來並告訴你
是哪個檔案、哪個名稱、以及那個檔案可以用哪些名稱 —— 不會靜靜地在客戶信裡留白。

要在信裡寫出真正的大括號，請寫兩次：{{{{ 和 }}}}。

各檔案可用的 placeholder
------------------------
{sections}
"""


def dump_defaults(dest: str | Path | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Write the built-in text out as files, as a starting point for editing.

    Refuses to clobber an existing file unless asked: the likeliest reason a
    file is already there is that somebody edited it.
    """
    directory = template_dir(dest)
    directory.mkdir(parents=True, exist_ok=True)
    written, skipped = [], []
    for name, text in sorted(DEFAULTS.items()):
        path = directory / f"{name}.txt"
        if path.exists() and not overwrite:
            skipped.append(str(path))
            continue
        path.write_text(text + "\n", encoding="utf-8")
        written.append(str(path))

    sections = "\n".join(
        f"{name}.txt\n    " + "  ".join("{" + k + "}" for k in keys_for(name))
        for name in sorted(DEFAULTS)
    )
    readme = directory / "README.txt"
    if overwrite or not readme.exists():
        readme.write_text(README.format(sections=sections), encoding="utf-8")
        written.append(str(readme))

    return {"dir": str(directory), "written": written, "skipped": skipped}


def status(override: str | Path | None = None) -> list[dict[str, str]]:
    """Which templates are overridden and which are using the default."""
    out = []
    for name in sorted(DEFAULTS):
        _, source = load(name, override)
        out.append({
            "name": name,
            "source": "default" if source == "default" else "file",
            "path": source if source != "default" else str(template_path(name, override)),
        })
    return out
