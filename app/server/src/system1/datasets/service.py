import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.datasets.constants import MIN_PER_BUCKET, MIN_TEST_PER_BUCKET, REVIEW_CARDS, SPLIT
from system1.datasets.models import Example
from system1.domain.policy import Policy, validate_policy
from system1.errors import ApiError, NotFound, PolicyInvalid
from system1.projects import service as project_service
from system1.projects.models import Project, now

Source = Literal["uploaded", "generated", "corrected"]
SplitName = Literal["train", "cal", "test"]

# About one in eight of the non-test examples is held out for calibration (SPLIT: 0.1 cal vs 0.7 train).
CAL_ONE_IN = round(SPLIT["train"] / SPLIT["cal"] + 1)


class FrozenTestSet(ApiError):
    status_code = 409
    code = "test_set_frozen"
    message = "Test examples can't be changed once training has started."


class ResetRequired(ApiError):
    status_code = 409
    code = "test_reset_required"
    message = (
        "This bucket has test examples. Deleting it resets the test set, so earlier report cards "
        "can't be compared with new ones."
    )


class UnknownBucket(ApiError):
    status_code = 422
    code = "unknown_bucket"
    message = "Pick a bucket that exists."


class UnknownLabel(ApiError):
    status_code = 422
    code = "unknown_label"
    message = "Some examples use a label that isn't a bucket in this project."


@dataclass
class NewExample:
    input: str | dict
    label: str
    source: Source
    how_sure: float | None = None


class Health(BaseModel):
    per_bucket: dict[str, dict[str, int]]
    sources: dict[str, int]
    below_minimum: list[str]
    synthetic_test: bool
    frozen: bool
    test_set_version: int
    dataset_version: int


def normalize(value: str | dict) -> str:
    text = json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
    return re.sub(r"\s+", " ", text).strip().lower()


def _hash(project_id: str, value: str | dict) -> str:
    return hashlib.sha256(f"{project_id}:{normalize(value)}".encode()).hexdigest()


def _quota(total: int) -> int:
    return max(MIN_TEST_PER_BUCKET, round(SPLIT["test"] * total))


def _layout(hashes: list[str]) -> list[SplitName]:
    """Splits for every example of one bucket before the freeze: lowest hashes fill the test quota,
    then the highest of the rest go to calibration. A bucket too small to fill the quota and still
    train keeps everything in train until it grows."""
    n = len(hashes)
    if n < MIN_TEST_PER_BUCKET + 1:
        return ["train"] * n
    order = sorted(range(n), key=lambda i: (hashes[i], i))
    quota = _quota(n)
    cal = round((n - quota) / CAL_ONE_IN)
    out: list[SplitName] = ["train"] * n
    for rank, i in enumerate(order):
        if rank < quota:
            out[i] = "test"
        elif rank >= n - cal:
            out[i] = "cal"
    return out


def _order(project: Project):
    return lambda e: _hash(project.id, e.input_json)


def _rebalance(session: Session, project: Project, labels: set[str]) -> None:
    """Re-assigns the split of every example in these buckets. Only valid while nothing is frozen."""
    for label in labels:
        rows = list(
            session.scalars(
                select(Example).where(Example.project_id == project.id, Example.label == label).order_by(Example.id)
            )
        )
        for row, split in zip(rows, _layout([_hash(project.id, r.input_json) for r in rows]), strict=True):
            row.split = split


def _owned(project: Project, principal: Principal) -> None:
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")


def _bucket_keys(session: Session, project: Project) -> list[str]:
    policy, _ = project_service.latest_policy(session, project)
    return [o.key for o in policy.options]


