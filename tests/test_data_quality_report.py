
import pytest

from data_quality_report import (
    build_summary,
    load_validation_report
)


def test_all_checks_pass():
    report = {
        "checks": [
            {"name": "Check 1", "status": "PASS", "detail": "OK"},
            {"name": "Check 2", "status": "PASS", "detail": "OK"}
        ]
    }

    summary = build_summary(report)

    assert summary["overall_status"] == "PASS"
    assert summary["passed_checks"] == 2
    assert summary["check_pass_rate_pct"] == 100.0


def test_failed_check_changes_overall_status():
    report = {
        "checks": [
            {"name": "Check 1", "status": "PASS", "detail": "OK"},
            {"name": "Check 2", "status": "FAIL", "detail": "Failed"}
        ]
    }

    summary = build_summary(report)

    assert summary["overall_status"] == "FAIL"
    assert summary["failed_checks"] == 1
    assert summary["check_pass_rate_pct"] == 50.0


def test_warning_check_changes_overall_status():
    report = {
        "checks": [
            {"name": "Check 1", "status": "PASS", "detail": "OK"},
            {"name": "Check 2", "status": "WARN", "detail": "Warning"}
        ]
    }

    summary = build_summary(report)

    assert summary["overall_status"] == "WARN"
    assert summary["warning_checks"] == 1


def test_empty_checks():
    report = {"checks": []}

    summary = build_summary(report)

    assert summary["total_checks"] == 0
    assert summary["check_pass_rate_pct"] == 0.0


def test_invalid_status():
    report = {
        "checks": [
            {"name": "Check 1", "status": "UNKNOWN", "detail": "Invalid"}
        ]
    }

    with pytest.raises(ValueError):
        build_summary(report)


def test_missing_input_file():
    with pytest.raises(FileNotFoundError):
        load_validation_report("nonexistent_report.json")
