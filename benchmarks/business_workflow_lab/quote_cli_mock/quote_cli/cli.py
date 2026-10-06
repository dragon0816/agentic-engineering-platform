"""quote_cli: the synthetic quote system's public command line.

Contract (stable, schema_version 1):
  quote_cli --help
  quote_cli customers list --format json
  quote_cli quotes list [--customer C001] [--project P001] [--from YYYY-MM-DD]
                        [--to YYYY-MM-DD] [--status Draft|Sent|Accepted|Expired]
                        [--format json|table]
  quote_cli quotes get Q0001 [--format json|table]
  quote_cli quotes export [filters as list] --output quotes.csv

Every filter is optional and filters combine with AND; dates include both
ends. stdout carries only the result (JSON or table); errors and diagnostics
go to stderr. Money is a decimal string in JSON ("1234.50"): parse it with a
decimal type, not a float. Nothing here creates or changes a quote.

Exit codes: 0 success (zero rows included), 2 invalid arguments, 3 document
not found, 4 temporary service error (retry later).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

LAB = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("QUOTE_CLI_DATA") or LAB / "operator" / "data" / "source.json")
STATE = LAB / "operator" / "state"
FAULT = STATE / "quote_fault.json"
EVENTS = STATE / "quote_events.jsonl"
STATUSES = ("Draft", "Sent", "Accepted", "Expired")
HEADER_FIELDS = ["QuoteID", "CustomerID", "ProjectID", "QuoteDate", "ValidUntil", "Status",
                 "Currency", "Subtotal", "DiscountPercent", "NetAmount"]
LINE_FIELDS = ["ProductID", "ProductName", "Quantity", "UnitPrice", "LineAmount"]
OK, BAD_ARGS, NOT_FOUND, TEMPORARY = 0, 2, 3, 4


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message)


def event(kind: str, **detail: Any) -> None:
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        line = {"at": datetime.now().isoformat(timespec="milliseconds"), "event": kind, **detail}
        with EVENTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass  # the operator log never changes what the CLI answers


def injected_failure(argv: list[str]) -> int | None:
    """The operator's fault mode: transient_once or force_exit2."""
    try:
        state = json.loads(FAULT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    mode = state.get("mode", "normal")
    if mode == "force_exit2":
        event("fault_force_exit2", argv=argv)
        print("quote_cli: error: the quote service rejected the request parameters "
              "(operator scenario: wrapper fixed to exit 2)", file=sys.stderr)
        return BAD_ARGS
    if mode == "transient_once" and not state.get("fired"):
        state["fired"] = True
        try:
            FAULT.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            return None  # a caller that cannot reach the service state gets no injected fault
        event("fault_transient_injected", argv=argv)
        print("quote_cli: error: quote service temporarily unavailable, retry later", file=sys.stderr)
        return TEMPORARY
    return None


def iso(text: str) -> str:
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}, expected YYYY-MM-DD") from error


def add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--customer", help="CustomerID, e.g. C001 (exact match)")
    parser.add_argument("--project", help="ProjectID, e.g. P001 (exact match)")
    parser.add_argument("--from", dest="date_from", type=iso, help="QuoteDate on or after (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", type=iso, help="QuoteDate on or before (YYYY-MM-DD)")
    parser.add_argument("--status", choices=STATUSES, help="quote status")


