import io
import json
import time
from datetime import timedelta

import openpyxl
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system1.datasets import service as dataset_service
from system1.datasets.constants import UPLOAD_MAX_BYTES, UPLOAD_MAX_COLUMNS, UPLOAD_MAX_ROWS
from system1.datasets.models import Example
from system1.domain.policy import MAX_OPTIONS
from system1.ingest.models import StagedUpload
from system1.ingest.parse import parse_table
from system1.projects.models import PolicyVersion, now

OPTIONS = [{"key": "refund", "name": "Refund"}, {"key": "other", "name": "Other"}]


def _project(client, options=OPTIONS) -> str:
    pid = client.post("/api/projects", json={"name": "Triage"}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": options}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    return pid


def _stage(client, pid: str, data: bytes, name: str = "tickets.csv"):
    return client.post(f"/api/projects/{pid}/uploads", files={"file": (name, data)})


def _csv(rows: list[tuple[str, str]], header: str = "text,kind") -> bytes:
    return ("﻿" + header + "\n" + "\n".join(f'"{a}",{b}' for a, b in rows) + "\n").encode()


def _import(client, pid: str, upload_id: str, **mapping):
    body = {"input_columns": ["text"], "label_column": "kind", "label_map": {}, "create_buckets": False} | mapping
    return client.post(f"/api/projects/{pid}/uploads/{upload_id}/import", json=body)


def _counts(client, pid: str) -> tuple[int, int]:
    with Session(client.app.state.engine) as session:
        examples = session.scalar(select(func.count()).select_from(Example).where(Example.project_id == pid))
        versions = session.scalar(
            select(func.count()).select_from(PolicyVersion).where(PolicyVersion.project_id == pid)
        )
        return examples or 0, versions or 0


def test_csv_with_bom_parses(client_for):
    client = client_for("org_a")
    pid = _project(client)
    res = _stage(client, pid, _csv([("Where is my refund?", "refund"), ("Hi there", "other")]))
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["text", "kind"]
    assert body["preview"][0] == {"text": "Where is my refund?", "kind": "refund"}
    assert body["row_count"] == 2


def test_empty_file_422(client_for):
    client = client_for("org_a")
    pid = _project(client)
    res = _stage(client, pid, b"  \n")
    assert res.status_code == 422
    assert res.json()["detail"]["message"] == "That file is empty."


def test_too_many_rows_422(client_for):
    client = client_for("org_a")
    pid = _project(client)
    data = ("text,kind\n" + "a,refund\n" * (UPLOAD_MAX_ROWS + 1)).encode()
    res = _stage(client, pid, data)
    assert res.status_code == 422
    assert res.json()["detail"]["message"] == "That file has more than 5,000 rows."
    assert _stage(client, pid, b"\x00\x01\x02binary").json()["detail"]["message"] == (
        "We couldn't read that file as CSV, Excel or JSONL."
    )


def test_label_case_and_whitespace_merge(client_for):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("a", " Refund "), ("b", "refund"), ("c", "Other"), ("d", "REFUND")])).json()
    res = client.get(f"/api/projects/{pid}/uploads/{up['upload_id']}/labels", params={"column": "kind"})
    assert res.status_code == 200
    assert res.json()["values"] == [{"value": "Refund", "count": 3}, {"value": "Other", "count": 1}]


def test_import_creates_buckets_and_examples(client_for):
    client = client_for("org_a")
    pid = _project(client)
    rows = [("Where is my refund?", "refund"), ("Reset my password", "Account Access"), ("Hello", "other")]
    rows += [("Where is my refund?", "REFUND")]  # exact duplicate input
    up = _stage(client, pid, _csv(rows)).json()
    res = _import(client, pid, up["upload_id"], label_map={"refund": "refund", "other": "other"}, create_buckets=True)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "added": 3,
        "skipped_duplicates": 1,
        "dropped_rows": 0,
        "too_long": 0,
        "created_buckets": ["account_access"],
    }
    policy = client.get(f"/api/projects/{pid}/policy").json()
    assert [o["key"] for o in policy["policy"]["options"]] == ["refund", "other", "account_access"]
    assert policy["policy"]["options"][2]["name"] == "Account Access"
    with Session(client.app.state.engine) as session:
        labels = {e.label: e.source for e in session.scalars(select(Example).where(Example.project_id == pid))}
    assert labels == {"refund": "uploaded", "account_access": "uploaded", "other": "uploaded"}
    # The staged copy is gone once it has been imported.
    assert _import(client, pid, up["upload_id"]).status_code == 404


