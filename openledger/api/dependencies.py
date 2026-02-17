from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request

from openledger.application.services.workflow_service import WorkflowService
from openledger.logger import get_logger
from openledger.settings import Settings, load_settings


@dataclass(slots=True)
class ApiContext:
    root: Path
    settings: Settings
    logger: Any
    workflow: WorkflowService


def build_context(root: Path) -> ApiContext:
    settings = load_settings()
    logger = get_logger()
    workflow = WorkflowService(root)
    return ApiContext(root=root, settings=settings, logger=logger, workflow=workflow)


def get_ctx(request: Request) -> ApiContext:
    return request.app.state.ctx
