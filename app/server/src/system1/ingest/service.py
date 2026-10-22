import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.config import get_settings
from system1.context.extract import clean_name, clean_text
from system1.datasets import service as dataset_service
from system1.datasets.service import NewExample
from system1.domain.policy import MAX_OPTIONS, MIN_OPTIONS, Option, Policy, validate_policy
from system1.errors import NotFound
from system1.ingest.models import StagedUpload
from system1.ingest.parse import IngestError, parse_table
from system1.projects import service as project_service
from system1.projects.models import Project, now

STAGED_TTL = timedelta(hours=1)
MAX_STAGED_PER_PROJECT = 5
PREVIEW_ROWS = 20
MAX_KEY_CHARS = 40
MAX_BUCKET_NAME_CHARS = 80
NOT_FOUND = "That upload has expired or doesn't exist. Upload the file again."


class Staged(BaseModel):
    upload_id: str
    columns: list[str]
    preview: list[dict[str, str]]
    row_count: int
    # Filled by preview_labels once a label column is chosen.
    label_values: dict[str, int] = Field(default_factory=dict)


class ImportMapping(BaseModel):
    input_columns: list[str] = Field(min_length=1)
    label_column: str
    # Maps an upload value (as the labels route returns it) to a bucket key, or None to drop those rows.
    label_map: dict[str, str | None] = Field(default_factory=dict)
    create_buckets: bool = False


class ImportResult(BaseModel):
    added: int
    skipped_duplicates: int
    dropped_rows: int
    too_long: int  # part of dropped_rows
    created_buckets: list[str]


def _owned(project: Project, principal: Principal) -> None:
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")


def _value(raw: str) -> str:
    return " ".join(clean_text(raw).split())


def _purge(session: Session) -> None:
    session.execute(delete(StagedUpload).where(StagedUpload.created_at < now() - STAGED_TTL))


def stage_upload(session: Session, project: Project, principal: Principal, filename: str, data: bytes) -> Staged:
    _owned(project, principal)
    table = parse_table(clean_name(filename), data)  # nothing is written if the file can't be read
    _purge(session)
    staged = StagedUpload(
        org_id=project.org_id, project_id=project.id, rows_json={"columns": table.columns, "rows": table.rows}
    )
    session.add(staged)
    session.flush()
    newest = session.scalars(
        select(StagedUpload.id)
        .where(StagedUpload.project_id == project.id)
        .order_by(StagedUpload.created_at.desc(), StagedUpload.id)
    ).all()
    if len(newest) > MAX_STAGED_PER_PROJECT:
        session.execute(delete(StagedUpload).where(StagedUpload.id.in_(newest[MAX_STAGED_PER_PROJECT:])))
    session.commit()
    return Staged(
        upload_id=staged.id, columns=table.columns, preview=table.rows[:PREVIEW_ROWS], row_count=len(table.rows)
    )


def _load(session: Session, project: Project, upload_id: str) -> StagedUpload:
    staged = session.get(StagedUpload, upload_id)
    # One message for missing, expired and other-project/org uploads: ids reveal nothing.
    if staged is None or staged.project_id != project.id or staged.org_id != project.org_id:
        raise NotFound(NOT_FOUND)
    created = staged.created_at if staged.created_at.tzinfo else staged.created_at.replace(tzinfo=UTC)
    if created < now() - STAGED_TTL:
        raise NotFound(NOT_FOUND)
    return staged


def _require_column(columns: list[str], name: str) -> None:
    if name not in columns:
        raise IngestError(f"The file has no column called '{name}'.")


def _label_counts(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    """Counts per label, merging values that differ only by case or spacing. The first spelling seen is kept."""
    spelling: dict[str, str] = {}
    counts: dict[str, int] = {}
    for row in rows:
        value = _value(row.get(column, ""))
        if not value:
            continue
        key = value.casefold()
        spelling.setdefault(key, value)
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts, key=lambda k: -counts[k])  # stable: ties keep first-seen order
    return {spelling[k]: counts[k] for k in ordered}


def preview_labels(session: Session, project: Project, upload_id: str, label_column: str) -> dict[str, int]:
    staged = _load(session, project, upload_id)
    _require_column(staged.rows_json["columns"], label_column)
    return _label_counts(staged.rows_json["rows"], label_column)


def _input_text(row: dict[str, str], columns: list[str]) -> str:
    if len(columns) == 1:
        return clean_text(row.get(columns[0], ""))
    parts = [(c, clean_text(row.get(c, ""))) for c in columns]
    return "\n".join(f"{c}: {v}" for c, v in parts if v)