def test_unmapped_label_without_create_is_dropped(client_for):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("a", "refund"), ("b", "mystery"), ("c", "skip me")])).json()
    res = _import(client, pid, up["upload_id"], label_map={"refund": "refund", "skip me": None})
    assert res.status_code == 200
    assert res.json() == {"added": 1, "skipped_duplicates": 0, "dropped_rows": 2, "too_long": 0, "created_buckets": []}
    assert _counts(client, pid) == (1, 2)


def test_missing_label_column_422_and_nothing_written(client_for):
    client = client_for("org_a")
    pid = _project(client)
    before = _counts(client, pid)
    up = _stage(client, pid, _csv([("a", "refund")])).json()
    res = _import(client, pid, up["upload_id"], label_column="nope", create_buckets=True)
    assert res.status_code == 422
    assert "nope" in res.json()["detail"]["message"]
    assert _counts(client, pid) == before


def test_new_buckets_over_the_limit_write_nothing(client_for):
    client = client_for("org_a")
    pid = _project(client)
    before = _counts(client, pid)
    rows = [(f"message {i}", f"kind {i}") for i in range(MAX_OPTIONS)]
    up = _stage(client, pid, _csv(rows)).json()
    res = _import(client, pid, up["upload_id"], create_buckets=True)
    assert res.status_code == 422
    assert str(MAX_OPTIONS) in res.json()["detail"]["message"]
    assert _counts(client, pid) == before


def test_long_rows_are_dropped_and_counted(client_for):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("short", "refund"), ("x" * 6001, "refund")])).json()
    res = _import(client, pid, up["upload_id"], label_map={"refund": "refund"})
    assert res.json()["added"] == 1
    assert res.json()["dropped_rows"] == 1 and res.json()["too_long"] == 1


def test_xlsx_and_jsonl_parse():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["text", "n"])
    sheet.append(["hello", 3])
    sheet.append([None, None])
    buf = io.BytesIO()
    book.save(buf)
    table = parse_table("t.xlsx", buf.getvalue())
    assert table.columns == ["text", "n"] and table.rows == [{"text": "hello", "n": "3"}]

    lines = "\n".join([json.dumps({"a": "x", "b": 1}), json.dumps({"a": "y", "c": None})]).encode()
    table = parse_table("t.jsonl", lines)
    assert table.columns == ["a", "b", "c"]
    assert table.rows == [{"a": "x", "b": "1", "c": ""}, {"a": "y", "b": "", "c": ""}]


def test_other_org_upload_404_and_staging_limits(client_for):
    engine_client = client_for("org_a")
    pid = _project(engine_client)
    up = _stage(engine_client, pid, _csv([("a", "refund")])).json()
    other = client_for("org_b", engine=engine_client.app.state.engine)
    res = other.get(f"/api/projects/{pid}/uploads/{up['upload_id']}/labels", params={"column": "kind"})
    assert res.status_code == 404

    # Only the newest five stay, and anything older than an hour is purged on the next upload.
    for _ in range(6):
        assert _stage(engine_client, pid, _csv([("a", "refund")])).status_code == 200
    with Session(engine_client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(StagedUpload)) == 5
        for row in session.scalars(select(StagedUpload)):
            row.created_at = now() - timedelta(hours=2)
        session.commit()
    assert _stage(engine_client, pid, _csv([("a", "refund")])).status_code == 200
    with Session(engine_client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(StagedUpload)) == 1


def test_deeply_nested_jsonl_is_a_plain_422(client_for):
    client = client_for("org_a")
    pid = _project(client)
    data = ('{"a": ' + "[" * 100_000 + "]" * 100_000 + "}").encode()
    res = _stage(client, pid, data, "t.jsonl")
    assert res.status_code == 422
    assert res.json()["detail"]["message"] == "We couldn't read that file as CSV, Excel or JSONL."


def test_column_count_is_bounded(client_for):
    client = client_for("org_a")
    pid = _project(client)
    wide = ",".join(f"c{i}" for i in range(UPLOAD_MAX_COLUMNS + 1)) + "\n" + "x\n"
    res = _stage(client, pid, wide.encode())
    assert res.status_code == 422
    assert res.json()["detail"]["message"] == "That file has more than 200 columns."

    keys = {f"k{i}": "x" for i in range(UPLOAD_MAX_COLUMNS + 1)}
    res = _stage(client, pid, json.dumps(keys).encode(), "t.jsonl")
    assert res.json()["detail"]["message"] == "That file has more than 200 columns."

    started = time.monotonic()
    res = _stage(client, pid, (",".join(["dup"] * 2000) + "\nx\n").encode())
    assert res.status_code == 422 and time.monotonic() - started < 1

    ok = _stage(client, pid, (",".join(["dup"] * UPLOAD_MAX_COLUMNS) + "\nx\n").encode())
    assert ok.status_code == 200 and ok.json()["columns"][:3] == ["dup", "dup (2)", "dup (3)"]


