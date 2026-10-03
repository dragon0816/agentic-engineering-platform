"""Original Workflow 13 runtime parameter schema and x-ui hints.

This is source characterization, not an execution grant. AEP preview wiring
must force dryRun and keep commit/push behind Bridge policy.
"""

from __future__ import annotations

from typing import Any

PARAMS_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "release_package params",
    "type": "object",
    "additionalProperties": False,
    "required": ["companyName", "chipsetId", "generalTestcaseVersion", "cmpKtOption"],
    "properties": {
        # `description` is the prompt both front ends show, so these are
        # questions to a person, not notes to a programmer (BRIDGE_API 6.1).
        "companyName": {
            "type": "string",
            "minLength": 1,
            "description": "Which company is this release for?",
            "examples": ["Foxconn"],
            "x-ui": {"control": "text", "group": "identity", "order": 10},
        },
        "chipsetId": {
            "type": "string",
            "minLength": 1,
            "description": "Which chipset or licence id?",
            "examples": ["kt326"],
            "x-ui": {"control": "list", "options": "ref:chipsets",
                     "group": "identity", "order": 20},
        },
        "info": {
            "type": "string",
            "default": "",
            "description": "Any extra tag for the branch name?",
            "examples": ["demo"],
            "x-ui": {"control": "text", "group": "identity", "order": 30},
        },
        "cmpKtOption": {
            "type": "string",
            "enum": ["KT160", "KT161"],
            "description": (
                "Which CMP_KT_OPTION? It decides which half of release.yaml the build reads."
            ),
            "x-ui": {"control": "list", "order": 40},
        },
        "generalTestcaseVersion": {
            "type": "string",
            "minLength": 1,
            "description": "Which general testcase version?",
            "examples": ["v3.0.17"],
            "x-ui": {"control": "list",
                     "options": "ref:packageVersions:rs-wmt-general-testcase",
                     "order": 50},
        },
        # No x-ui below this line, deliberately. These are machinery -- a
        # dashboard or a phone has no business being asked for an upload set id
        # -- and 6.1's rule is that a field a front end should not offer simply
        # does not declare a control.
        "chipsetVersion": {
            "type": "string",
            "default": "",
            "description": "Which version of it?",
            # Follows `chipsetId`, which is why its order is higher: the two
            # interfaces ask in order, so the answer this depends on has to
            # already exist (BRIDGE_API 6.1). Not in the `identity` group --
            # company, chipset and info decide the branch name; the version
            # pinned inside it does not.
            "x-ui": {
                "control": "list",
                "options": "ref:packageVersions:{chipsetId}",
                "order": 25,
            },
        },
        "releaseVersion": {
            "type": "string",
            "default": "",
            "description": "VERSION in release.yaml. Empty: one more than the branch already has.",
        },
        "uploadSetId": {
            "type": "string",
            "default": "",
            "description": (
                "Id of files uploaded to the dashboard for this run. Fetched and placed by kind."
            ),
        },
        "notes": {
            "type": "string", "default": "",
            "description": "What changed in this release?",
            "examples": ["fixed the throughput test plan"],
            "x-ui": {"control": "text", "order": 60},
        },
        "testPlans": {
            "type": "array", "items": {"type": "string"}, "default": [],
            "description": "Test plan files (.json).",
            "x-ui": {"control": "upload", "accept": ".json", "multiple": True, "order": 70},
        },
        "configurations": {
            "type": "array", "items": {"type": "string"}, "default": [],
            "description": "Configuration files (.yaml).",
            "x-ui": {"control": "upload", "accept": ".yaml,.yml", "multiple": True, "order": 80},
        },
        "overlays": {
            "type": "array", "items": {"type": "string"}, "default": [],
            "description": "Overlay files.",
            "x-ui": {"control": "upload", "multiple": True, "order": 90},
        },
        "suffix": {"type": "string", "default": "",
                   "description": "SUFFIX in release.yaml (KT160 installer names only).",
                   "x-ui": {"control": "text", "order": 100}},
        "push": {"type": "boolean", "default": True,
                 "description": "Push the branch when done. Ignored on a dry run."},
        "dryRun": {"type": "boolean", "default": False,
                   "description": (
                       "Do everything except commit and push. The working copy still changes."
                   )},
    },
}