def _snake(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    if not slug:
        slug = "bucket"
    elif not slug[0].isalpha():
        slug = f"bucket_{slug}"
    return slug[:MAX_KEY_CHARS].rstrip("_")


def _unique_key(value: str, taken: set[str]) -> str:
    base = _snake(value)
    key, n = base, 2
    while key in taken:
        suffix = f"_{n}"
        key = f"{base[: MAX_KEY_CHARS - len(suffix)].rstrip('_')}{suffix}"
        n += 1
    return key


def _existing_buckets(policy: Policy) -> list[tuple[str, set[str]]]:
    """Each existing bucket's key with the spellings an upload value may match it by."""
    return [(o.key, {o.key, _snake(o.key), _snake(o.name), o.name.casefold()}) for o in policy.options]


def _match_existing(value: str, existing: list[tuple[str, set[str]]]) -> str | None:
    """A value that already names a bucket (by key or name, ignoring case) goes there instead of a lookalike."""
    spellings = {value.casefold(), _snake(value)}
    return next((key for key, names in existing if spellings & names), None)


@dataclass
class _Candidate:
    text: str
    label: str  # canonical upload value


def import_upload(
    session: Session, project: Project, principal: Principal, upload_id: str, mapping: ImportMapping
) -> ImportResult:
    _owned(project, principal)
    staged = _load(session, project, upload_id)
    columns: list[str] = staged.rows_json["columns"]
    rows: list[dict[str, str]] = staged.rows_json["rows"]
    inputs = list(dict.fromkeys(mapping.input_columns))
    for name in [*inputs, mapping.label_column]:
        _require_column(columns, name)
    if mapping.label_column in inputs:
        raise IngestError("The decision column can't also be part of what comes in.")

    limit = get_settings().max_input_chars
    spelling = {v.casefold(): v for v in _label_counts(rows, mapping.label_column)}
    candidates: list[_Candidate] = []
    dropped = too_long = 0
    for row in rows:
        label = spelling.get(_value(row.get(mapping.label_column, "")).casefold())
        text = _input_text(row, inputs)
        if label is None or not text:
            dropped += 1
        elif len(text) > limit:
            dropped += 1
            too_long += 1
        else:
            candidates.append(_Candidate(text, label))

    policy, _ = project_service.latest_policy(session, project)
    taken = {o.key for o in policy.options}
    chosen = {_value(k).casefold(): v for k, v in mapping.label_map.items()}
    # Every target is checked, including those of values with no surviving rows, so a typo never goes unnoticed.
    for target in mapping.label_map.values():
        if target is not None and target not in taken:
            raise IngestError(f"'{target}' isn't a bucket in this project.")
    existing = _existing_buckets(policy)
    target_of: dict[str, str] = {}  # canonical upload value -> bucket key
    new_options: list[Option] = []
    for value in dict.fromkeys(c.label for c in candidates):
        norm = value.casefold()
        if norm in chosen:
            target = chosen[norm]
            if target is not None:
                target_of[value] = target
        elif mapping.create_buckets:
            match = _match_existing(value, existing)
            if match is not None:
                target_of[value] = match
                continue
            key = _unique_key(value, taken)
            taken.add(key)
            target_of[value] = key
            new_options.append(Option(key=key, name=value[:MAX_BUCKET_NAME_CHARS]))

    kept = [NewExample(c.text, target_of[c.label], "uploaded") for c in candidates if c.label in target_of]
    dropped += len(candidates) - len(kept)

    new_policy: Policy | None = None
    if new_options:
        new_policy = policy.model_copy(update={"options": [*policy.options, *new_options]})
        total = len(new_policy.options)
        if total > MAX_OPTIONS:
            raise IngestError(
                f"That would make {total} buckets and the limit is {MAX_OPTIONS}. "
                "Map some labels to existing buckets or drop them."
            )
        if total < MIN_OPTIONS:
            raise IngestError(f"A project needs at least {MIN_OPTIONS} buckets, and this file only adds {total}.")
        issues = validate_policy(new_policy)
        if issues:
            raise IngestError(f"The new buckets aren't valid: {issues[0].message}.")

    # The new policy version, the examples and the removal of the staged copy commit together or not at all.
    try:
        if new_policy is not None:
            project_service.save_policy(session, principal, project, new_policy, commit=False)
        added = dataset_service.add_examples(session, project, kept, commit=False)
        session.delete(staged)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return ImportResult(
        added=added,
        skipped_duplicates=len(kept) - added,
        dropped_rows=dropped,
        too_long=too_long,
        created_buckets=[o.key for o in new_options],
    )