def build_parser() -> Parser:
    parser = Parser(prog="quote_cli", description=__doc__,
                    formatter_class=argparse.RawDescriptionHelpFormatter)
    top = parser.add_subparsers(dest="group", required=True, parser_class=Parser)
    customers = top.add_parser("customers", help="customer master data")
    customers_sub = customers.add_subparsers(dest="action", required=True, parser_class=Parser)
    customers_list = customers_sub.add_parser("list", help="list customers")
    customers_list.add_argument("--format", choices=("json", "table"), default="table")
    quotes = top.add_parser("quotes", help="quotes")
    quotes_sub = quotes.add_subparsers(dest="action", required=True, parser_class=Parser)
    quotes_list = quotes_sub.add_parser("list", help="list quote headers matching all filters")
    add_filters(quotes_list)
    quotes_list.add_argument("--format", choices=("json", "table"), default="table")
    quotes_get = quotes_sub.add_parser("get", help="one quote with its line items")
    quotes_get.add_argument("quote_id")
    quotes_get.add_argument("--format", choices=("json", "table"), default="table")
    quotes_export = quotes_sub.add_parser("export", help="write matching quote headers to a CSV file")
    add_filters(quotes_export)
    quotes_export.add_argument("--output", required=True, help="CSV path to write (UTF-8 with BOM)")
    return parser


def selected(quotes: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    out = []
    for quote in quotes:
        if args.customer and quote["CustomerID"] != args.customer:
            continue
        if args.project and quote["ProjectID"] != args.project:
            continue
        if args.status and quote["Status"] != args.status:
            continue
        if args.date_from and quote["QuoteDate"] < args.date_from:
            continue
        if args.date_to and quote["QuoteDate"] > args.date_to:
            continue
        out.append({k: quote[k] for k in HEADER_FIELDS})
    return sorted(out, key=lambda q: q["QuoteID"])


def table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    widths = {f: max([len(f)] + [len(str(r.get(f, ""))) for r in rows]) for f in fields}
    lines = ["  ".join(f.ljust(widths[f]) for f in fields)]
    lines += ["  ".join(str(r.get(f, "")).ljust(widths[f]) for f in fields) for r in rows]
    return "\n".join(lines)


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as error:
        event("usage_error", argv=argv)
        parser.print_usage(sys.stderr)
        print(f"quote_cli: error: {error}", file=sys.stderr)
        return BAD_ARGS
    except SystemExit as stop:  # --help
        return int(stop.code or 0)
    failure = injected_failure(argv)
    if failure is not None:
        return failure
    data = json.loads(DATA.read_text(encoding="utf-8"))
    # argv0 tells a real CLI process (the module or launcher) from a script
    # that imported this module and called main() in its own process.
    event("command", argv=argv, argv0=sys.argv[0] if sys.argv else "", pid=os.getpid())
    if args.group == "customers":
        rows = [{"CustomerID": c["CustomerID"], "CustomerName": c["CustomerName"]} for c in data["customers"]]
        if args.format == "json":
            emit({"schema_version": 1, "items": rows, "count": len(rows)})
        else:
            print(table(rows, ["CustomerID", "CustomerName"]))
        return OK
    if args.action == "get":
        quote = next((q for q in data["quotes"] if q["QuoteID"] == args.quote_id), None)
        if quote is None:
            print(f"quote_cli: error: quote {args.quote_id} not found", file=sys.stderr)
            return NOT_FOUND
        header = {k: quote[k] for k in HEADER_FIELDS}
        lines = [{k: line[k] for k in LINE_FIELDS} for line in quote["Lines"]]
        if args.format == "json":
            emit({"schema_version": 1, "header": header, "line_items": lines})
        else:
            print(table([header], HEADER_FIELDS))
            print()
            print(table(lines, LINE_FIELDS))
        return OK
    if args.date_from and args.date_to and args.date_from > args.date_to:
        print("quote_cli: error: --from is after --to", file=sys.stderr)
        return BAD_ARGS
    rows = selected(data["quotes"], args)
    if args.action == "list":
        if args.format == "json":
            emit({"schema_version": 1, "items": rows, "count": len(rows)})
        else:
            print(table(rows, HEADER_FIELDS))
            print(f"({len(rows)} rows)")
        return OK
    target = Path(args.output)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER_FIELDS, lineterminator="\r\n")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as error:
        print(f"quote_cli: error: cannot write {target}: {error}", file=sys.stderr)
        return BAD_ARGS
    emit({"schema_version": 1, "output": str(target), "rows": len(rows)})
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
