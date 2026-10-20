# Vendored oracle: rs_workflow_system@896046e8 host-bridge/tests/test_loan_templates.py; only tests/loan_oracle.py REPLACEMENTS differ.
"""Editable mail templates for the loan flow.

The point of this feature is that someone who is not deploying Python can
change what a customer receives. So the tests are about the promises made to
that person: no file is needed, a file wins, an edit takes effect immediately,
and a mistake is explained rather than silently mailed out.
"""

from __future__ import annotations

import pytest

from capabilities.loan_reply import rules
from capabilities.loan_reply import templates as t

BORROW = "DR26270135"


def write(dirpath, name, text):
    p = dirpath / f"{name}.txt"
    p.write_text(text, encoding="utf-8")
    return p


class TestOverrides:
    def test_no_file_means_the_built_in_text(self, tmp_path):
        text, source = t.load("shipping-reply", tmp_path)
        assert source == "default"
        assert text == t.DEFAULTS["shipping-reply"]

    def test_a_file_wins_over_the_built_in_text(self, tmp_path):
        write(tmp_path, "shipping-reply", "改過的內容 {borrowNo}")
        out = t.render("shipping-reply", {"borrowNo": BORROW}, tmp_path)
        assert out == f"改過的內容 {BORROW}"

    def test_overriding_one_message_leaves_the_others_alone(self, tmp_path):
        """The reason overrides are per-file rather than one config blob."""
        write(tmp_path, "shipping-reply", "只改這封")
        _, blocked_source = t.load("blocked-reply", tmp_path)
        assert blocked_source == "default"

    def test_an_edit_takes_effect_without_a_restart(self, tmp_path):
        """Templates are data, not code.

        Job modules are cached by the long-lived Bridge process, so if the text
        were read once at import the operator would have to restart the Bridge
        to change a sentence -- which is the thing this feature exists to avoid.
        """
        write(tmp_path, "shipping-reply", "第一版")
        assert t.render("shipping-reply", {}, tmp_path) == "第一版"
        write(tmp_path, "shipping-reply", "第二版")
        assert t.render("shipping-reply", {}, tmp_path) == "第二版"

    def test_deleting_the_file_returns_to_the_default(self, tmp_path):
        p = write(tmp_path, "shipping-reply", "暫時的")
        assert rules.shipping_reply(BORROW, templateDir=tmp_path) == "暫時的"
        p.unlink()
        assert BORROW in rules.shipping_reply(BORROW, templateDir=tmp_path)

    def test_a_notepad_bom_is_not_part_of_the_message(self, tmp_path):
        """This is a file we invite people to edit in Notepad, which adds one."""
        (tmp_path / "shipping-reply.txt").write_text("您好", encoding="utf-8-sig")
        assert t.render("shipping-reply", {}, tmp_path) == "您好"

    def test_the_editors_trailing_newline_is_not_part_of_the_message(self, tmp_path):
        write(tmp_path, "shipping-reply", "結尾\n\n")
        assert t.render("shipping-reply", {}, tmp_path) == "結尾"


class TestMistakes:
    def test_an_unknown_placeholder_names_the_file_and_the_valid_names(self, tmp_path):
        """A typo must stop the run, not leave a blank in a customer's mail."""
        p = write(tmp_path, "shipping-reply", "訂單 {borrowNumber} 已出貨")
        with pytest.raises(t.TemplateError) as exc:
            t.render("shipping-reply", {"borrowNo": BORROW}, tmp_path)
        message = str(exc.value)
        assert str(p) in message
        assert "borrowNumber" in message
        assert "{borrowNo}" in message      # tells them what they meant

    def test_a_literal_brace_is_explained_rather_than_crashing(self, tmp_path):
        write(tmp_path, "shipping-reply", "價格 { 未定")
        with pytest.raises(t.TemplateError, match=r"\{\{"):
            t.render("shipping-reply", {}, tmp_path)

    def test_an_unknown_template_name_lists_the_known_ones(self):
        with pytest.raises(t.TemplateError, match="shipping-reply"):
            t.load("no-such-message")

    def test_the_failure_notice_survives_its_own_broken_template(self, tmp_path):
        """The notice that reports a broken template must not need one.

        Otherwise the single message able to explain the problem is the one
        message that cannot be produced, and the operator sees nothing at all.
        """
        write(tmp_path, "failure-body", "壞掉的 {nonsense}")
        subject, body, warnings = rules.failure_notice(
            BORROW, "https://portal/x", "boom", templateDir=tmp_path)
        assert BORROW in subject
        assert "boom" in body                      # fell back to the built-in text
        assert warnings and "nonsense" in warnings[0]

    def test_a_healthy_failure_template_produces_no_warning(self, tmp_path):
        subject, body, warnings = rules.failure_notice(
            BORROW, "https://portal/x", "boom", templateDir=tmp_path)
        assert warnings == []

    def test_other_messages_do_not_silently_fall_back(self, tmp_path):
        """Only the failure notice tolerates a broken override.

        A customer reply that quietly reverts to different wording would be
        indistinguishable from the edit having worked.
        """
        write(tmp_path, "blocked-reply", "{nonsense}")
        with pytest.raises(t.TemplateError):
            rules.blocked_reply(BORROW, rules.BlockStatus(True, "Z1", ""),
                                templateDir=tmp_path)


