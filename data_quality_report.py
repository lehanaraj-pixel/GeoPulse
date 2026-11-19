
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone


VALID_STATUSES = {"PASS", "WARN", "FAIL"}


def load_validation_report(input_path):
    """Load and validate the original JSON report."""

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Report not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    required_fields = {"file", "total_records", "unique_devices", "checks"}

    missing_fields = required_fields - report.keys()

    if missing_fields:
        raise ValueError(f"Missing fields: {missing_fields}")

    if not isinstance(report["checks"], list):
        raise ValueError("'checks' must be a list")

    for check in report["checks"]:
        if not isinstance(check, dict):
            raise ValueError("Each check must be a dictionary")

        if not {"name", "status", "detail"}.issubset(check):
            raise ValueError("A check is missing required fields")

        if check["status"] not in VALID_STATUSES:
            raise ValueError(
                f"Unknown status: {check['status']}"
            )

    return report


def build_summary(report):
    
    """Generate summary statistics from validation checks."""
    checks = report["checks"]

    for check in checks:
        if check.get("status") not in VALID_STATUSES:
            raise ValueError(
                f"Unknown status: {check.get('status')}"
            )

    status_counts = {
        status: sum(
            1 for check in checks
            if check["status"] == status
        )
        for status in VALID_STATUSES
    }

    total_checks = len(checks)
    passed = status_counts["PASS"]

    pass_rate = (
        round((passed / total_checks) * 100, 2)
        if total_checks > 0 else 0.0
    )

    if status_counts["FAIL"] > 0:
        overall_status = "FAIL"
    elif status_counts["WARN"] > 0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "overall_status": overall_status,
        "total_checks": total_checks,
        "passed_checks": status_counts["PASS"],
        "warning_checks": status_counts["WARN"],
        "failed_checks": status_counts["FAIL"],
        "check_pass_rate_pct": pass_rate
    }


def build_quality_report(input_path):
    """Build the enriched data quality report."""

    source_report = load_validation_report(input_path)

    summary = build_summary(source_report)

    return {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_report": str(input_path),
        "dataset": {
            "file": source_report["file"],
            "total_records": source_report["total_records"],
            "unique_devices": source_report["unique_devices"]
        },
        "summary": summary,
        "catchment": source_report.get("catchment", {}),
        "checks": source_report["checks"]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate an enriched GeoPulse data quality report"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the original validation JSON"
    )

    parser.add_argument(
        "--output",
        default="data/processed/enriched_quality_report.json",
        help="Path for the enriched JSON report"
    )

    args = parser.parse_args()

    report = build_quality_report(args.input)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("\nGEOPULSE ENRICHED DATA QUALITY REPORT")
    print("=" * 45)
    print(f"Overall status : {report['summary']['overall_status']}")
    print(f"Total checks   : {report['summary']['total_checks']}")
    print(f"Passed         : {report['summary']['passed_checks']}")
    print(f"Warnings       : {report['summary']['warning_checks']}")
    print(f"Failed         : {report['summary']['failed_checks']}")
    print(f"Pass rate      : {report['summary']['check_pass_rate_pct']}%")
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
