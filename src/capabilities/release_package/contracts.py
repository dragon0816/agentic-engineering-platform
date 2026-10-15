"""Static checkout and runtime preview contracts for source Workflow 13."""

from pathlib import Path, PureWindowsPath
from typing import Self

from pydantic import ConfigDict, Field, StrictBool, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Text

from .planning import ReleaseRequest


def _absolute(value: str) -> bool:
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


class ReleasePreviewSettings(Contract):
    """Trusted Host paths. The selected branch must already be checked out."""

    checkout_path: Text
    inbox_path: Text

    @model_validator(mode="after")
    def guarded_paths(self) -> Self:
        if not _absolute(self.checkout_path) or not _absolute(self.inbox_path):
            raise ValueError("checkout_path and inbox_path must be absolute")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class IsolatedApplySettings(ReleasePreviewSettings):
    """Trusted test checkout boundary; never point this at a live release root."""

    allowed_root: Text

    @model_validator(mode="after")
    def absolute_root(self) -> Self:
        if not _absolute(self.allowed_root):
            raise ValueError("allowed_root must be absolute")
        return self


class ReleasePreviewRequest(Contract):
    """Original W13 runtime names; a version is mandatory in this preview slice.

    The step receives the whole run, which also carries this install's
    settings (merged by the engine), so fields that are not run names are
    ignored here; run fields were validated against the declaration upstream.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    company_name: Text = Field(alias="companyName")
    chipset_id: Text = Field(alias="chipsetId")
    cmp_kt_option: Text = Field(alias="cmpKtOption")
    chipset_version: Text = Field(alias="chipsetVersion")
    general_testcase_version: Text = Field(alias="generalTestcaseVersion")
    info: str = ""
    release_version: str = Field(default="", alias="releaseVersion")
    suffix: str = ""
    notes: str = ""
    test_plans: tuple[Text, ...] = Field(default=(), alias="testPlans")
    configurations: tuple[Text, ...] = ()
    overlays: tuple[Text, ...] = ()

    def to_release_request(self) -> ReleaseRequest:
        return ReleaseRequest(
            company_name=self.company_name,
            chipset_id=self.chipset_id,
            cmp_kt_option=self.cmp_kt_option,
            chipset_version=self.chipset_version,
            general_testcase_version=self.general_testcase_version,
            info=self.info,
            release_version=self.release_version,
            suffix=self.suffix,
            notes=self.notes,
            test_plans=self.test_plans,
            configurations=self.configurations,
            overlays=self.overlays,
        )


class ReleasePreviewStepInput(Contract):
    """The run's request plus this install's settings, selected by name."""

    request: ReleasePreviewRequest
    checkout_path: Text
    inbox_path: Text

    def settings(self) -> ReleasePreviewSettings:
        return ReleasePreviewSettings(checkout_path=self.checkout_path, inbox_path=self.inbox_path)


class IsolatedApplyStepInput(ReleasePreviewStepInput):
    allowed_root: Text

    def isolated_settings(self) -> IsolatedApplySettings:
        return IsolatedApplySettings(
            checkout_path=self.checkout_path,
            inbox_path=self.inbox_path,
            allowed_root=self.allowed_root,
        )


class ReleaseSelectedFile(Contract):
    kind: Text
    name: Text
    destination: Text
    sha256: Sha256


class ReleasePreview(Contract):
    branch: Text
    previous_version: str | None
    release_version: Text
    requirements: tuple[Text, Text]
    release_yaml: Text
    selected_files: tuple[ReleaseSelectedFile, ...]
    changed_paths: tuple[Text, ...]
    source_revision: Text
    committed: StrictBool = False
    pushed: StrictBool = False


class IsolatedApplyOutput(Contract):
    branch: Text
    previous_version: str | None
    release_version: Text
    requirements: tuple[Text, Text]
    changed_paths: tuple[Text, ...]
    selected_files: tuple[ReleaseSelectedFile, ...]
    source_revision: Text
    prepared: StrictBool = True
    committed: StrictBool = False
    pushed: StrictBool = False