class TestPlaceholders:
    def test_every_default_renders_with_the_keys_it_advertises(self):
        """`keys_for` is what the error message tells people to use.

        If it disagreed with what the text actually needs, the guidance would
        send them to a name that does not work.
        """
        for name in t.DEFAULTS:
            ctx = {k: f"<{k}>" for k in t.keys_for(name)}
            rendered = t.render(name, ctx)
            assert rendered

    def test_the_reply_context_carries_the_customer_details(self):
        ctx = rules.reply_context(BORROW, customerName="BTL Inc.", customerId="130895")
        assert ctx["customerName"] == "BTL Inc."
        assert ctx["borrowNo"] == BORROW
        assert ctx["signature"] == rules.SIGNATURE

    def test_a_missing_borrow_number_still_reads_as_something(self):
        assert rules.reply_context("")["borrowNoOrUnknown"] == "(未知單號)"

    def test_customer_details_reach_a_customer_reply(self, tmp_path):
        """The reason the context is built once for every branch."""
        write(tmp_path, "shipping-reply", "{customerName} / {customerId} / {category}")
        out = rules.shipping_reply(BORROW, customerName="BTL Inc.", customerId="130895",
                                   category="一般", templateDir=tmp_path)
        assert out == "BTL Inc. / 130895 / 一般"


class TestGettingStarted:
    def test_write_templates_produces_editable_files_and_a_readme(self, tmp_path):
        out = t.dump_defaults(tmp_path)
        names = {p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in out["written"]}
        assert "README.txt" in names
        assert "blocked-reply.txt" in names
        assert (tmp_path / "blocked-reply.txt").read_text(encoding="utf-8").strip()

    def test_it_does_not_clobber_an_edited_file(self, tmp_path):
        """A file that is already there is almost certainly someone's edit."""
        write(tmp_path, "blocked-reply", "我改過的")
        out = t.dump_defaults(tmp_path)
        assert any("blocked-reply" in p for p in out["skipped"])
        assert (tmp_path / "blocked-reply.txt").read_text(encoding="utf-8") == "我改過的"

    def test_overwrite_replaces_it_when_asked(self, tmp_path):
        write(tmp_path, "blocked-reply", "我改過的")
        t.dump_defaults(tmp_path, overwrite=True)
        assert "我改過的" not in (tmp_path / "blocked-reply.txt").read_text(encoding="utf-8")

    def test_the_readme_lists_the_placeholders_for_each_file(self, tmp_path):
        t.dump_defaults(tmp_path)
        readme = (tmp_path / "README.txt").read_text(encoding="utf-8")
        assert "{classificationDeliveryBlock}" in readme
        assert "blocked-reply.txt" in readme
        assert "{{" in readme                     # how to write a literal brace

    def test_dumped_files_render_unchanged(self, tmp_path):
        """Round trip: what is written out must mean the same as the built-in."""
        t.dump_defaults(tmp_path)
        for name in t.DEFAULTS:
            ctx = {k: f"<{k}>" for k in t.keys_for(name)}
            assert t.render(name, ctx, tmp_path) == t.render(name, ctx)

    def test_status_says_which_are_overridden(self, tmp_path):
        write(tmp_path, "shipping-reply", "x")
        rows = {r["name"]: r["source"] for r in t.status(tmp_path)}
        assert rows["shipping-reply"] == "file"
        assert rows["blocked-reply"] == "default"
