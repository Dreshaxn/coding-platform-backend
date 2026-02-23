"""
Driver code generators for LeetCode-style execution.

When a problem has a function_name, the user writes code inside a Solution class.
The driver stub is appended to the user's code before execution. It:
1. Reads stdin (each line is a JSON-encoded argument)
2. Instantiates Solution() and calls the method
3. Prints json.dumps(result) to stdout

All internal variable names use underscore prefixes (_json, _sol, etc.)
to avoid colliding with user code.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Python driver
# ---------------------------------------------------------------------------

_PYTHON_DRIVER_TEMPLATE = '''
import json as _json, sys as _sys

_lines = _sys.stdin.read().strip().split('\\n')
_args = [_json.loads(_l) for _l in _lines if _l]
_sol = Solution()
_result = _sol.{function_name}(*_args)
print(_json.dumps(_result))
'''


# ---------------------------------------------------------------------------
# Java driver (placeholder for future use)
# ---------------------------------------------------------------------------

_JAVA_DRIVER_TEMPLATE = None  # TODO: implement


# ---------------------------------------------------------------------------
# C driver (placeholder for future use)
# ---------------------------------------------------------------------------

_C_DRIVER_TEMPLATE = None  # TODO: implement


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DRIVER_TEMPLATES = {
    "python3": _PYTHON_DRIVER_TEMPLATE,
    "python": _PYTHON_DRIVER_TEMPLATE,
    # "java": _JAVA_DRIVER_TEMPLATE,
    # "c": _C_DRIVER_TEMPLATE,
}


def generate_driver(language_slug: str, function_name: str) -> Optional[str]:
    """
    Generate the driver stub for a given language and function name.

    Returns the driver code string to append to the user's solution,
    or None if the language doesn't support LeetCode-style execution yet.
    """
    template = _DRIVER_TEMPLATES.get(language_slug.lower())
    if template is None:
        return None
    return template.format(function_name=function_name)
