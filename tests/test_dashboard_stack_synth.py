# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
End-to-end CDK synthesis test for cdk/dashboard_stack.py's QuickSightStack
(task 18.1). Synthesizes the full stack and asserts, via the resulting
CloudFormation template's CfnAnalysis Definition property, that the new
sheet/datasets/visuals added across tasks 12, 13, and 15 all exist:
- the "Licensed Users" sheet (task 15.1)
- the "Daily Active Users" retitle of adopt-trend (task 12.2)
- the Function Usage Distribution visual (task 12.5)
- the Agent Hours volume visuals on the "cost" sheet (task 13.2)
- the new dataset identifiers and calculated fields (tasks 12.1, 12.4, 13.1)
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


def _get_definition() -> dict:
    """Return the Definition property dict from the synthesized CfnAnalysis
    resource (raw CloudFormation template properties)."""
    template = _synth_template()
    analyses = template.find_resources("AWS::QuickSight::Analysis")
    assert len(analyses) == 1, f"expected exactly one Analysis resource, got {len(analyses)}"
    return list(analyses.values())[0]["Properties"]["Definition"]


def _find_sheet(definition: dict, name: str) -> dict:
    matches = [s for s in definition["Sheets"] if s["Name"] == name]
    assert len(matches) == 1, f"expected exactly one sheet named {name!r}, got {len(matches)}"
    return matches[0]


def _visual_type_and_body(visual: dict):
    """A visual dict has exactly one key ending in 'Visual' (e.g.
    'KPIVisual', 'TableVisual', 'LineChartVisual'). Return (type, body)."""
    for key, body in visual.items():
        if key.endswith("Visual"):
            return key, body
    raise AssertionError(f"visual dict has no *Visual key: {visual!r}")


# ---------------------------------------------------------------------------
# 1. Exactly 6 sheets exist, including one named "Licensed Users"
# Requirements: 6.1
# ---------------------------------------------------------------------------
def test_exactly_six_sheets_including_licensed_users():
    definition = _get_definition()
    sheets = definition["Sheets"]

    assert len(sheets) == 6, f"expected exactly 6 sheets, got {len(sheets)}"

    sheet_names = [s["Name"] for s in sheets]
    assert "Licensed Users" in sheet_names


# ---------------------------------------------------------------------------
# 2. Licensed Users sheet visuals include a TableVisual
#    (licensed-inactive-table) and >=2 KPIVisuals
#    (licensed-kpi-total, licensed-kpi-inactive)
# Requirements: 6.4
# ---------------------------------------------------------------------------
def test_licensed_users_sheet_has_table_and_kpi_visuals():
    definition = _get_definition()
    sheet = _find_sheet(definition, "Licensed Users")

    visual_types_by_id = {}
    for visual in sheet["Visuals"]:
        vtype, body = _visual_type_and_body(visual)
        visual_types_by_id[body["VisualId"]] = vtype

    table_ids = [vid for vid, vtype in visual_types_by_id.items() if vtype == "TableVisual"]
    kpi_ids = [vid for vid, vtype in visual_types_by_id.items() if vtype == "KPIVisual"]

    assert any(vid.endswith("licensed-inactive-table") for vid in table_ids), (
        f"expected a TableVisual ending in 'licensed-inactive-table', got table ids: {table_ids}"
    )
    assert len(kpi_ids) >= 2, f"expected at least 2 KPIVisuals, got {len(kpi_ids)}: {kpi_ids}"
    assert any(vid.endswith("licensed-kpi-total") for vid in kpi_ids)
    assert any(vid.endswith("licensed-kpi-inactive") for vid in kpi_ids)


# ---------------------------------------------------------------------------
# 3. "Chat Agents Usage" sheet contains a LineChartVisual retitled to
#    "Daily Active Users" (confirms task 12.2's adopt-trend retitle)
# Requirements: 1.1
# ---------------------------------------------------------------------------
def test_chat_agents_usage_sheet_has_daily_active_users_line_chart():
    definition = _get_definition()
    sheet = _find_sheet(definition, "Chat Agents Usage")

    line_chart_titles = [
        body["Title"]["FormatText"]["PlainText"]
        for visual in sheet["Visuals"]
        for vtype, body in [_visual_type_and_body(visual)]
        if vtype == "LineChartVisual"
    ]

    assert "Daily Active Users" in line_chart_titles, (
        f"expected a LineChartVisual titled 'Daily Active Users', got titles: {line_chart_titles}"
    )


