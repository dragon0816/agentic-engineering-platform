"""What every model call in knowledge code shares: an adapter that raises is
a retryable failure, never an escaping exception."""

from common.execution import Failure


def failure_from_exception(error: BaseException) -> Failure:
    message = f"{type(error).__name__}: {error}"[:200].strip() or type(error).__name__
    return Failure(code="model_error", message=message, retryable=True)
