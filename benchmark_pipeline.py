
"""
GeoPulse - Full Pipeline Performance Benchmark

Measures:
1. Total pipeline execution time
2. Peak process memory usage
3. Pipeline execution status

The benchmark runs footfall_analysis.py as a separate process.
"""

import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil


# Project paths
ROOT_DIR = Path(__file__).resolve().parent
PIPELINE_SCRIPT = ROOT_DIR / "footfall_analysis.py"
OUTPUT_DIR = ROOT_DIR / "data" / "processed"
REPORT_PATH = OUTPUT_DIR / "pipeline_benchmark.json"
LOG_PATH = OUTPUT_DIR / "pipeline_benchmark.log"


def monitor_memory(process):
    """Return the total RSS memory of the process and its children."""

    total_memory = 0

    try:
        total_memory += process.memory_info().rss

        for child in process.children(recursive=True):
            try:
                total_memory += child.memory_info().rss
            except psutil.NoSuchProcess:
                continue

    except psutil.NoSuchProcess:
        pass

    return total_memory / (1024 * 1024)


def run_benchmark():
    """Execute the GeoPulse pipeline and record performance metrics."""

    if not PIPELINE_SCRIPT.exists():
        raise FileNotFoundError(
            f"Pipeline script not found: {PIPELINE_SCRIPT}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n========== GEOPULSE PIPELINE BENCHMARK ==========")
    print(f"Pipeline: {PIPELINE_SCRIPT.name}")
    print("Starting full pipeline execution...\n")

    start_time = time.perf_counter()
    peak_memory_mb = 0

    with open(LOG_PATH, "w", encoding="utf-8") as log_file:

        process = subprocess.Popen(
            [sys.executable, str(PIPELINE_SCRIPT)],
            cwd=ROOT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )

        monitored_process = psutil.Process(process.pid)

        while process.poll() is None:

            current_memory = monitor_memory(monitored_process)

            peak_memory_mb = max(
                peak_memory_mb,
                current_memory
            )

            time.sleep(0.1)

        exit_code = process.returncode

    end_time = time.perf_counter()
    execution_time = end_time - start_time

    status = "SUCCESS" if exit_code == 0 else "FAILED"

    report = {
        "project": "GeoPulse",
        "benchmark_timestamp": datetime.now().isoformat(),
        "pipeline_script": PIPELINE_SCRIPT.name,
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),
        "execution_time_seconds": round(execution_time, 3),
        "peak_memory_mb": round(peak_memory_mb, 2),
        "exit_code": exit_code,
        "status": status,
        "execution_log": str(LOG_PATH.relative_to(ROOT_DIR))
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=4)

    print("\n========== BENCHMARK RESULTS ==========")
    print(f"Execution time : {execution_time:.2f} seconds")
    print(f"Peak memory    : {peak_memory_mb:.2f} MB")
    print(f"Pipeline status: {status}")
    print(f"Exit code      : {exit_code}")
    print(f"Report saved   : {REPORT_PATH}")
    print(f"Execution log  : {LOG_PATH}")

    if exit_code != 0:
        print("\nPipeline failed. Check the execution log.")
        raise SystemExit(exit_code)


if __name__ == "__main__":
    run_benchmark()