def add_examples(session: Session, project: Project, rows: list[NewExample]) -> int:
    """Callers must already have checked the project belongs to their org."""
    known = set(_bucket_keys(session, project))
    unknown = list(dict.fromkeys(r.label for r in rows if r.label not in known))
    if unknown:
        shown = ", ".join(f"'{label}'" for label in unknown[:5])
        raise UnknownLabel(
            f"These labels aren't buckets in this project: {shown}{' and more' if len(unknown) > 5 else ''}."
        )
    seen = {normalize(v) for v in session.scalars(select(Example.input_json).where(Example.project_id == project.id))}
    fresh: list[NewExample] = []
    for row in rows:
        key = normalize(row.input)
        if key and key not in seen:
            seen.add(key)
            fresh.append(row)
    if not fresh:
        return 0

    project.dataset_version += 1
    new = [
        Example(
            org_id=project.org_id,
            project_id=project.id,
            input_json=r.input,
            label=r.label,
            source=r.source,
            split="train",
            how_sure=r.how_sure,
            dataset_version=project.dataset_version,
        )
        for r in fresh
    ]
    session.add_all(new)
    session.flush()

    if project.frozen_at is None:
        _rebalance(session, project, {r.label for r in new})
    else:
        _place_after_freeze(session, project, new)
    session.commit()
    return len(new)


def _place_after_freeze(session: Session, project: Project, new: list[Example]) -> None:
    """Existing examples never move. New ones go to train or calibration, except into a bucket that
    has fewer than the minimum test examples, which they fill first."""
    test_added = False
    for label in {e.label for e in new}:
        have = session.scalar(
            select(func.count())
            .select_from(Example)
            .where(Example.project_id == project.id, Example.label == label, Example.split == "test")
        )
        need = max(0, MIN_TEST_PER_BUCKET - (have or 0))
        # A correction never lands in test, even in a short bucket: it would grade the model on its own fixes.
        eligible = sorted((e for e in new if e.label == label and e.source != "corrected"), key=_order(project))
        filling = {e.id for e in eligible[:need]}
        for example in new:
            if example.label != label:
                continue
            if example.id in filling:
                example.split = "test"
                test_added = True
            elif int(_hash(project.id, example.input_json), 16) % CAL_ONE_IN == 0:
                example.split = "cal"
    if test_added:
        project.test_set_version += 1


def freeze(session: Session, project: Project) -> None:
    if project.frozen_at is None:
        # Review moves and relabels may have left the buckets off-quota; settle them before the set locks.
        labels = set(session.scalars(select(Example.label).where(Example.project_id == project.id).distinct()))
        session.flush()
        before = dict(session.execute(select(Example.id, Example.split).where(Example.project_id == project.id)).all())
        _rebalance(session, project, labels)
        session.flush()
        after = dict(session.execute(select(Example.id, Example.split).where(Example.project_id == project.id)).all())
        if before != after:
            project.dataset_version += 1
        project.frozen_at = now()
        session.commit()


def health(session: Session, project: Project) -> Health:
    policy, _ = project_service.latest_policy(session, project)
    per_bucket = {o.key: {"train": 0, "cal": 0, "test": 0, "total": 0} for o in policy.options}
    sources = {"uploaded": 0, "generated": 0, "corrected": 0}
    uploaded_test = False
    for label, source, split in session.execute(
        select(Example.label, Example.source, Example.split).where(Example.project_id == project.id)
    ):
        counts = per_bucket.setdefault(label, {"train": 0, "cal": 0, "test": 0, "total": 0})
        counts[split] += 1
        counts["total"] += 1
        sources[source] = sources.get(source, 0) + 1
        uploaded_test = uploaded_test or (split == "test" and source == "uploaded")
    return Health(
        per_bucket=per_bucket,
        sources=sources,
        below_minimum=[o.key for o in policy.options if per_bucket[o.key]["total"] < MIN_PER_BUCKET],
        synthetic_test=not uploaded_test,
        frozen=project.frozen_at is not None,
        test_set_version=project.test_set_version,
        dataset_version=project.dataset_version,
    )


def list_examples(
    session: Session, project: Project, split: str | None = None, source: str | None = None, limit: int = 50
) -> list[Example]:
    stmt = select(Example).where(Example.project_id == project.id)
    if split:
        stmt = stmt.where(Example.split == split)
    if source:
        stmt = stmt.where(Example.source == source)
    return list(session.scalars(stmt.order_by(Example.created_at, Example.id).limit(limit)))


