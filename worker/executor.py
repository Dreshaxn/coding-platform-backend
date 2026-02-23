"""
Docker-based code execution engine.

This module safely executes untrusted user code inside isolated Docker containers.
It's the core of the online judge system - taking user submissions and running them
against test cases while enforcing strict resource limits.

Security is enforced through Docker's isolation features:
- No network access (prevents cheating via external APIs)
- CPU/memory limits (prevents resource exhaustion)
- Dropped capabilities (minimizes attack surface)
- Read-only filesystem mounts where possible
"""

import os
import json
import time
import tempfile
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .config import (
    LanguageConfig,
    ResourceLimits,
    ExecutionStatus,
    ExecutionStrategy,
    DEFAULT_LIMITS,
    get_language,
)
from .drivers import generate_driver
from .scripts import read_script


@dataclass
class TestResult:
    """Result of running code against a single test case."""
    test_index: int
    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: float
    memory_kb: float


@dataclass
class ExecutionResult:
    """Aggregated result of running code against all test cases."""
    status: ExecutionStatus
    test_results: List[TestResult]
    compilation_output: Optional[str]
    total_runtime_ms: float
    passed_count: int
    total_count: int
    
    @property
    def all_passed(self) -> bool:
        return self.passed_count == self.total_count


def _outputs_match(actual: str, expected: str) -> bool:
    """
    Compare actual vs expected output, trying JSON-normalized comparison first.
    
    For LeetCode-style problems the driver prints json.dumps(result), so
    [0, 1] and [0,1] should be considered equal. For plain stdin/stdout
    problems we fall back to exact string comparison.
    """
    actual = actual.strip()
    expected = expected.strip()
    
    # Fast path: exact match
    if actual == expected:
        return True
    
    # Try JSON comparison (handles whitespace differences in JSON output)
    try:
        return json.loads(actual) == json.loads(expected)
    except (json.JSONDecodeError, ValueError):
        return False


