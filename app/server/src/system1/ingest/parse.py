"""Turns an uploaded CSV, Excel or JSONL file into a table of strings. The file is data and is never executed."""

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

import openpyxl

from system1.context.extract import clean_name, clean_text
from system1.datasets.constants import UPLOAD_MAX_BYTES, UPLOAD_MAX_ROWS
from system1.errors import ApiError

MAX_XLSX_UNZIPPED_BYTES = 50_000_000
# Spreadsheets often declare a million formatted-but-blank rows; stop looking long before the end of one.
MAX_XLSX_SCANNED_ROWS = 200_000
SNIFF_CHARS = 4096

UNREADABLE = "We couldn't read that file as CSV, Excel or JSONL."


class IngestError(ApiError):
    status_code = 422
    code = "bad_upload"
    message = UNREADABLE


class FileTooLarge(IngestError):
    status_code = 413
    code = "file_too_large"
    message = f"That file is over {UPLOAD_MAX_BYTES // 1_000_000} MB."


@dataclass
class Table:
    columns: list[str]
    rows: list[dict[str, str]]


def _too_many_rows() -> IngestError:
    return IngestError(f"That file has more than {UPLOAD_MAX_ROWS:,} rows.")


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if hasattr(value, "isoformat"):
        return clean_text(value.isoformat())
    return clean_text(str(value))


def _names(raw: list[str]) -> list[str]:
    """Column names stripped and made unique, so two columns can never share a key."""
    out: list[str] = []
    for name in raw:
        name = " ".join(clean_text(name).split())
        if not name:
            raise IngestError("Every column needs a name in the first row.")
        candidate, n = name, 2
        while candidate in out:
            candidate = f"{name} ({n})"
            n += 1
        out.append(candidate)
    return out


def _build(header: list[str], body: list[list[str]]) -> Table:
    columns = _names(header)
    rows = []
    for cells in body:
        values = [_cell(c) for c in cells[: len(columns)]]
        values += [""] * (len(columns) - len(values))
        if any(values):
            rows.append(dict(zip(columns, values, strict=True)))
            if len(rows) > UPLOAD_MAX_ROWS:
                raise _too_many_rows()
    if not rows:
        raise IngestError("That file has no rows.")
    return Table(columns, rows)


def _decode(data: bytes) -> str:
    if b"\x00" in data:
        raise IngestError()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise IngestError() from None


def _csv_table(data: bytes) -> Table:
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:SNIFF_CHARS], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    try:
        records = csv.reader(io.StringIO(text, newline=""), dialect)
        header = next(records, [])
        # +2 leaves room for blank lines between records; _build enforces the real limit.
        body = []
        for record in records:
            body.append(record)
            if len(body) > UPLOAD_MAX_ROWS * 2 + 2:
                raise _too_many_rows()
    except csv.Error:
        raise IngestError() from None
    return _build(header, body)


def _jsonl_table(data: bytes) -> Table:
    objects: list[dict] = []
    for line in _decode(data).splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            raise IngestError() from None
        if not isinstance(obj, dict):
            raise IngestError()
        objects.append(obj)
        if len(objects) > UPLOAD_MAX_ROWS:
            raise _too_many_rows()
    raw_keys = list(dict.fromkeys(k for obj in objects for k in obj))
    body = [[_json_value(obj[k]) if k in obj else "" for k in raw_keys] for obj in objects]
    return _build(raw_keys, body)


def _json_value(value: object) -> str:
    return value if isinstance(value, str) else ("" if value is None else json.dumps(value))


def _xlsx_table(data: bytes) -> Table:
    # Same boundary as the document parsers: openpyxl has no stable exception contract on hostile input.
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_XLSX_UNZIPPED_BYTES:
                raise IngestError()
        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            sheet = book.worksheets[0]
            header: list[str] | None = None
            body: list[list[str]] = []
            for scanned, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                if scanned > MAX_XLSX_SCANNED_ROWS:
                    raise IngestError()
                cells = [_cell(c) for c in row]
                if not any(cells):
                    continue
                if header is None:
                    header = cells
                    continue
                body.append(cells)
                if len(body) > UPLOAD_MAX_ROWS:
                    raise _too_many_rows()
        finally:
            book.close()
        if header is None:
            raise IngestError("That file is empty.")
        while header and not header[-1]:
            header.pop()  # trailing blank header cells are formatting, not columns
        return _build(header, body)
    except IngestError:
        raise
    except Exception:  # noqa: BLE001 - boundary around a parser with no stable exception contract
        raise IngestError() from None


def parse_table(filename: str, data: bytes) -> Table:
    if len(data) > UPLOAD_MAX_BYTES:
        raise FileTooLarge()
    if not data.strip():
        raise IngestError("That file is empty.")
    suffix = PurePosixPath(clean_name(filename).lower()).suffix
    if suffix == ".xlsx" or (suffix not in {".csv", ".tsv", ".txt", ".jsonl", ".ndjson"} and data[:2] == b"PK"):
        return _xlsx_table(data)
    if suffix in {".jsonl", ".ndjson"} or (suffix not in {".csv", ".tsv", ".txt"} and data.lstrip()[:1] == b"{"):
        return _jsonl_table(data)
    return _csv_table(data)