# ---------------------------------------------------------------------------
# 4. "Chat Agents Usage" sheet contains a PieChartVisual sourcing from the
#    "function-usage-distribution" dataset (task 12.5)
# Requirements: 4.1
# ---------------------------------------------------------------------------
def test_chat_agents_usage_sheet_has_function_usage_distribution_pie_chart():
    definition = _get_definition()
    sheet = _find_sheet(definition, "Chat Agents Usage")

    pie_charts = [
        body for visual in sheet["Visuals"]
        for vtype, body in [_visual_type_and_body(visual)]
        if vtype == "PieChartVisual"
    ]

    matching = []
    for body in pie_charts:
        category_dims = body["ChartConfiguration"]["FieldWells"]["PieChartAggregatedFieldWells"]["Category"]
        for dim in category_dims:
            dim_key = "DateDimensionField" if "DateDimensionField" in dim else "CategoricalDimensionField"
            if dim[dim_key]["Column"]["DataSetIdentifier"] == "function-usage-distribution":
                matching.append(body)
                break

    assert len(matching) == 1, (
        f"expected exactly one PieChartVisual sourcing from "
        f"'function-usage-distribution', got {len(matching)}"
    )
    assert matching[0]["Title"]["FormatText"]["PlainText"] == "Function Usage Distribution"


# ---------------------------------------------------------------------------
# 5. "Hours Spent on Research, Flow, Automation" sheet contains the two new
#    Agent Hours volume visuals: cost-hours-volume-total (BarChartVisual)
#    and cost-hours-volume-avg (KPIVisual)
# Requirements: 3.1
# ---------------------------------------------------------------------------
def test_cost_sheet_has_agent_hours_volume_visuals():
    definition = _get_definition()
    sheet = _find_sheet(definition, "Hours Spent on Research, Flow, Automation")

    bar_chart_ids = [
        body["VisualId"] for visual in sheet["Visuals"]
        for vtype, body in [_visual_type_and_body(visual)]
        if vtype == "BarChartVisual"
    ]
    kpi_ids = [
        body["VisualId"] for visual in sheet["Visuals"]
        for vtype, body in [_visual_type_and_body(visual)]
        if vtype == "KPIVisual"
    ]

    assert any(vid.endswith("cost-hours-volume-total") for vid in bar_chart_ids), (
        f"expected a BarChartVisual ending in 'cost-hours-volume-total', got: {bar_chart_ids}"
    )
    assert any(vid.endswith("cost-hours-volume-avg") for vid in kpi_ids), (
        f"expected a KPIVisual ending in 'cost-hours-volume-avg', got: {kpi_ids}"
    )


# ---------------------------------------------------------------------------
# 6. DataSetIdentifierDeclarations includes all 7 expected dataset
#    identifiers
# Requirements: 6.1, 4.1
# ---------------------------------------------------------------------------
def test_dataset_identifier_declarations_include_all_seven_datasets():
    definition = _get_definition()
    identifiers = {decl["Identifier"] for decl in definition["DataSetIdentifierDeclarations"]}

    expected = {
        "chat-activity",
        "feedback-analysis",
        "agent-hours-usage",
        "api-audit-trail",
        "index-usage",
        "licensed-users",
        "function-usage-distribution",
    }
    assert identifiers == expected, (
        f"expected exactly {expected}, got {identifiers}"
    )


# ---------------------------------------------------------------------------
# 7. CalculatedFields includes both daily_avg_usage_volume and
#    daily_avg_agent_hours
# Requirements: 2.2, 3.2
# ---------------------------------------------------------------------------
def test_calculated_fields_include_both_daily_average_fields():
    definition = _get_definition()
    calculated_field_names = {cf["Name"] for cf in definition["CalculatedFields"]}

    assert "daily_avg_usage_volume" in calculated_field_names
    assert "daily_avg_agent_hours" in calculated_field_names
