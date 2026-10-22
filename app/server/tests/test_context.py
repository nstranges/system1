import io

from docx import Document
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.context import service as context_service
from system1.context.extract import extract_text
from system1.datasets.constants import CONTEXT_MAX_FILE_BYTES, CONTEXT_MAX_FILES
from system1.projects.service import get_project

PRINCIPAL = Principal(user_id="user_1", org_id="org_a", org_role="admin", org_slug="org_a")


def _project(client) -> str:
    return client.post("/api/projects", json={"name": "Triage"}).json()["id"]


def _upload(client, project_id: str, name: str, data: bytes):
    return client.post(f"/api/projects/{project_id}/context", files={"file": (name, data)})


def test_upload_txt_and_list(client_for):
    client = client_for("org_a")
    pid = _project(client)

    up = _upload(client, pid, "../../notes.txt", b"Refunds over $500 need approval.")
    assert up.status_code == 200
    assert up.json()["name"] == "notes.txt"
    assert up.json()["kind"] == "txt"
    assert "text" not in up.json()

    pasted = client.post(f"/api/projects/{pid}/context/paste", json={"name": "FAQ", "text": "Hello"})
    assert pasted.status_code == 200 and pasted.json()["kind"] == "paste"

    listed = client.get(f"/api/projects/{pid}/context").json()
    assert [d["name"] for d in listed] == ["notes.txt", "FAQ"]
    assert listed[0]["chars"] == len("Refunds over $500 need approval.")
    assert all(set(d) == {"id", "name", "kind", "chars", "created_at"} for d in listed)

    assert client.delete(f"/api/projects/{pid}/context/{listed[0]['id']}").status_code == 204
    assert len(client.get(f"/api/projects/{pid}/context").json()) == 1


def test_eleventh_file_rejected(client_for):
    client = client_for("org_a")
    pid = _project(client)
    for i in range(CONTEXT_MAX_FILES):
        assert _upload(client, pid, f"f{i}.txt", b"x").status_code == 200
    res = _upload(client, pid, "extra.txt", b"x")
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "too_many_files"
    assert res.json()["detail"]["message"] == "A project can hold up to 10 context files."


def test_other_org_gets_404_for_context(client_for):
    owner = client_for("org_a")
    pid = _project(owner)
    doc_id = _upload(owner, pid, "a.txt", b"secret").json()["id"]
    other = client_for("org_b", engine=owner.app.state.engine)

    for method, path, kwargs in [
        ("get", f"/api/projects/{pid}/context", {}),
        ("post", f"/api/projects/{pid}/context", {"files": {"file": ("a.txt", b"x")}}),
        ("post", f"/api/projects/{pid}/context/paste", {"json": {"name": "n", "text": "t"}}),
        ("delete", f"/api/projects/{pid}/context/{doc_id}", {}),
    ]:
        assert getattr(other, method)(path, **kwargs).status_code == 404, path
    assert len(owner.get(f"/api/projects/{pid}/context").json()) == 1


def test_unsupported_extension_422(client_for):
    client = client_for("org_a")
    pid = _project(client)
    res = _upload(client, pid, "malware.exe", b"MZ")
    assert res.status_code == 422
    assert res.json()["detail"] == {
        "code": "unsupported_file",
        "message": "Use a PDF, Word, Markdown or text file.",
    }


def test_context_text_truncates_to_limit(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _upload(client, pid, "a.txt", b"A" * 100)
    _upload(client, pid, "b.md", b"B" * 100)
    with Session(client.app.state.engine) as session:
        project = get_project(session, PRINCIPAL, pid)
        full = context_service.context_text(session, project)
        assert full == f"--- a.txt ---\n{'A' * 100}\n\n--- b.md ---\n{'B' * 100}"
        assert context_service.context_text(session, project, max_chars=30) == full[:30]


def test_oversized_upload_413_and_empty_text_422(client_for):
    client = client_for("org_a")
    pid = _project(client)
    big = _upload(client, pid, "big.txt", b"x" * (CONTEXT_MAX_FILE_BYTES + 1))
    assert big.status_code == 413
    assert big.json()["detail"]["message"] == "That file is over 2 MB."
    assert _upload(client, pid, "blank.txt", b"  \n\x00 ").json()["detail"]["code"] == "empty_text"
    too_long = client.post(
        f"/api/projects/{pid}/context/paste", json={"name": "n", "text": "x" * (CONTEXT_MAX_FILE_BYTES + 1)}
    )
    assert too_long.status_code == 413


def test_extract_docx_and_bad_pdf():
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Escalate outages.")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "P1"
    table.cell(0, 1).text = "15 min"
    doc.save(buf)
    kind, text = extract_text("Policy.DOCX", buf.getvalue())
    assert kind == "docx" and "Escalate outages." in text and "P1" in text

    import pytest

    from system1.context.extract import UnreadablePdf

    with pytest.raises(UnreadablePdf) as err:
        extract_text("x.pdf", b"not a pdf")
    assert err.value.message == "We couldn't read that PDF."


def test_deleting_a_project_removes_its_context(client_for):
    from sqlalchemy import func, select

    from system1.context.models import ContextDoc

    client = client_for("org_a")
    pid = _project(client)
    _upload(client, pid, "a.txt", b"x")
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(ContextDoc)) == 0
