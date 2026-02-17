from __future__ import annotations

from pydantic import JsonValue, RootModel


class JsonObjectPayload(RootModel[dict[str, JsonValue]]):
    pass