class DockerExecutor:
    """
    Executes user code inside Docker containers with security constraints.
    
    The executor supports two strategies:
    1. BATCH: All tests run in one container (faster, uses runner script)
    2. INDIVIDUAL: Each test runs in a fresh container (simpler, more isolated)
    
    Usage:
        executor = DockerExecutor()
        result = executor.execute(code, "python3", inputs, expected_outputs)
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or DEFAULT_LIMITS
    
    def execute(
        self,
        code: str,
        language_slug: str,
        test_inputs: List[str],
        expected_outputs: List[str],
        function_name: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute code against test cases and return results.
        
        This is the main entry point. It handles:
        1. Language validation
        2. Writing code to a temp directory (with driver stub for LeetCode-style problems)
        3. Compilation (if needed)
        4. Running tests with the appropriate strategy
        5. Collecting and returning results
        
        When function_name is provided, appends a driver stub that instantiates
        Solution() and calls the named method with JSON-parsed stdin args.
        """
        language = get_language(language_slug)
        if not language:
            return self._error_result(
                f"Unsupported language: {language_slug}",
                len(test_inputs),
            )
        
        start_time = time.perf_counter()
        total_timeout = self._calculate_total_timeout(len(test_inputs))
        
        # Use a temp directory that's cleaned up automatically
        with tempfile.TemporaryDirectory(prefix="judge_") as work_dir:
            self._write_solution(work_dir, language, code, function_name)
            
            # Compiled languages need an extra step
            if language.needs_compilation:
                success, output = self._compile(work_dir, language)
                if not success:
                    return ExecutionResult(
                        status=ExecutionStatus.COMPILATION_ERROR,
                        test_results=[],
                        compilation_output=output,
                        total_runtime_ms=(time.perf_counter() - start_time) * 1000,
                        passed_count=0,
                        total_count=len(test_inputs),
                    )
            
            # Run tests using the strategy defined for this language
            test_results = self._execute_tests(
                work_dir, language, test_inputs, expected_outputs, total_timeout
            )
        
        total_runtime = (time.perf_counter() - start_time) * 1000
        return self._build_result(test_results, total_runtime)
    
    def execute_single(
        self,
        code: str,
        language_slug: str,
        stdin: str = "",
    ) -> TestResult:
        """Convenience method for running code with a single input."""
        result = self.execute(code, language_slug, [stdin], [""])
        if result.test_results:
            return result.test_results[0]
        return TestResult(
            test_index=0,
            status=result.status,
            stdout="",
            stderr=result.compilation_output or "Execution failed",
            exit_code=1,
            runtime_ms=result.total_runtime_ms,
            memory_kb=0,
        )
    
    def _build_docker_command(
        self,
        image: str,
        work_dir: str,
        command: str,
        readonly: bool = True,
    ) -> List[str]:
        """
        Build the docker run command with all security flags.
        
        Security measures:
        - --network none: No internet access
        - --cap-drop ALL: Remove all Linux capabilities
        - --security-opt no-new-privileges: Can't escalate permissions
        - Resource limits: CPU, memory, process count, open files
        """
        mount_mode = "ro" if readonly else "rw"
        
        return [
            "docker", "run", "--rm", "-i",
            "--network", "none",                    # No network access
            "--cpus", self.limits.cpu_limit,
            "--memory", self.limits.memory_limit,
            "--memory-swap", self.limits.memory_swap,
            "--pids-limit", str(self.limits.max_pids),
            "--security-opt", "no-new-privileges",  # Can't sudo or setuid
            "--cap-drop", "ALL",                    # Minimal permissions
            "--ulimit", f"nofile={self.limits.max_open_files}:{self.limits.max_open_files}",
            "-v", f"{work_dir}:/app:{mount_mode}",
            image, "sh", "-c", command,
        ]
    
    def _compile(
        self,
        work_dir: str,
        language: LanguageConfig,
    ) -> tuple[bool, str]:
        """
        Compile source code if the language requires it.
        
        Compilation runs in a container with write access (needs to create binaries).
        Returns (success, error_message).
        """
        if not language.compile_command:
            return True, ""
        
        cmd = self._build_docker_command(
            image=language.docker_image,
            work_dir=work_dir,
            command=language.compile_command,
            readonly=False,  # Compiler needs to write output files
        )
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.limits.compilation_timeout,
            )
            
            if result.returncode != 0:
                error = result.stderr or result.stdout or "Compilation failed"
                return False, error[:2000]
            
            return True, result.stdout
            
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out"
        except Exception as e:
            return False, str(e)
    
    def _execute_tests(
        self,
        work_dir: str,
        language: LanguageConfig,
        test_inputs: List[str],
        expected_outputs: List[str],
        total_timeout: float,
    ) -> List[TestResult]:
        """Dispatch to the appropriate execution strategy for this language."""
        if language.strategy == ExecutionStrategy.BATCH:
            return self._execute_batch(
                work_dir, language, test_inputs, expected_outputs, total_timeout
            )
        else:
            return self._execute_individual(
                work_dir, language, test_inputs, expected_outputs, total_timeout
            )
    
    def _execute_batch(
        self,
        work_dir: str,
        language: LanguageConfig,
        test_inputs: List[str],
        expected_outputs: List[str],
        total_timeout: float,
    ) -> List[TestResult]:
        """
        Run all tests in a single container using a runner script.
        
        This is more efficient because container startup is expensive (~200ms).
        The runner script executes each test as a subprocess and collects metrics.
        """
        # Copy runner script into the work directory
        runner_script = read_script("python_batch_runner.py")
        runner_path = os.path.join(work_dir, "runner.py")
        with open(runner_path, "w") as f:
            f.write(runner_script)
        
        # Send test cases as JSON via stdin
        test_data = json.dumps({
            "test_cases": test_inputs,
            "timeout": self.limits.timeout_per_test,
        })
        
        cmd = self._build_docker_command(
            image=language.docker_image,
            work_dir=work_dir,
            command="python3 /app/runner.py",
        )
        
        try:
            result = subprocess.run(
                cmd,
                input=test_data,
                capture_output=True,
                text=True,
                timeout=total_timeout,
            )
            
            if result.returncode == 0:
                try:
                    raw_results = json.loads(result.stdout)
                    return self._parse_batch_results(raw_results, expected_outputs)
                except json.JSONDecodeError:
                    return self._create_error_results(
                        test_inputs, ExecutionStatus.INTERNAL_ERROR, result.stderr[:500]
                    )
            
            return self._create_error_results(
                test_inputs, ExecutionStatus.RUNTIME_ERROR, result.stderr[:500]
            )
            
        except subprocess.TimeoutExpired:
            return self._create_error_results(
                test_inputs, ExecutionStatus.TIME_LIMIT_EXCEEDED, "Total time limit exceeded"
            )
    
    def _execute_individual(
        self,
        work_dir: str,
        language: LanguageConfig,
        test_inputs: List[str],
        expected_outputs: List[str],
        total_timeout: float,
    ) -> List[TestResult]:
        """
        Run each test in a separate container.
        
        Slower due to container overhead, but simpler and provides
        stronger isolation between test cases.
        """
        results = []
        remaining_time = total_timeout
        
        for index, (test_input, expected) in enumerate(zip(test_inputs, expected_outputs)):
            # Stop if we've exhausted the total time budget
            if remaining_time <= 0:
                results.append(TestResult(
                    test_index=index,
                    status=ExecutionStatus.TIME_LIMIT_EXCEEDED,
                    stdout="",
                    stderr="Time limit exceeded",
                    exit_code=124,
                    runtime_ms=0,
                    memory_kb=0,
                ))
                continue
            
            result = self._run_single_test(
                work_dir, language, test_input, expected, index, remaining_time
            )
            results.append(result)
            remaining_time -= result.runtime_ms / 1000
        
        return results
    
    def _run_single_test(
        self,
        work_dir: str,
        language: LanguageConfig,
        test_input: str,
        expected_output: str,
        index: int,
        remaining_time: float,
    ) -> TestResult:
        """Execute a single test case and compare output."""
        cmd = self._build_docker_command(
            image=language.docker_image,
            work_dir=work_dir,
            command=language.run_command,
        )
        
        timeout = min(self.limits.timeout_per_test + 1, remaining_time)
        start_time = time.perf_counter()
        
        try:
            proc = subprocess.run(
                cmd,
                input=test_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            elapsed = time.perf_counter() - start_time
            stdout = proc.stdout.strip()
            
            # Determine verdict based on exit code and output comparison
            if proc.returncode != 0:
                status = ExecutionStatus.RUNTIME_ERROR
            elif _outputs_match(stdout, expected_output):
                status = ExecutionStatus.SUCCESS
            else:
                status = ExecutionStatus.WRONG_ANSWER
            
            return TestResult(
                test_index=index,
                status=status,
                stdout=stdout[:self.limits.max_stdout_bytes],
                stderr=proc.stderr[:self.limits.max_stderr_bytes],
                exit_code=proc.returncode,
                runtime_ms=elapsed * 1000,
                memory_kb=0,
            )
            
        except subprocess.TimeoutExpired:
            return TestResult(
                test_index=index,
                status=ExecutionStatus.TIME_LIMIT_EXCEEDED,
                stdout="",
                stderr="Time limit exceeded",
                exit_code=124,
                runtime_ms=self.limits.timeout_per_test * 1000,
                memory_kb=0,
            )
    
    def _parse_batch_results(
        self,
        raw_results: List[dict],
        expected_outputs: List[str],
    ) -> List[TestResult]:
        """Parse JSON results from the batch runner and determine verdicts."""
        results = []
        
        for raw in raw_results:
            index = raw.get("index", len(results))
            stdout = raw.get("stdout", "").strip()
            stderr = raw.get("stderr", "")
            exit_code = raw.get("exit_code", 0)
            
            # Exit code 124 is the conventional timeout signal
            if exit_code == 124:
                status = ExecutionStatus.TIME_LIMIT_EXCEEDED
            elif exit_code != 0:
                status = ExecutionStatus.RUNTIME_ERROR
            elif index < len(expected_outputs) and _outputs_match(stdout, expected_outputs[index]):
                status = ExecutionStatus.SUCCESS
            elif index < len(expected_outputs):
                status = ExecutionStatus.WRONG_ANSWER
            else:
                status = ExecutionStatus.SUCCESS
            
            results.append(TestResult(
                test_index=index,
                status=status,
                stdout=stdout[:self.limits.max_stdout_bytes],
                stderr=stderr[:self.limits.max_stderr_bytes],
                exit_code=exit_code,
                runtime_ms=raw.get("runtime_ms", 0),
                memory_kb=raw.get("memory_kb", 0),
            ))
        
        return results
    
    def _build_result(
        self,
        test_results: List[TestResult],
        total_runtime: float,
    ) -> ExecutionResult:
        """
        Aggregate individual test results into a final verdict.
        
        Priority: TLE > Runtime Error > Wrong Answer
        (We report the most severe issue first)
        """
        passed_count = sum(1 for r in test_results if r.status == ExecutionStatus.SUCCESS)
        
        if passed_count == len(test_results):
            status = ExecutionStatus.SUCCESS
        elif any(r.status == ExecutionStatus.TIME_LIMIT_EXCEEDED for r in test_results):
            status = ExecutionStatus.TIME_LIMIT_EXCEEDED
        elif any(r.status == ExecutionStatus.RUNTIME_ERROR for r in test_results):
            status = ExecutionStatus.RUNTIME_ERROR
        else:
            status = ExecutionStatus.WRONG_ANSWER
        
        return ExecutionResult(
            status=status,
            test_results=test_results,
            compilation_output=None,
            total_runtime_ms=total_runtime,
            passed_count=passed_count,
            total_count=len(test_results),
        )
    
    def _error_result(self, message: str, test_count: int) -> ExecutionResult:
        """Create an error result for cases like unsupported language."""
        return ExecutionResult(
            status=ExecutionStatus.INTERNAL_ERROR,
            test_results=[],
            compilation_output=message,
            total_runtime_ms=0,
            passed_count=0,
            total_count=test_count,
        )
    
    def _create_error_results(
        self,
        test_inputs: List[str],
        status: ExecutionStatus,
        message: str,
    ) -> List[TestResult]:
        """Create uniform error results for all test cases."""
        return [
            TestResult(
                test_index=i,
                status=status,
                stdout="",
                stderr=message,
                exit_code=1,
                runtime_ms=0,
                memory_kb=0,
            )
            for i in range(len(test_inputs))
        ]
    
    def _write_solution(
        self,
        work_dir: str,
        language: LanguageConfig,
        code: str,
        function_name: Optional[str] = None,
    ) -> None:
        """
        Write user's source code to the working directory.
        
        For LeetCode-style problems (function_name is set), appends a driver
        stub that handles JSON I/O and calls Solution().method(*args).
        """
        path = os.path.join(work_dir, language.filename)
        with open(path, "w") as f:
            f.write(code)
            if function_name:
                driver = generate_driver(language.slug, function_name)
                if driver:
                    f.write("\n")
                    f.write(driver)
    
    def _calculate_total_timeout(self, test_count: int) -> float:
        """Calculate total timeout with buffer for container overhead."""
        calculated = test_count * self.limits.timeout_per_test + 10
        return min(self.limits.max_total_timeout, calculated)


# =============================================================================
# MODULE-LEVEL API
# =============================================================================

_default_executor = DockerExecutor()


def run_code(
    code: str,
    language_slug: str,
    test_inputs: List[str],
    expected_outputs: List[str],
    function_name: Optional[str] = None,
) -> ExecutionResult:
    """Execute code against test cases. Main entry point for the judge system."""
    return _default_executor.execute(
        code, language_slug, test_inputs, expected_outputs, function_name=function_name
    )


def run_single(code: str, language_slug: str, stdin: str = "") -> TestResult:
    """Execute code with a single input. Useful for "Run" button functionality."""
    return _default_executor.execute_single(code, language_slug, stdin)
