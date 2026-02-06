"""
Configuration for the code execution engine.

This module centralizes all settings for running untrusted user code safely:
- Language definitions (Docker images, compile/run commands)
- Resource limits (CPU, memory, time)
- Execution strategies (batch vs individual test runs)

Keeping configuration separate from execution logic makes it easy to:
- Add new languages without touching execution code
- Tune resource limits for different contexts (contests vs practice)
- Audit security settings in one place
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class ExecutionStrategy(str, Enum):
    """
    Determines how test cases are executed for a language.
    
    BATCH: Runs all tests in a single container using a runner script.
           More efficient (one container startup), but requires a runner script.
           Best for interpreted languages like Python.
    
    INDIVIDUAL: Runs each test in a separate container.
                Simpler and more isolated, but slower due to container overhead.
                Used for compiled languages or when batch runners aren't available.
    """
    BATCH = "batch"
    INDIVIDUAL = "individual"


class ExecutionStatus(str, Enum):
    """Possible outcomes when executing user code."""
    SUCCESS = "success"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class LanguageConfig:
    """
    Defines how to compile and run code for a specific language.
    
    Each language needs:
    - A Docker image with the compiler/interpreter
    - Commands to compile (if applicable) and run the code
    - A file extension and execution strategy
    """
    slug: str                           # Unique identifier (e.g., "python3")
    name: str                           # Display name (e.g., "Python 3.12")
    docker_image: str                   # Docker Hub image to use
    file_extension: str                 # Source file extension
    run_command: str                    # Command to execute the code
    compile_command: Optional[str] = None  # Compilation command (None for interpreted languages)
    strategy: ExecutionStrategy = ExecutionStrategy.INDIVIDUAL
    
    @property
    def needs_compilation(self) -> bool:
        return self.compile_command is not None
    
    @property
    def filename(self) -> str:
        """Solution filename. Java requires class name to match filename."""
        if self.slug == "java":
            return "Solution.java"
        return f"solution{self.file_extension}"


@dataclass(frozen=True)
class ResourceLimits:
    """
    Security constraints for code execution.
    
    These limits prevent malicious or buggy code from:
    - Running forever (time limits)
    - Consuming all memory (memory limits)
    - Fork-bombing the system (process limits)
    - Filling up disk space (file limits)
    """
    # Time limits (seconds)
    timeout_per_test: float = 2.0       # Max time for a single test case
    max_total_timeout: float = 60.0     # Max total execution time
    compilation_timeout: float = 30.0   # Max time for compilation
    
    # Memory limits
    memory_limit: str = "256m"          # Container memory limit
    memory_swap: str = "256m"           # Same as memory = no swap allowed
    
    # Process limits
    cpu_limit: str = "1.0"              # Max CPU cores
    max_pids: int = 128                 # Max processes (prevents fork bombs)
    max_open_files: int = 64            # Max file descriptors
    
    # Output limits (bytes)
    max_stdout_bytes: int = 1024 * 1024  # 1MB - prevents output flooding
    max_stderr_bytes: int = 512 * 1024   # 512KB



# SUPPORTED LANGUAGES


LANGUAGES: dict[str, LanguageConfig] = {
    "python3": LanguageConfig(
        slug="python3",
        name="Python 3.12",
        docker_image="python:3.12-slim",
        file_extension=".py",
        run_command="python3 /app/solution.py",
        strategy=ExecutionStrategy.BATCH,  # Batch is faster for Python
    ),
    "python": LanguageConfig(
        slug="python",
        name="Python 3.12",
        docker_image="python:3.12-slim",
        file_extension=".py",
        run_command="python3 /app/solution.py",
        strategy=ExecutionStrategy.BATCH,
    ),
    "java": LanguageConfig(
        slug="java",
        name="Java 21",
        docker_image="eclipse-temurin:21-jdk",
        file_extension=".java",
        run_command="java -cp /app Solution",
        compile_command="javac -d /app /app/Solution.java",
        strategy=ExecutionStrategy.INDIVIDUAL,
    ),
    "c": LanguageConfig(
        slug="c",
        name="C (GCC 13)",
        docker_image="gcc:13",
        file_extension=".c",
        run_command="/app/solution",
        compile_command="gcc -O2 -std=c17 -o /app/solution /app/solution.c",
        strategy=ExecutionStrategy.INDIVIDUAL,
    ),
}


# PRESET LIMITS FOR DIFFERENT CONTEXTS

DEFAULT_LIMITS = ResourceLimits()

CONTEST_LIMITS = ResourceLimits(
    timeout_per_test=1.0,        # Stricter time limits for competitive fairness
    max_total_timeout=30.0,
    memory_limit="128m",
    memory_swap="128m",
    max_pids=64,
)

PRACTICE_LIMITS = ResourceLimits(
    timeout_per_test=5.0,        # More lenient for learning/debugging
    max_total_timeout=120.0,
    memory_limit="512m",
    memory_swap="512m",
    max_pids=256,
)


# HELPER FUNCTIONS

def get_language(slug: str) -> Optional[LanguageConfig]:
    """Get language configuration by slug, case-insensitive."""
    return LANGUAGES.get(slug.lower())


def is_supported(slug: str) -> bool:
    """Check if a language is supported."""
    return slug.lower() in LANGUAGES


def get_supported_languages() -> List[str]:
    """Get list of all supported language slugs."""
    return list(LANGUAGES.keys())


def get_limits(context: str = "default") -> ResourceLimits:
    """Get resource limits for a given context (default, contest, practice)."""
    limits_map = {
        "default": DEFAULT_LIMITS,
        "contest": CONTEST_LIMITS,
        "practice": PRACTICE_LIMITS,
    }
    return limits_map.get(context, DEFAULT_LIMITS)
