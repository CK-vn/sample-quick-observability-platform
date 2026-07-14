# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Unit test for the filter_groups shape produced by
cdk/dashboard_stack.py's QuickSightStack.__init__ (tasks 15.1-15.3):
- the "licensed-users" sheet gets a NumericRangeFilter on
  inactivity_period instead of the generic per-sheet TimeRangeFilter
- the generic per-sheet TimeRangeFilter loop still applies to sheets
  whose dataset does have event_time (regression check)
"""
from aws_cdk import App
from aws_cdk.assertions import Template

from cdk.dashboard_stack import QuickSightStack


def _synth_template() -> Template:
    """Synthesize QuickSightStack once with the context values it requires
    (quicksightOwnerArn) and return its Template."""
    app = App(
        context={
            "quicksightOwnerArn": "arn:aws:quicksight:us-east-1:123456789012:user/default/test-user",
        }
    )
    stack = QuickSightStack(
        app, "TestQuickSightStack",
        env={"account": "123456789012", "region": "us-east-1"},
    )
    return Template.from_stack(stack)


def _get_definition_filter_groups() -> list:
    """Return the FilterGroups list from the CfnAnalysis's Definition
    property override (raw CloudFormation template properties)."""
    template = _synth_template()
    analyses = template.find_resources("AWS::QuickSight::Analysis")
    assert len(analyses) == 1, f"expected exactly one Analysis resource, got {len(analyses)}"
    definition = list(analyses.values())[0]["Properties"]["Definition"]
    return definition["FilterGroups"]


# ---------------------------------------------------------------------------
# Task 15.4 - unit test for the NumericRangeFilter/TimeRangeFilter JSON shape
# Requirements: 6.6
# ---------------------------------------------------------------------------
def test_licensed_users_sheet_has_numeric_range_filter_on_inactivity_period():
    """Requirements: 6.6 - exactly one filter group's Filters contain a
    NumericRangeFilter with Column.DataSetIdentifier="licensed-users",
    Column.ColumnName="inactivity_period",
    RangeMinimum={"Parameter": "InactivityThresholdDays"},
    IncludeMinimum=True, and no RangeMaximum key present."""
    filter_groups = _get_definition_filter_groups()

    matching_groups = []
    for fg in filter_groups:
        for f in fg["Filters"]:
            numeric_filter = f.get("NumericRangeFilter")
            if numeric_filter and numeric_filter["Column"]["DataSetIdentifier"] == "licensed-users":
                matching_groups.append(fg)

    assert len(matching_groups) == 1, (
        f"expected exactly one filter group with a NumericRangeFilter on "
        f"licensed-users, got {len(matching_groups)}"
    )

    numeric_filter = matching_groups[0]["Filters"][0]["NumericRangeFilter"]
    assert numeric_filter["Column"] == {
        "DataSetIdentifier": "licensed-users",
        "ColumnName": "inactivity_period",
    }
    assert numeric_filter["RangeMinimum"] == {"Parameter": "InactivityThresholdDays"}
    assert numeric_filter["IncludeMinimum"] is True
    assert "RangeMaximum" not in numeric_filter


def test_licensed_users_dataset_has_no_time_range_filter():
    """Requirements: 6.6 - no TimeRangeFilter filter group references
    DataSetIdentifier="licensed-users", confirming the "licensed-users"
    sheet is excluded from the generic per-sheet date-filter loop."""
    filter_groups = _get_definition_filter_groups()

    time_range_filters_on_licensed_users = [
        f["TimeRangeFilter"]
        for fg in filter_groups
        for f in fg["Filters"]
        if "TimeRangeFilter" in f
        and f["TimeRangeFilter"]["Column"]["DataSetIdentifier"] == "licensed-users"
    ]

    assert time_range_filters_on_licensed_users == []


def test_other_sheet_still_has_time_range_filter_regression():
    """Requirements: 6.6 (regression) - a TimeRangeFilter filter group still
    exists for another sheet's own dataset (chat-activity), proving the
    generic per-sheet TimeRangeFilter loop still works for sheets that do
    have event_time."""
    filter_groups = _get_definition_filter_groups()

    time_range_filters_on_chat_activity = [
        f["TimeRangeFilter"]
        for fg in filter_groups
        for f in fg["Filters"]
        if "TimeRangeFilter" in f
        and f["TimeRangeFilter"]["Column"]["DataSetIdentifier"] == "chat-activity"
    ]

    assert len(time_range_filters_on_chat_activity) == 1
    time_range_filter = time_range_filters_on_chat_activity[0]
    assert time_range_filter["Column"] == {
        "DataSetIdentifier": "chat-activity",
        "ColumnName": "event_time",
    }
    assert time_range_filter["RangeMinimumValue"] == {"Parameter": "StartDate"}
    assert time_range_filter["RangeMaximumValue"] == {"Parameter": "EndDate"}
