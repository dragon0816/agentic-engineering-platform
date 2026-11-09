"""Shallow JSON object composition without implicit precedence or side effects."""

from pydantic import Field, JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext

SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "data", "name": "merge", "version": "1.0.0"},
        "name": "data.merge",
        "description": "Merge two bounded JSON objects; refuse conflicting duplicate keys",
        "input_contract": "data.merge.v1",
        "output_contract": "data.merged.v1",
        "side_effect": "read",
        "policy": {
            "risk": "low",
            "approval_required": False,
            "required_permissions": ["data.merge"],
            "policy_refs": ["data-policy"],
        },
    }
)


class MergeRequest(Contract):
    left: dict[str, JsonValue] = Field(max_length=1000)
    right: dict[str, JsonValue] = Field(max_length=1000)


class MergeResult(Contract):
    data: dict[str, JsonValue] = Field(max_length=2000)


class MergeHandler:
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = MergeRequest.model_validate(inputs)
        for key in request.left.keys() & request.right.keys():
            if not _equal_json(request.left[key], request.right[key]):
                # Neither names nor values from the data belong in errors/traces.
                raise CapabilityRefused("data_merge_conflict")
        return MergeResult(data={**request.left, **request.right})


def _equal_json(left: JsonValue, right: JsonValue) -> bool:
    """JSON booleans differ from numbers; numeric 1 and 1.0 remain equal.

    Apply that rule through containers, independent of object key order.
    This is comparison only: nested objects are never recursively merged.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict):
        return (
            isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_equal_json(value, right[key]) for key, value in left.items())
        )
    if isinstance(left, list):
        return (
            isinstance(right, list)
            and len(left) == len(right)
            and all(_equal_json(a, b) for a, b in zip(left, right, strict=True))
        )
    return left == right
