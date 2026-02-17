from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PreviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
