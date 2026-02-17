from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
