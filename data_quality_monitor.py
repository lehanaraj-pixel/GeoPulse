
import json
from pathlib import Path
from datetime import datetime, timezone


def load_report(file_path):
    """Load an enriched data quality report."""

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Report not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    required_fields = {"dataset", "summary", "checks"}

    if not required_fields.issubset(report):
        raise ValueError("Invalid quality report structure")

    if not isinstance(report["checks"], list):
        raise ValueError("'checks' must be a list")

    return report


def get_check_statuses(report):
    """Create a mapping of check names to their statuses."""

    statuses = {}

    for check in report["checks"]:
        name = check.get("name")
        status = check.get("status")

        if not name or status not in {"PASS", "WARN", "FAIL"}:
            raise ValueError("Invalid check name or status")

        if name in statuses:
            raise ValueError(f"Duplicate check name: {name}")

        statuses[name] = status

    return statuses


def compare_reports(previous, current):
    """Compare two quality reports and detect regressions."""

    previous_checks = get_check_statuses(previous)
    current_checks = get_check_statuses(current)

    previous_summary = previous["summary"]
    current_summary = current["summary"]

    previous_records = previous["dataset"]["total_records"]
    current_records = current["dataset"]["total_records"]

    previous_devices = previous["dataset"]["unique_devices"]
    current_devices = current["dataset"]["unique_devices"]

    common_checks = previous_checks.keys() & current_checks.keys()

    regressions = []
    improvements = []

    for name in sorted(common_checks):
        old_status = previous_checks[name]
        new_status = current_checks[name]

        if old_status == "PASS" and new_status in {"WARN", "FAIL"}:
            regressions.append({
                "check": name,
                "previous_status": old_status,
                "current_status": new_status
            })

        elif old_status in {"WARN", "FAIL"} and new_status == "PASS":
            improvements.append({
                "check": name,
                "previous_status": old_status,
                "current_status": new_status
            })

    new_checks = sorted(current_checks.keys() - previous_checks.keys())
    removed_checks = sorted(previous_checks.keys() - current_checks.keys())

    record_change = current_records - previous_records
    device_change = current_devices - previous_devices

    previous_failures = previous_summary["failed_checks"]
    current_failures = current_summary["failed_checks"]

    previous_status = previous_summary["overall_status"]
    current_status = current_summary["overall_status"]

    status_rank = {"PASS": 0, "WARN": 1, "FAIL": 2}

    if current_status not in status_rank or previous_status not in status_rank:
        raise ValueError("Invalid overall validation status")

    if status_rank[current_status] > status_rank[previous_status]:
        overall_change = "DETERIORATED"
    elif status_rank[current_status] < status_rank[previous_status]:
        overall_change = "IMPROVED"
    else:
        overall_change = "UNCHANGED"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_change": overall_change,
        "previous_status": previous_status,
        "current_status": current_status,
        "dataset_changes": {
            "previous_records": previous_records,
            "current_records": current_records,
            "record_change": record_change,
            "previous_devices": previous_devices,
            "current_devices": current_devices,
            "device_change": device_change
        },
        "validation_changes": {
            "previous_failures": previous_failures,
            "current_failures": current_failures,
            "new_regressions": regressions,
            "improvements": improvements,
            "new_checks": new_checks,
            "removed_checks": removed_checks
        }
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare two GeoPulse data quality reports"
    )

    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)

    parser.add_argument(
        "--output",
        default="data/processed/regression_report.json"
    )

    args = parser.parse_args()

    previous = load_report(args.previous)
    current = load_report(args.current)

    result = compare_reports(previous, current)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("\nGEOPULSE DATA QUALITY COMPARISON")
    print("=" * 42)
    print(f"Overall change : {result['overall_change']}")
    print(f"Previous status: {result['previous_status']}")
    print(f"Current status : {result['current_status']}")
    print(
        "Record change  : "
        f"{result['dataset_changes']['record_change']:,}"
    )
    print(
        "Device change  : "
        f"{result['dataset_changes']['device_change']:,}"
    )
    print(
        "New regressions: "
        f"{len(result['validation_changes']['new_regressions'])}"
    )
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
