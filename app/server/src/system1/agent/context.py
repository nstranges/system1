from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from system1.agent.models import PendingAction
from system1.auth.principal import Principal
from system1.config import Settings
from system1.projects.models import Project
from system1.providers import Providers


@dataclass
class AgentContext:
    session: Session
    principal: Principal
    providers: Providers
    settings: Settings
    project: Project


ActionHandler = Callable[[AgentContext, PendingAction], Awaitable[dict]]

_handlers: dict[str, ActionHandler] = {}


def register_action_handler(kind: str, handler: ActionHandler) -> None:
    """Later tasks register what confirming a `dataset` or `training` action actually runs."""
    _handlers[kind] = handler


def get_action_handler(kind: str) -> ActionHandler | None:
    return _handlers.get(kind)
