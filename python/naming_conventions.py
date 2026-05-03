"""
Houdini FX Pipeline — naming conventions.
Standard task list and validators. Import this in pipeline tools and HDAs.
"""

import re

STANDARD_TASKS = [
    "dust-sim",
    "smoke-sim",
    "fire-sim",
    "pyro",
    "destruction",
    "falling-debris",
    "rigid-body",
    "flip-fluids",
    "ocean-sim",
    "grains",
    "cloth-sim",
    "wire-sim",
    "fur-sim",
    "crowd-sim",
]

_TASK_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def format_task(raw: str) -> str:
    """Normalise raw input to a valid task slug. 'Falling Ice' -> 'falling-ice'"""
    slug = raw.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def is_valid_task(task: str) -> bool:
    return bool(_TASK_RE.match(task))


def validate_task(raw: str) -> str:
    """Format and validate. Raises ValueError if result is not a valid task slug."""
    result = format_task(raw)
    if not result or not is_valid_task(result):
        raise ValueError(
            f"'{raw}' cannot be converted to a valid task name. "
            "Use lowercase letters, digits, and hyphens (e.g. 'falling-ice')."
        )
    return result
