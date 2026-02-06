"""
Code Execution Engine

This module provides secure, sandboxed execution of user-submitted code.
It's the core of the online judge system, responsible for:

1. Running untrusted code safely inside Docker containers
2. Enforcing resource limits (CPU, memory, time)
3. Comparing output against expected results
4. Collecting execution metrics (runtime, memory usage)

Architecture:
    DockerExecutor     - Runs code in isolated containers
    config             - Language definitions and resource limits
    scripts/           - Helper scripts that run inside containers

Usage:
    from worker import run_code, ExecutionStatus

    result = run_code(
        code="print(int(input()) * 2)",
        language_slug="python3",
        test_inputs=["5", "10"],
        expected_outputs=["10", "20"]
    )

    if result.status == ExecutionStatus.SUCCESS:
        print(f"All {result.passed_count} tests passed!")
"""

# Main executor
from .executor import (
    DockerExecutor,
    run_code,
    run_single,
    TestResult,
    ExecutionResult,
)

# Configuration
from .config import (
    ExecutionStatus,
    ExecutionStrategy,
    LanguageConfig,
    ResourceLimits,
    LANGUAGES,
    DEFAULT_LIMITS,
    CONTEST_LIMITS,
    PRACTICE_LIMITS,
    get_language,
    is_supported,
    get_supported_languages,
    get_limits,
)

__all__ = [
    # Executor
    "DockerExecutor",
    "run_code",
    "run_single",
    "TestResult",
    "ExecutionResult",
    # Enums
    "ExecutionStatus",
    "ExecutionStrategy",
    # Configuration
    "LanguageConfig",
    "ResourceLimits",
    "LANGUAGES",
    "DEFAULT_LIMITS",
    "CONTEST_LIMITS",
    "PRACTICE_LIMITS",
    # Helpers
    "get_language",
    "is_supported",
    "get_supported_languages",
    "get_limits",
]

"""
Code Execution Engine

This module provides secure, sandboxed execution of user-submitted code.
It's the core of the online judge system, responsible for:

1. Running untrusted code safely inside Docker containers
2. Enforcing resource limits (CPU, memory, time)
3. Comparing output against expected results
4. Collecting execution metrics (runtime, memory usage)

Architecture:
    DockerExecutor     - Runs code in isolated containers
    config             - Language definitions and resource limits
    scripts/           - Helper scripts that run inside containers

Usage:
    from worker import run_code, ExecutionStatus
    
    result = run_code(
        code="print(int(input()) * 2)",
        language_slug="python3",
        test_inputs=["5", "10"],
        expected_outputs=["10", "20"]
    )
    
    if result.status == ExecutionStatus.SUCCESS:
        print(f"All {result.passed_count} tests passed!")
"""

# Main executor
from .executor import (
    DockerExecutor,
    run_code,
    run_single,
    TestResult,
    ExecutionResult,
)

# Configuration
from .config import (
    ExecutionStatus,
    ExecutionStrategy,
    LanguageConfig,
    ResourceLimits,
    LANGUAGES,
    DEFAULT_LIMITS,
    CONTEST_LIMITS,
    PRACTICE_LIMITS,
    get_language,
    is_supported,
    get_supported_languages,
    get_limits,
)

__all__ = [
    # Executor
    "DockerExecutor",
    "run_code",
    "run_single",
    "TestResult",
    "ExecutionResult",
    # Enums
    "ExecutionStatus",
    "ExecutionStrategy",
    # Configuration
    "LanguageConfig",
    "ResourceLimits",
    "LANGUAGES",
    "DEFAULT_LIMITS",
    "CONTEST_LIMITS",
    "PRACTICE_LIMITS",
    # Helpers
    "get_language",
    "is_supported",
    "get_supported_languages",
    "get_limits",
]
