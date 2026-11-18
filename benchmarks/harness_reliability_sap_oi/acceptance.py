"""Keep artifact correctness distinct from successful end-to-end completion."""


def task_passed(status: str, artifact: bool, exporter: bool, downloaded_rows: int) -> bool:
    return status == "answered" and artifact and exporter and downloaded_rows == 16
