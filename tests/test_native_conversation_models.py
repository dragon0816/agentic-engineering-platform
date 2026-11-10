"""Backend scopes preserve Gateway choices and never reuse another catalog."""

from pathlib import Path

from host_runtime.conversation_models import ConversationModels


def test_backend_choices_defaults_and_provider_reset(tmp_path: Path) -> None:
    store = ConversationModels(
        tmp_path,
        listing=lambda: {"ok": True, "models": ["gateway"]},
        configured=lambda: "gateway",
        native_listing=lambda backend: {"ok": True, "models": [backend + "-m"]},
    )
    assert store.choose("owner", "one", "gateway")["ok"]
    assert store.choose("owner", "one", "codex-m", backend="codex")["ok"]
    assert store.for_turn("owner", "one", backend="codex") == "codex-m"
    assert store.listed("owner", "two", backend="codex")["selected"] == "codex-m"
    assert store.listed("owner", "one")["selected"] == "gateway"
    assert not store.choose("owner", "one", "gateway", backend="codex")["ok"]
    assert store.choose("owner", "one", "", backend="codex")["ok"]
    assert store.for_turn("owner", "one", backend="codex") is None


def test_native_failure_and_disappeared_choice_never_reuses_old_catalog(tmp_path: Path) -> None:
    answer = {"ok": True, "models": ["m1"]}
    store = ConversationModels(
        tmp_path,
        listing=lambda: {"ok": True, "models": ["gateway"]},
        configured=lambda: "gateway",
        native_listing=lambda _: answer,
    )
    assert store.choose("owner", "one", "m1", backend="codex")["ok"]
    answer.update(ok=False, code="model_catalog_timeout", models=[])
    listed = store.listed("owner", "one", backend="codex", refresh=True)
    assert listed["selected"] == ""
    assert listed["unavailable"] == "m1"
    assert listed["models"] == [{"id": "", "label": "Provider default", "status": "CLI default"}]
    assert not store.choose("owner", "one", "m1", backend="codex")["ok"]