def test_xlsx_stray_far_cell_does_not_widen_rows():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["text", "kind"])
    sheet.append(["hello", "refund"])
    sheet["XFD2"] = "stray"
    sheet.append(["bye", "other"])
    buf = io.BytesIO()
    book.save(buf)
    started = time.monotonic()
    table = parse_table("t.xlsx", buf.getvalue())
    assert time.monotonic() - started < 2
    assert table.columns == ["text", "kind"]
    assert table.rows == [{"text": "hello", "kind": "refund"}, {"text": "bye", "kind": "other"}]


def test_trailing_blank_csv_headers_are_dropped():
    table = parse_table("t.csv", b"text,kind,,\nhello,refund,,\n")
    assert table.columns == ["text", "kind"]
    assert table.rows == [{"text": "hello", "kind": "refund"}]


def test_create_buckets_matches_existing_buckets_by_key_or_name(client_for):
    client = client_for("org_a")
    pid = _project(client, [{"key": "refund", "name": "Refund"}, {"key": "acct", "name": "Account Access"}])
    rows = [("a", "REFUND"), ("b", "account access"), ("c", "Billing")]
    up = _stage(client, pid, _csv(rows)).json()
    res = _import(client, pid, up["upload_id"], create_buckets=True)
    assert res.status_code == 200, res.text
    assert res.json()["created_buckets"] == ["billing"]
    keys = [o["key"] for o in client.get(f"/api/projects/{pid}/policy").json()["policy"]["options"]]
    assert keys == ["refund", "acct", "billing"]
    with Session(client.app.state.engine) as session:
        labels = sorted(e.label for e in session.scalars(select(Example).where(Example.project_id == pid)))
    assert labels == ["acct", "billing", "refund"]


def test_label_map_targets_are_checked_even_without_rows(client_for):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("a", "refund")])).json()
    res = _import(client, pid, up["upload_id"], label_map={"refund": "refund", "ghost": "nowhere"})
    assert res.status_code == 422 and "nowhere" in res.json()["detail"]["message"]
    assert _counts(client, pid) == (0, 2)


def test_oversized_upload_is_413(client_for):
    client = client_for("org_a")
    pid = _project(client)
    res = _stage(client, pid, b"a" * (UPLOAD_MAX_BYTES + 1))
    assert res.status_code == 413
    assert res.json()["detail"]["message"] == "That file is over 5 MB."


def test_expired_upload_is_404(client_for):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("a", "refund")])).json()
    with Session(client.app.state.engine) as session:
        session.get(StagedUpload, up["upload_id"]).created_at = now() - timedelta(hours=2)
        session.commit()
    res = client.get(f"/api/projects/{pid}/uploads/{up['upload_id']}/labels", params={"column": "kind"})
    assert res.status_code == 404
    assert _import(client, pid, up["upload_id"]).status_code == 404


def test_failure_after_the_policy_is_staged_rolls_everything_back(client_for, monkeypatch):
    client = client_for("org_a")
    pid = _project(client)
    up = _stage(client, pid, _csv([("a", "refund"), ("b", "Billing")])).json()

    def boom(*_args, **_kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(dataset_service, "add_examples", boom)
    with pytest.raises(RuntimeError):
        _import(client, pid, up["upload_id"], label_map={"refund": "refund"}, create_buckets=True)
    assert _counts(client, pid) == (0, 2)
    with Session(client.app.state.engine) as session:
        assert session.get(StagedUpload, up["upload_id"]) is not None


def test_csv_with_escaped_quotes_and_newlines_keeps_its_rows():
    from system1.ingest.parse import parse_table

    csv_text = 'text,decision\n"they said ""no"", please help, ok?",a\n"\nline two",b\nplain,a\n'
    table = parse_table("x.csv", csv_text.encode())
    assert [r["decision"] for r in table.rows] == ["a", "b", "a"]
    assert table.rows[0]["text"] == 'they said "no", please help, ok?'
