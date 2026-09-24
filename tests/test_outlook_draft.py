"""The draft writer, and the one thing it must never do.

Outlook is not in CI, so the COM adapter is driven against a stand-in that
records the calls made on it -- which is enough to pin the object model this
adapter was written to, and to pin that no verb which delivers is ever
reached.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from integrations import outlook_draft
from integrations.outlook_draft import (
    DraftError,
    InlineImage,
    MailDraft,
    OutlookComDraft,
    RecordingDraftWriter,
)


class FakeAccessor:
    def __init__(self, into: dict[str, Any]) -> None:
        self.into = into

    def SetProperty(self, name: str, value: Any) -> None:  # noqa: N802 - COM's spelling
        self.into[name] = value


class FakeAttachment:
    def __init__(self, path: str, properties: dict[str, Any]) -> None:
        self.path = path
        self.PropertyAccessor = FakeAccessor(properties)


class FakeAttachments:
    def __init__(self, record: list[FakeAttachment], properties: dict[str, Any]) -> None:
        self.record = record
        self.properties = properties

    def Add(self, path: str) -> FakeAttachment:  # noqa: N802 - COM's spelling
        attachment = FakeAttachment(path, self.properties)
        self.record.append(attachment)
        return attachment


class FakeParent:
    Name = "Drafts"


class FakeItem:
    """An Outlook mail item with no way to send. Anything that reached for a
    delivering verb would raise here, which is the point."""

    def __init__(self) -> None:
        self.Subject = ""
        self.HTMLBody = ""
        self.To = ""
        self.CC = ""
        self.EntryID = "0000FEEDFACE"
        self.Parent = FakeParent()
        self.saves = 0
        self.attached: list[FakeAttachment] = []
        self.properties: dict[str, Any] = {}
        self.Attachments = FakeAttachments(self.attached, self.properties)

    def Save(self) -> None:  # noqa: N802 - COM's spelling
        self.saves += 1


class FakeOutlook:
    def __init__(self) -> None:
        self.item = FakeItem()
        self.created: list[int] = []

    def CreateItem(self, kind: int) -> FakeItem:  # noqa: N802 - COM's spelling
        self.created.append(kind)
        return self.item


def draft(**changes: Any) -> MailDraft:
    values: dict[str, Any] = {
        "subject": "GTM weekly report 2026_39W",
        "html_body": "<div>four tickets</div>",
        "to": ("team@example.com",),
    }
    values.update(changes)
    return MailDraft(**values)


def test_the_module_cannot_send_because_it_never_says_so() -> None:
    """The failure this prevents is a mail about the team's work arriving in
    the team's inbox unread. Asserted against the source text, so a future
    edit that adds a delivering call fails here rather than in somebody's
    outbox."""
    source = inspect.getsource(outlook_draft)
    for forbidden in (".Send(", "Send()", "olSend", "SendAndSave", "Deliver"):
        assert forbidden not in source, f"this module reached for {forbidden}"


def test_a_draft_is_saved_and_lands_where_a_person_will_find_it() -> None:
    outlook = FakeOutlook()
    receipt = OutlookComDraft(dispatch=outlook).save(draft(cc=("lead@example.com",)))
    assert outlook.created == [0], "olMailItem"
    assert outlook.item.saves == 1, "saved exactly once"
    assert outlook.item.Subject == "GTM weekly report 2026_39W"
    assert outlook.item.To == "team@example.com"
    assert outlook.item.CC == "lead@example.com"
    assert receipt.saved is True
    assert receipt.entry_id == "0000FEEDFACE"
    assert receipt.folder == "Drafts"


def test_several_recipients_are_joined_the_way_outlook_reads_them() -> None:
    outlook = FakeOutlook()
    OutlookComDraft(dispatch=outlook).save(draft(to=("a@example.com", "b@example.com")))
    assert outlook.item.To == "a@example.com; b@example.com"


def test_the_chart_is_attached_as_the_body_refers_to_it(tmp_path: Path) -> None:
    """A picture whose content id is not set is an attachment at the bottom
    and a broken image in the body."""
    picture = tmp_path / "chart.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n")
    outlook = FakeOutlook()
    OutlookComDraft(dispatch=outlook).save(
        draft(images=(InlineImage(cid="effort-chart", path=str(picture)),))
    )
    assert len(outlook.item.attached) == 1
    assert outlook.item.attached[0].path == str(picture.resolve())
    assert outlook.item.properties[outlook_draft._CONTENT_ID] == "effort-chart"
    assert outlook.item.properties[outlook_draft._HIDDEN] is True, "not also listed as a file"


def test_a_missing_picture_leaves_no_half_built_draft(tmp_path: Path) -> None:
    """Checked before Outlook is touched: a broken run must not leave an item
    in somebody's drafts for them to puzzle over."""
    outlook = FakeOutlook()
    with pytest.raises(DraftError) as raised:
        OutlookComDraft(dispatch=outlook).save(
            draft(images=(InlineImage(cid="c", path=str(tmp_path / "nothing.png")),))
        )
    assert raised.value.code == "attachment_missing"
    assert outlook.created == [], "Outlook was never asked for an item"


def test_what_com_raises_is_not_repeated_back(tmp_path: Path) -> None:
    """A COM message can carry the subject line and the recipients, and this
    host does not echo the team's own data into a log."""

    class Angry:
        def CreateItem(self, _kind: int) -> Any:  # noqa: N802 - COM's spelling
            raise RuntimeError("could not create mail to team@example.com about 2026_39W")

    with pytest.raises(DraftError) as raised:
        OutlookComDraft(dispatch=Angry()).save(draft())
    assert raised.value.code == "draft_failed"
    assert "team@example.com" not in str(raised.value)
    assert str(raised.value) == "draft_failed"


def test_the_recording_writer_keeps_what_it_was_given(tmp_path: Path) -> None:
    picture = tmp_path / "chart.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n")
    writer = RecordingDraftWriter()
    receipt = writer.save(draft(images=(InlineImage(cid="c", path=str(picture)),)))
    assert receipt.saved is True
    assert len(writer.drafts) == 1
    assert writer.drafts[0].subject == "GTM weekly report 2026_39W"
    with pytest.raises(DraftError):
        writer.save(draft(images=(InlineImage(cid="c", path=str(tmp_path / "no.png")),)))


def test_the_chart_is_written_beside_the_draft_and_named(tmp_path: Path) -> None:
    images, cid = outlook_draft.images_for(b"\x89PNG\r\n\x1a\n", tmp_path / "mail")
    assert cid == "effort-chart"
    assert len(images) == 1
    assert Path(images[0].path).read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_a_week_with_no_chart_asks_for_no_picture(tmp_path: Path) -> None:
    assert outlook_draft.images_for(None, tmp_path) == ((), "")
    assert not (tmp_path / "effort-chart.png").exists()


def test_blank_recipients_are_dropped_and_the_rest_left_alone() -> None:
    """Not validated here: what an address may look like is Outlook's rule,
    and a host guessing wrong would refuse a draft nobody asked it to judge."""
    assert outlook_draft.recipients([" a@example.com ", "", "  ", "b"]) == ("a@example.com", "b")
