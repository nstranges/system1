from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.decisions.models import Decision, Feedback
from system1.domain.policy import Policy, validate_policy
from system1.errors import NotFound, PolicyInvalid
from system1.gateway.keys import ApiKey
from system1.projects.models import PolicyVersion, Project
from system1.templates.catalog import get_template


def _add_version(session: Session, project_id: str, version: int, policy: Policy, user_id: str) -> None:
    session.add(
        PolicyVersion(
            project_id=project_id, version=version, policy_json=policy.model_dump(by_alias=True), created_by=user_id
        )
    )


def _starter_policy(name: str) -> Policy:
    # Intentionally invalid (no options yet): the canvases show it as "not finished" and Try stays blocked.
    return Policy(decision_question=name, question_key="decision", inputs=[], options=[], rules=[])


def ensure_policy(session: Session, principal: Principal, project: Project) -> None:
    """Gives a project created before starter policies existed its version 1."""
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")
    has_any = session.scalar(
        select(func.count()).select_from(PolicyVersion).where(PolicyVersion.project_id == project.id)
    )
    if not has_any:
        _add_version(session, project.id, 1, _starter_policy(project.name), principal.user_id)
        session.commit()


def create_project(
    session: Session, principal: Principal, name: str, template_id: str | None = None, description: str | None = None
) -> Project:
    template = None
    if template_id is not None:
        try:
            template = get_template(template_id)
        except KeyError:
            raise NotFound("That template doesn't exist.") from None
    project = Project(
        org_id=principal.org_id,
        name=name,
        description=description if description is not None else (template.summary if template else None),
        template_id=template_id,
        created_by=principal.user_id,
    )
    session.add(project)
    session.flush()
    _add_version(session, project.id, 1, template.policy if template else _starter_policy(name), principal.user_id)
    session.commit()
    return project


def list_projects(session: Session, principal: Principal) -> list[Project]:
    stmt = select(Project).where(Project.org_id == principal.org_id).order_by(Project.created_at.desc())
    return list(session.scalars(stmt))


def get_project(session: Session, principal: Principal, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise NotFound("Project not found.")
    return project


def delete_project(session: Session, principal: Principal, project_id: str) -> None:
    project = get_project(session, principal, project_id)
    session.execute(delete(Feedback).where(Feedback.project_id == project.id))
    session.execute(delete(ApiKey).where(ApiKey.project_id == project.id))
    session.execute(delete(Decision).where(Decision.project_id == project.id))
    session.execute(delete(PolicyVersion).where(PolicyVersion.project_id == project.id))
    session.delete(project)
    session.commit()


def latest_policy(session: Session, project: Project) -> tuple[Policy, int]:
    """Callers must already have checked the project belongs to their org."""
    row = session.scalars(
        select(PolicyVersion).where(PolicyVersion.project_id == project.id).order_by(PolicyVersion.version.desc())
    ).first()
    if row is None:
        raise NotFound("This project has no policy yet.")
    return Policy(**row.policy_json), row.version


def current_policy(session: Session, principal: Principal, project: Project) -> tuple[Policy, int]:
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")
    return latest_policy(session, project)


def save_policy(session: Session, principal: Principal, project: Project, policy: Policy) -> int:
    if project.org_id != principal.org_id:
        raise NotFound("Project not found.")
    issues = validate_policy(policy)
    if issues:
        raise PolicyInvalid(issues)
    top = session.scalar(select(func.max(PolicyVersion.version)).where(PolicyVersion.project_id == project.id)) or 0
    _add_version(session, project.id, top + 1, policy, principal.user_id)
    session.commit()
    return top + 1
