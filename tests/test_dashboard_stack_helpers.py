# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Unit tests for the `_make_visual` / `_build_visual_definition` helper changes
in cdk/dashboard_stack.py (task 11.1 - dataset override, task 11.2 -
missing_data_treatment).
"""
from cdk.dashboard_stack import _build_visual_definition, _make_visual


def _measure_column(measure: dict) -> dict:
    """Extract the Column dict from a MeasureField, regardless of whether it
    is Categorical or Numerical."""
    if "CategoricalMeasureField" in measure:
        return measure["CategoricalMeasureField"]["Column"]
    return measure["NumericalMeasureField"]["Column"]


def _dimension_column(dimension: dict) -> dict:
    """Extract the Column dict from a DimensionField, regardless of whether
    it is a DateDimensionField or CategoricalDimensionField."""
    if "DateDimensionField" in dimension:
        return dimension["DateDimensionField"]["Column"]
    return dimension["CategoricalDimensionField"]["Column"]


# ---------------------------------------------------------------------------
# Task 11.1 - dataset override
# Requirements: 4.1
# ---------------------------------------------------------------------------
def test_dataset_override_binds_fields_to_overriding_dataset():
    """A visual built with dataset="other-dataset" on a sheet whose own
    dataset is "sheet-dataset" resolves all field IDs/column references to
    "other-dataset", not the sheet's own dataset."""
    visual = _make_visual(
        "adopt-function-distribution",
        "Function Usage Distribution",
        "PIE",
        {"category": "category", "values": [{"field": "category", "agg": "COUNT"}]},
        dataset="other-dataset",
    )

    result = _build_visual_definition("prefix", "sheet-dataset", visual)

    chart_config = result["PieChartVisual"]["ChartConfiguration"]
    field_wells = chart_config["FieldWells"]["PieChartAggregatedFieldWells"]

    measure_column = _measure_column(field_wells["Values"][0])
    assert measure_column["DataSetIdentifier"] == "other-dataset"

    dimension_column = _dimension_column(field_wells["Category"][0])
    assert dimension_column["DataSetIdentifier"] == "other-dataset"


# ---------------------------------------------------------------------------
# Task 11.2 - missing_data_treatment
# Requirements: 1.4
# ---------------------------------------------------------------------------
def test_missing_data_treatment_produces_primary_y_axis_missing_data_config():
    """A LINE visual built with missing_data_treatment="SHOW_AS_ZERO" produces
    a PrimaryYAxisDisplayOptions.MissingDataConfigurations list with exactly
    one entry whose TreatmentOption is "SHOW_AS_ZERO"."""
    visual = _make_visual(
        "adopt-trend",
        "Daily Active Users",
        "LINE",
        {"category": "event_time", "values": [{"field": "user_name", "agg": "DISTINCT_COUNT"}]},
        missing_data_treatment="SHOW_AS_ZERO",
    )

    result = _build_visual_definition("prefix", "sheet-dataset", visual)

    chart_config = result["LineChartVisual"]["ChartConfiguration"]
    missing_data_config = chart_config["PrimaryYAxisDisplayOptions"]["MissingDataConfigurations"]

    assert len(missing_data_config) == 1
    entry = missing_data_config[0]
    assert entry["TreatmentOption"] == "SHOW_AS_ZERO"
    assert "FieldId" not in entry


# ---------------------------------------------------------------------------
# Control/regression case - neither override param set
# Requirements: 1.4, 4.1
# ---------------------------------------------------------------------------
def test_defaults_are_true_no_ops():
    """A visual with neither dataset nor missing_data_treatment set resolves
    to the sheet's own dataset and never adds
    PrimaryYAxisDisplayOptions to its chart config."""
    visual = _make_visual(
        "cost-trend",
        "Agent Hours Trend by Service",
        "LINE",
        {"category": "event_time", "values": [{"field": "hours", "agg": "SUM"}], "group": "service"},
    )

    result = _build_visual_definition("prefix", "sheet-dataset", visual)

    chart_config = result["LineChartVisual"]["ChartConfiguration"]
    assert "PrimaryYAxisDisplayOptions" not in chart_config

    first_measure = chart_config["FieldWells"]["LineChartAggregatedFieldWells"]["Values"][0]
    measure_column = _measure_column(first_measure)
    assert measure_column["DataSetIdentifier"] == "sheet-dataset"

    category_dimension = chart_config["FieldWells"]["LineChartAggregatedFieldWells"]["Category"][0]
    dimension_column = _dimension_column(category_dimension)
    assert dimension_column["DataSetIdentifier"] == "sheet-dataset"
