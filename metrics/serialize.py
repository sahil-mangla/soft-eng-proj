"""JSON-safe conversion for results: dataclasses, enum keys, and non-finite
floats. NaN and infinity are not valid JSON (a browser's `res.json()` throws
on them), so they become null."""

import math
from dataclasses import asdict, is_dataclass
from enum import Enum


def to_jsonable(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {(k.value if isinstance(k, Enum) else str(k)): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj
