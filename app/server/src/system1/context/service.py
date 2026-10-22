from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from system1.auth.principal import Principal
from system1.context.extract import EmptyText, TooMuchText, clean_name, clean_text
from system1.context.models import ContextDoc
from system1.datasets.constants import CONTEXT_MAX_FILE_BYTES, CONTEXT_MAX_FILES, CONTEXT_PROMPT_CHARS
from system1.errors import ApiError, NotFound
from system1.projects.models import Project


class TooManyFiles(ApiError):
    status_code = 422
    code = "too_many_files"
    message = f"A project can hold up to {CONTEXT_MAX_FILES} context files."


class FileTooLarge(ApiError):
    status_code = 413
    code = "file_too_large"
    message = f"That file is over {CONTEXT_MAX_FILE_BYTES // 1_000_000} MB."


def _owned(project: Project, principal: Principal) -> None:
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")


def list_docs(session: Session, principal: Principal, project: Project) -> list[ContextDoc]:
    _owned(project, principal)
    stmt = (
        select(ContextDoc)
        .where(ContextDoc.project_id == project.id)
        .options(defer(ContextDoc.text))
        .order_by(ContextDoc.created_at, ContextDoc.id)
    )
    return list(session.scalars(stmt))


def add_doc(session: Session, project: Project, principal: Principal, name: str, kind: str, text: str) -> ContextDoc:
    _owned(project, principal)
    name = clean_name(name) or "Pasted text"
    text = clean_text(text)
    if not text:
        raise EmptyText("There's no text to add.")
    if len(text) > CONTEXT_MAX_FILE_BYTES:
        raise TooMuchText()
    count = session.scalar(select(func.count()).select_from(ContextDoc).where(ContextDoc.project_id == project.id))
    if (count or 0) >= CONTEXT_MAX_FILES:
        raise TooManyFiles()
    doc = ContextDoc(org_id=project.org_id, project_id=project.id, name=name, kind=kind, text=text, chars=len(text))
    session.add(doc)
    session.commit()
    return doc


def delete_doc(session: Session, principal: Principal, project: Project, doc_id: str) -> None:
    _owned(project, principal)
    doc = session.get(ContextDoc, doc_id)
    if doc is None or doc.project_id != project.id:
        raise NotFound("That file doesn't exist.")
    session.delete(doc)
    session.commit()


def context_text(session: Session, project: Project, max_chars: int = CONTEXT_PROMPT_CHARS) -> str:
    """Callers must already have checked the project belongs to their org."""
    stmt = select(ContextDoc).where(ContextDoc.project_id == project.id).order_by(ContextDoc.created_at, ContextDoc.id)
    joined = "\n\n".join(f"--- {d.name} ---\n{d.text}" for d in session.scalars(stmt))
    return joined[:max_chars]
