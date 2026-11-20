
import pytest

from data_quality_monitor import (
    compare_reports,
    get_check_statuses,
    load_report
)


def create_report(records, devices, overall, checks):
    """Create a sample enriched quality report."""

    return {
        "dataset": {
            "total_records": records,
            "unique_devices": devices
        },
        "summary": {
            "overall_status": overall,
            "failed_checks": sum(
                1 for check in checks
                if check["status"] == "FAIL"
            )
        },
        "checks": checks
    }


def test_detect_new_regression():
    previous = create_report(
        1000, 50, "PASS",
        [{"name": "Missing values", "status": "PASS"}]
    )

    current = create_report(
        1000, 50, "FAIL",
        [{"name": "Missing values", "status": "FAIL"}]
    )

    result = compare_reports(previous, current)

    assert result["overall_change"] == "DETERIORATED"
    assert len(result["validation_changes"]["new_regressions"]) == 1


def test_detect_improvement():
    previous = create_report(
        1000, 50, "FAIL",
        [{"name": "Missing values", "status": "FAIL"}]
    )

    current = create_report(
        1000, 50, "PASS",
        [{"name": "Missing values", "status": "PASS"}]
    )

    result = compare_reports(previous, current)

    assert result["overall_change"] == "IMPROVED"
    assert len(result["validation_changes"]["improvements"]) == 1


def test_detect_record_and_device_changes():
    previous = create_report(1000, 50, "PASS", [])
    current = create_report(900, 45, "PASS", [])

    result = compare_reports(previous, current)
    changes = result["dataset_changes"]

    assert changes["record_change"] == -100
    assert changes["device_change"] == -5


def test_detect_new_and_removed_checks():
    previous = create_report(
        1000, 50, "PASS",
        [{"name": "Check A", "status": "PASS"}]
    )

    current = create_report(
        1000, 50, "PASS",
        [{"name": "Check B", "status": "PASS"}]
    )

    result = compare_reports(previous, current)
    changes = result["validation_changes"]

    assert changes["new_checks"] == ["Check B"]
    assert changes["removed_checks"] == ["Check A"]


def test_unchanged_reports():
    checks = [
        {"name": "Missing values", "status": "PASS"}
    ]

    previous = create_report(1000, 50, "PASS", checks)
    current = create_report(1000, 50, "PASS", checks)

    result = compare_reports(previous, current)

    assert result["overall_change"] == "UNCHANGED"
    assert result["dataset_changes"]["record_change"] == 0


def test_duplicate_check_names_rejected():
    report = {
        "checks": [
            {"name": "Check A", "status": "PASS"},
            {"name": "Check A", "status": "FAIL"}
        ]
    }

    with pytest.raises(ValueError):
        get_check_statuses(report)


def test_invalid_status_rejected():
    report = {
        "checks": [
            {"name": "Check A", "status": "UNKNOWN"}
        ]
    }

    with pytest.raises(ValueError):
        get_check_statuses(report)


def test_missing_report_rejected():
    with pytest.raises(FileNotFoundError):
        load_report("missing_report.json")