def review_queue(session: Session, project: Project, limit: int = REVIEW_CARDS) -> list[Example]:
    stmt = select(Example).where(
        Example.project_id == project.id,
        Example.source == "generated",
        Example.how_sure.is_not(None),
        Example.review.is_(None),
    )
    if project.frozen_at is not None:
        stmt = stmt.where(Example.split != "test")
    return list(session.scalars(stmt.order_by(Example.how_sure, Example.id).limit(limit)))


def get_example(session: Session, principal: Principal, example_id: str) -> tuple[Example, Project]:
    example = session.get(Example, example_id)
    if example is None:
        raise NotFound("That example doesn't exist.")
    if example.org_id != principal.org_id:
        raise NotFound("That example doesn't exist.")  # same message as a missing one: no existence oracle
    return example, project_service.get_project(session, principal, example.project_id)


def review(
    session: Session, project: Project, example_id: str, action: Literal["agree", "move"], to: str | None = None
) -> Example:
    example = session.get(Example, example_id)
    if example is None or example.project_id != project.id:
        raise NotFound("That example doesn't exist.")
    if project.frozen_at is not None and example.split == "test":
        raise FrozenTestSet()
    if action == "move":
        if to is None or to not in _bucket_keys(session, project):
            raise UnknownBucket()
        if to == example.label:
            example.review = "agree"  # nothing to move, but the card is answered
        else:
            old = example.label
            example.label = to
            example.review = "moved"
            project.dataset_version += 1
            example.dataset_version = project.dataset_version
            if project.frozen_at is None:
                session.flush()
                _rebalance(session, project, {old, to})
    else:
        example.review = "agree"
    session.commit()
    return example


class DeleteBucketResult(BaseModel):
    policy_version: int
    examples_affected: int
    test_set_version: int


def delete_bucket(
    session: Session,
    principal: Principal,
    project: Project,
    key: str,
    mode: Literal["drop", "move"],
    to: str | None,
    reset_test: bool,
) -> DeleteBucketResult:
    _owned(project, principal)
    policy, _ = project_service.latest_policy(session, project)
    if key not in {o.key for o in policy.options}:
        raise NotFound("That bucket doesn't exist.")
    target: str | None = None
    if mode == "move":
        if to is None or to == key or to not in {o.key for o in policy.options}:
            raise UnknownBucket("Pick a different bucket to move the examples to.")
        target = to

    frozen_test = 0
    if project.frozen_at is not None:
        frozen_test = (
            session.scalar(
                select(func.count())
                .select_from(Example)
                .where(Example.project_id == project.id, Example.label == key, Example.split == "test")
            )
            or 0
        )
        if frozen_test and not reset_test:
            raise ResetRequired()

    # Validate the shrunken policy before touching any example.
    smaller = Policy.model_validate(
        {
            **policy.model_dump(by_alias=True),
            "options": [o.model_dump() for o in policy.options if o.key != key],
            "rules": [r.model_dump(by_alias=True) for r in policy.rules if r.label != key],
        }
    )
    issues = validate_policy(smaller)
    if issues:
        raise PolicyInvalid(issues)

    rows = list(session.scalars(select(Example).where(Example.project_id == project.id, Example.label == key)))
    if target is None:
        session.execute(delete(Example).where(Example.project_id == project.id, Example.label == key))
    else:
        for row in rows:
            row.label = target
    if rows:
        project.dataset_version += 1
    if frozen_test:
        project.test_set_version += 1
    elif target is not None and project.frozen_at is None and rows:
        session.flush()
        _rebalance(session, project, {target})
    version = project_service.save_policy(session, principal, project, smaller)
    return DeleteBucketResult(
        policy_version=version, examples_affected=len(rows), test_set_version=project.test_set_version
    )
