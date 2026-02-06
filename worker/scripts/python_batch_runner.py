#!/usr/bin/env python3
"""
Batch runner for Python solutions.

This script runs INSIDE a Docker container. It receives test cases via stdin,
executes the user's solution against each one, and outputs results as JSON.

Why batch execution?
- Container startup takes ~200ms
- For 20 test cases, individual = 20 * 200ms = 4 seconds of overhead
- Batch execution = 200ms total overhead (one container for all tests)

Input (stdin JSON):
    {
        "test_cases": ["input1", "input2", ...],
        "timeout": 2.0
    }

Output (stdout JSON):
    [
        {"index": 0, "stdout": "...", "stderr": "...", "exit_code": 0, "runtime_ms": 12.5, "memory_kb": 1024},
        ...
    ]
"""

import sys
import json
import time
import resource
import subprocess


def run_single_test(test_input: str, timeout: float, index: int) -> dict:
    """
    Execute the solution with a single test input.
    
    Runs the solution as a subprocess to isolate it and measure resources.
    Returns a dict with stdout, stderr, timing, and memory usage.
    """
    start_time = time.perf_counter()
    mem_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    
    try:
        proc = subprocess.run(
            ["python3", "/app/solution.py"],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        elapsed = time.perf_counter() - start_time
        mem_after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        
        return {
            "index": index,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "runtime_ms": elapsed * 1000,
            "memory_kb": max(0, mem_after - mem_before),
        }
        
    except subprocess.TimeoutExpired:
        # Exit code 124 is the conventional signal for timeout
        return {
            "index": index,
            "stdout": "",
            "stderr": "Time limit exceeded",
            "exit_code": 124,
            "runtime_ms": timeout * 1000,
            "memory_kb": 0,
        }
        
    except Exception as e:
        return {
            "index": index,
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "runtime_ms": 0,
            "memory_kb": 0,
        }


def main():
    """Entry point - parse input, run tests, output results."""
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps([{"error": f"Invalid JSON input: {e}"}]))
        sys.exit(1)
    
    test_cases = data.get("test_cases", [])
    timeout = data.get("timeout", 2.0)
    
    results = [
        run_single_test(test_input, timeout, index)
        for index, test_input in enumerate(test_cases)
    ]
    
    print(json.dumps(results))


if __name__ == "__main__":
    main()
