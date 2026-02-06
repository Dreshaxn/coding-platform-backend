"""
Runner scripts for batch execution inside Docker containers.

These scripts are copied into the container at runtime and execute
user code against multiple test cases, collecting metrics for each.
This avoids the overhead of starting a new container per test.
"""

import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_script_path(name: str) -> str:
    """Get the absolute path to a runner script."""
    return os.path.join(SCRIPTS_DIR, name)


def read_script(name: str) -> str:
    """Read the contents of a runner script for copying into containers."""
    path = get_script_path(name)
    with open(path, "r") as f:
        return f.read()
