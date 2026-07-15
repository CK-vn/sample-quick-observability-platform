# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""CloudFormation custom-resource provider for the Terraform deployment."""

from __future__ import annotations

import ast
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

import boto3
from botocore.exceptions import ClientError


POLL_SECONDS = 3
ATHENA_TIMEOUT_SECONDS = 240
QUICKSIGHT_TIMEOUT_SECONDS = 600
TABLE_MESSAGE_COLUMNS = "  user_message STRING,\n  system_text_message STRING\n"
THEME_ACTIONS = [
    "quicksight:DescribeTheme", "quicksight:DescribeThemeAlias",
    "quicksight:DescribeThemePermissions", "quicksight:ListThemeVersions",
    "quicksight:ListThemeAliases", "quicksight:UpdateTheme",
    "quicksight:UpdateThemeAlias", "quicksight:UpdateThemePermissions",
    "quicksight:CreateThemeAlias", "quicksight:DeleteTheme",
    "quicksight:DeleteThemeAlias",
]
LINK_ACTIONS = [
    "quicksight:DescribeDashboard", "quicksight:QueryDashboard",
    "quicksight:ListDashboardVersions",
]


def _log(message: str) -> None:
    print(message, flush=True)


def _response(event: dict[str, Any], context: Any, status: str,
              data: dict[str, Any] | None = None, reason: str | None = None,
              physical_id: str | None = None) -> None:
    """Send the mandatory CloudFormation response without logging its URL."""
    physical_id = physical_id or event.get("PhysicalResourceId") or _physical_id(event)
    body = json.dumps({
        "Status": status,
        "Reason": reason or f"See CloudWatch Logs: {getattr(context, 'log_stream_name', 'unknown')}",
        "PhysicalResourceId": physical_id,
        "StackId": event.get("StackId", ""),
        "RequestId": event.get("RequestId", ""),
        "LogicalResourceId": event.get("LogicalResourceId", ""),
        "NoEcho": False,
        "Data": data or {},
    }, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        event["ResponseURL"], data=body, method="PUT",
        headers={"content-type": "", "content-length": str(len(body))},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def _physical_id(event: dict[str, Any]) -> str:
    stack_name = event.get("StackId", "stack").split("/")[-2:-1]
    base = stack_name[0] if stack_name else "stack"
    logical = event.get("LogicalResourceId", "resource")
    kind = event.get("ResourceProperties", {}).get("ResourceKind", "provider")
    return f"{base}-{logical}-{kind}"[:1024]


def _prop(props: dict[str, Any], *names: str, default: Any = None,
          required: bool = False) -> Any:
    for name in names:
        value = props.get(name)
        if value is not None and value != "":
            return value
    if required:
        raise ValueError(f"Missing required property: {names[0]}")
    return default


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes", "on"}


def _ownership_parameter(prefix: str, kind: str) -> str:
    return f"/quick-observability/{prefix}/terraform-{kind}-owner"


def _ownership_state(ssm: Any, name: str, token: str) -> str:
    try:
        value = ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return "unclaimed"
        raise
    return "owned" if value == token else "foreign"


def _claim_ownership(ssm: Any, name: str, token: str) -> None:
    ssm.put_parameter(
        Name=name,
        Description="Ownership marker for Terraform custom-resource lifecycle",
        Type="String",
        Value=token,
        Overwrite=False,
    )


def _release_ownership(ssm: Any, name: str) -> None:
    try:
        ssm.delete_parameter(Name=name)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ParameterNotFound":
            raise


def _validate_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label}")
    return value


def _is_not_found(error: Exception) -> bool:
    if not isinstance(error, ClientError):
        return False
    code = error.response.get("Error", {}).get("Code", "")
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status == 404 or code in {
        "ResourceNotFoundException", "NotFoundException", "EntityNotFoundException",
    }


def _find_packaged(name: str) -> Path:
    here = Path(__file__).resolve().parent
    candidates = [here / name, here.parent / name, Path("/var/task") / name]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Local source-tree fallback; packaged Lambdas have no repository ancestors.
    try:
        repository_root = here.parents[2]
    except IndexError:
        repository_root = None
    if repository_root is not None:
        if name == "dashboard_definition.py":
            candidates.append(
                repository_root / "terraform" / "lambda" / "provisioner" / name
            )
        elif name == "sql":
            candidates.append(repository_root / "sql")
    for candidate in candidates[3:]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Packaged asset not found: {name}")


def _load_dashboard_source() -> dict[str, Any]:
    """Execute only the source module's data declarations and pure builders."""
    source_path = _find_packaged("dashboard_definition.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    assignments = {
        "DATASET_CONFIGS", "TOPIC_COLUMNS", "CUSTOM_INSTRUCTIONS",
        "SHEET_DEFS", "OWNER_ACTIONS",
    }
    functions = {
        "_make_visual", "_build_field_id", "_build_measure", "_build_dimension",
        "_build_visual_definition", "_build_grid_layout",
    }
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
            selected.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            if names & assignments:
                selected.append(node)
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"),
        namespace,
    )
    missing = (assignments | {"_build_visual_definition", "_build_grid_layout"}) - namespace.keys()
    if missing:
        raise ValueError(f"Dashboard source is missing: {', '.join(sorted(missing))}")
    return namespace


_DASHBOARD = _load_dashboard_source()
DATASET_CONFIGS = _DASHBOARD["DATASET_CONFIGS"]
TOPIC_COLUMNS = _DASHBOARD["TOPIC_COLUMNS"]
CUSTOM_INSTRUCTIONS = _DASHBOARD["CUSTOM_INSTRUCTIONS"]
SHEET_DEFS = _DASHBOARD["SHEET_DEFS"]
OWNER_ACTIONS = _DASHBOARD["OWNER_ACTIONS"]
_build_visual_definition = _DASHBOARD["_build_visual_definition"]
_build_grid_layout = _DASHBOARD["_build_grid_layout"]


def build_definition(prefix: str, region: str, account_id: str) -> dict[str, Any]:
    """Build the analysis/dashboard definition for the Terraform provisioner."""
    used_datasets = {sheet["dataset"] for sheet in SHEET_DEFS}
    for sheet in SHEET_DEFS:
        used_datasets.update(
            visual["dataset"] for visual in sheet["visuals"] if visual.get("dataset")
        )
    declarations = [{
        "Identifier": config["id_suffix"],
        "DataSetArn": (
            f"arn:aws:quicksight:{region}:{account_id}:dataset/"
            f"{prefix}-{config['id_suffix']}"
        ),
    } for config in DATASET_CONFIGS if config["id_suffix"] in used_datasets]

    calculated_fields = [
        {
            "DataSetIdentifier": "chat-activity", "Name": "daily_avg_usage_volume",
            "Expression": (
                "distinct_count({conversation_id}) / "
                "distinct_count(truncDate('DD', {event_time}))"
            ),
        },
        {
            "DataSetIdentifier": "agent-hours-usage", "Name": "daily_avg_agent_hours",
            "Expression": "sum({hours}) / distinct_count(truncDate('DD', {event_time}))",
        },
    ]
    sheets: list[dict[str, Any]] = []
    for sheet_def in SHEET_DEFS:
        suffix = sheet_def["id_suffix"]
        visuals = [
            _build_visual_definition(prefix, sheet_def["dataset"], visual)
            for visual in sheet_def["visuals"]
        ]
        detail_visual = next((
            f"{prefix}-{visual['visual_id']}"
            for visual in reversed(sheet_def["visuals"]) if visual["type"] == "TABLE"
        ), None)
        if detail_visual:
            for index, visual in enumerate(sheet_def["visuals"]):
                if visual["type"] == "TABLE":
                    continue
                visual_id = f"{prefix}-{visual['visual_id']}"
                action = {
                    "CustomActionId": f"{visual_id}-filter-action",
                    "Name": "Filter details", "Trigger": "DATA_POINT_CLICK", "Status": "ENABLED",
                    "ActionOperations": [{"FilterOperation": {
                        "SelectedFieldsConfiguration": {"SelectedFieldOptions": "ALL_FIELDS"},
                        "TargetVisualsConfiguration": {"SameSheetTargetVisualConfiguration": {
                            "TargetVisuals": [detail_visual]
                        }},
                    }}],
                }
                for visual_type, payload in visuals[index].items():
                    if visual_type.endswith("Visual"):
                        payload.setdefault("Actions", []).append(action)
                        break
        sheets.append({
            "SheetId": f"{prefix}-sheet-{suffix}", "Name": sheet_def["name"],
            "Visuals": visuals,
            "Layouts": [{"Configuration": {"GridLayout": {
                "Elements": _build_grid_layout(prefix, sheet_def)
            }}}],
        })

    parameters = [
        {"DateTimeParameterDeclaration": {
            "Name": "StartDate", "TimeGranularity": "DAY",
            "DefaultValues": {"RollingDate": {"Expression": "truncDate('YYYY', now())"}},
        }},
        {"DateTimeParameterDeclaration": {
            "Name": "EndDate", "TimeGranularity": "DAY",
            "DefaultValues": {"RollingDate": {"Expression": "now()"}},
        }},
        {"IntegerParameterDeclaration": {
            "Name": "InactivityThresholdDays", "ParameterValueType": "SINGLE_VALUED",
            "DefaultValues": {"StaticValues": [30]},
        }},
    ]
    filters: list[dict[str, Any]] = []
    for sheet_def in SHEET_DEFS:
        suffix = sheet_def["id_suffix"]
        if suffix == "licensed-users":
            continue
        sheet_id = f"{prefix}-sheet-{suffix}"
        datasets = [sheet_def["dataset"]] + sorted({
            visual["dataset"] for visual in sheet_def["visuals"]
            if visual.get("dataset") and visual["dataset"] != sheet_def["dataset"]
        })
        for dataset_suffix in datasets:
            qualifier = "" if dataset_suffix == sheet_def["dataset"] else f"-{dataset_suffix}"
            filters.append({
                "FilterGroupId": f"{prefix}-fg-{suffix}{qualifier}",
                "Filters": [{"TimeRangeFilter": {
                    "FilterId": f"{prefix}-filter-date-{suffix}{qualifier}",
                    "Column": {"DataSetIdentifier": dataset_suffix, "ColumnName": "event_time"},
                    "RangeMinimumValue": {"Parameter": "StartDate"},
                    "RangeMaximumValue": {"Parameter": "EndDate"},
                    "NullOption": "ALL_VALUES", "IncludeMinimum": True, "IncludeMaximum": True,
                }}],
                "ScopeConfiguration": {"SelectedSheets": {
                    "SheetVisualScopingConfigurations": [{"SheetId": sheet_id, "Scope": "ALL_VISUALS"}]
                }},
                "CrossDataset": "SINGLE_DATASET", "Status": "ENABLED",
            })

    licensed_sheet_id = f"{prefix}-sheet-licensed-users"
    filters.append({
        "FilterGroupId": f"{prefix}-fg-licensed-users-threshold",
        "Filters": [{"NumericRangeFilter": {
            "FilterId": f"{prefix}-filter-licensed-users-threshold",
            "Column": {"DataSetIdentifier": "licensed-users", "ColumnName": "inactivity_period"},
            "RangeMinimum": {"Parameter": "InactivityThresholdDays"},
            "IncludeMinimum": True, "NullOption": "ALL_VALUES",
        }}],
        "ScopeConfiguration": {"SelectedSheets": {"SheetVisualScopingConfigurations": [{
            "SheetId": licensed_sheet_id, "Scope": "SELECTED_VISUALS",
            "VisualIds": [f"{prefix}-licensed-kpi-inactive", f"{prefix}-licensed-inactive-table"],
        }]}},
        "CrossDataset": "SINGLE_DATASET", "Status": "ENABLED",
    })

    for index, sheet_def in enumerate(SHEET_DEFS):
        suffix = sheet_def["id_suffix"]
        for visual_filter in sheet_def.get("visual_filters", []):
            visual_id = f"{prefix}-{visual_filter['visual_id']}"
            column = visual_filter["column"]
            filters.append({
                "FilterGroupId": f"{prefix}-fg-{suffix}-{visual_filter['visual_id']}",
                "Filters": [{"CategoryFilter": {
                    "FilterId": f"{prefix}-filter-{suffix}-{visual_filter['visual_id']}-{column}",
                    "Column": {"DataSetIdentifier": sheet_def["dataset"], "ColumnName": column},
                    "Configuration": {"FilterListConfiguration": {
                        "MatchOperator": "CONTAINS", "CategoryValues": visual_filter["values"]
                    }},
                }}],
                "ScopeConfiguration": {"SelectedSheets": {"SheetVisualScopingConfigurations": [{
                    "SheetId": f"{prefix}-sheet-{suffix}", "Scope": "SELECTED_VISUALS",
                    "VisualIds": [visual_id],
                }]}},
                "CrossDataset": "SINGLE_DATASET", "Status": "ENABLED",
            })
        if suffix == "licensed-users":
            sheets[index]["ParameterControls"] = [{"Slider": {
                "ParameterControlId": f"{prefix}-ctrl-threshold-{suffix}",
                "SourceParameterName": "InactivityThresholdDays",
                "Title": "Inactivity Threshold (days)",
                "MinimumValue": 0, "MaximumValue": 365, "StepSize": 1,
            }}]
        else:
            sheets[index]["ParameterControls"] = [
                {"DateTimePicker": {
                    "ParameterControlId": f"{prefix}-ctrl-start-{suffix}",
                    "SourceParameterName": "StartDate", "Title": "Start Date",
                }},
                {"DateTimePicker": {
                    "ParameterControlId": f"{prefix}-ctrl-end-{suffix}",
                    "SourceParameterName": "EndDate", "Title": "End Date",
                }},
            ]
    return {
        "DataSetIdentifierDeclarations": declarations,
        "ParameterDeclarations": parameters,
        "FilterGroups": filters,
        "CalculatedFields": calculated_fields,
        "Sheets": sheets,
    }


def _athena_query(client: Any, query: str, database: str, workgroup: str,
                  output_location: str) -> None:
    response = client.start_query_execution(
        QueryString=query, QueryExecutionContext={"Database": database},
        WorkGroup=workgroup, ResultConfiguration={"OutputLocation": output_location},
    )
    query_id = response["QueryExecutionId"]
    deadline = time.monotonic() + ATHENA_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        execution = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
        status = execution["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            return
        if state in {"FAILED", "CANCELLED"}:
            reason = status.get("AthenaError", {}).get("ErrorMessage") or status.get("StateChangeReason", state)
            raise RuntimeError(f"Athena query {state.lower()}: {reason[:500]}")
        time.sleep(POLL_SECONDS)
    try:
        client.stop_query_execution(QueryExecutionId=query_id)
    except Exception:
        pass
    raise TimeoutError("Athena query did not complete before the timeout")


def _catalog(props: dict[str, Any], request_type: str,
             old_props: dict[str, Any] | None = None) -> dict[str, Any]:
    database = _validate_identifier(
        _prop(props, "DatabaseName", "Database", required=True), "database name"
    )
    prefix = str(_prop(props, "ResourcePrefix", default="quickobserve"))
    token = str(_prop(props, "_StackId", required=True))
    workgroup = _prop(props, "WorkGroup", "Workgroup", default="primary")
    bucket = _prop(props, "BucketName", "Bucket", required=True)
    output = _prop(
        props, "AthenaOutputLocation", "OutputLocation",
        default=f"s3://{bucket}/athena-results/",
    )
    region = _prop(props, "Region", default=os.environ.get("AWS_REGION"))
    athena = boto3.client("athena", region_name=region)
    glue = boto3.client("glue", region_name=region)
    ssm = boto3.client("ssm", region_name=region)
    owner_name = _ownership_parameter(prefix, "catalog")
    ownership = _ownership_state(ssm, owner_name, token)

    if request_type == "Delete":
        if ownership != "owned":
            _log(f"Catalog: skipping unowned database {database}")
            return {}
        _log(f"Catalog: dropping database {database}")
        _athena_query(
            athena, f"DROP SCHEMA IF EXISTS {database} CASCADE",
            "default", workgroup, output,
        )
        _release_ownership(ssm, owner_name)
        return {}

    if ownership == "foreign":
        raise RuntimeError(f"Catalog prefix {prefix} is owned by another deployment")

    if request_type == "Create" and ownership == "unclaimed":
        try:
            glue.get_database(Name=database)
        except glue.exceptions.EntityNotFoundException:
            pass
        else:
            raise RuntimeError(
                f"Glue database {database} already exists; choose another database_name"
            )
        _claim_ownership(ssm, owner_name, token)
    elif request_type == "Update" and ownership != "owned":
        raise RuntimeError("Catalog update rejected because ownership could not be verified")

    old_database = None
    if old_props:
        old_database = _prop(old_props, "DatabaseName", "Database")
    if request_type == "Update":
        target = old_database or database
        _log(f"Catalog: rebuilding database {target}")
        _athena_query(
            athena, f"DROP SCHEMA IF EXISTS {target} CASCADE",
            "default", workgroup, output,
        )

    try:
        glue.create_database(DatabaseInput={
            "Name": database,
            "Description": "Amazon Quick Observability Data Lake",
        })
    except glue.exceptions.AlreadyExistsException:
        if ownership != "owned":
            raise

    sql_dir = _find_packaged("sql")
    files = sorted(sql_dir.glob("create_*_table.sql")) + sorted(
        sql_dir.glob("create_*_view.sql")
    )
    if not files:
        raise FileNotFoundError("No packaged catalog SQL files found")
    for sql_file in files:
        _log(f"Catalog: applying {sql_file.name}")
        query = sql_file.read_text(encoding="utf-8")
        query = query.replace("${DATABASE}", database).replace("${BUCKET}", bucket)
        if sql_file.name == "create_chat_logs_table.sql":
            # Keep a stable table schema. When collection is disabled the
            # transform Lambda strips these fields, so Athena/QuickSight see
            # NULL values without requiring a destructive schema migration.
            query = query.replace(
                "  web_search STRING\n", f"  web_search STRING,\n{TABLE_MESSAGE_COLUMNS}",
            )
        _athena_query(athena, query, database, workgroup, output)
    return {}


def _arn(region: str, account_id: str, resource_type: str, resource_id: str) -> str:
    return f"arn:aws:quicksight:{region}:{account_id}:{resource_type}/{resource_id}"


def _permissions(owner_arn: str, resource_type: str) -> list[dict[str, Any]]:
    return [{"Principal": owner_arn, "Actions": OWNER_ACTIONS[resource_type]}]


def _theme_configuration() -> dict[str, Any]:
    return {
        "DataColorPalette": {
            "Colors": [
                "#268EE5", "#1659A9", "#5FAEF0", "#A1C2FB", "#A9DFFF",
                "#DDEDFF", "#90D9F6", "#F0F3F5", "#6F23C7", "#1C79F1",
                "#DDDDDB", "#BACDE6", "#7D008B", "#EEEE5E", "#FDE9EB",
                "#E1DBF6", "#F3F3F4", "#FF02A3", "#D703B2", "#1B2250",
            ],
            "MinMaxGradient": ["#ADC7FF", "#7D008B"], "EmptyFillColor": "#F6F7F8",
        },
        "UIColorPalette": {
            "PrimaryForeground": "#243040", "PrimaryBackground": "#F6F5FB",
            "SecondaryForeground": "#4D5A6A", "SecondaryBackground": "#F6F5FB",
            "Accent": "#177199", "AccentForeground": "#FFFFFF",
            "Danger": "#A01106", "DangerForeground": "#FFFFFF",
            "Warning": "#D48104", "WarningForeground": "#FFFFFF",
            "Success": "#218001", "SuccessForeground": "#FFFFFF",
            "Dimension": "#177199", "DimensionForeground": "#FFFFFF",
            "Measure": "#218001", "MeasureForeground": "#FFFFFF",
        },
        "Sheet": {
            "Tile": {"Border": {"Show": True}},
            "TileLayout": {"Gutter": {"Show": False}, "Margin": {"Show": False}},
        },
        "Typography": {"FontFamilies": [
            {"FontFamily": "Amazon Ember"}, {"FontFamily": "sans-serif"}
        ]},
    }


def _describe_wait(describe: Callable[[], dict[str, Any]], state_path: tuple[str, ...],
                   success: set[str], failures: set[str], label: str) -> dict[str, Any]:
    deadline = time.monotonic() + QUICKSIGHT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = describe()
        value: Any = response
        for key in state_path:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        state = str(value)
        if state in success:
            return response
        if state in failures or state.endswith("FAILED"):
            raise RuntimeError(f"{label} entered state {state}")
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"{label} did not stabilize before the timeout")


def _retry_quicksight_conflict(operation: Callable[[], Any], label: str) -> Any:
    deadline = time.monotonic() + QUICKSIGHT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            return operation()
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code != "ConflictException":
                raise
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"{label} remained busy before the timeout")


def _upsert_theme(qs: Any, account_id: str, theme_id: str, owner_arn: str) -> None:
    common = {
        "AwsAccountId": account_id, "ThemeId": theme_id,
        "Name": "Quick Observability", "BaseThemeId": "RAINIER",
        "Configuration": _theme_configuration(),
    }
    try:
        qs.describe_theme(AwsAccountId=account_id, ThemeId=theme_id)
        qs.update_theme(**common, VersionDescription="Managed by CloudFormation")
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_theme(**common, Permissions=[{"Principal": owner_arn, "Actions": THEME_ACTIONS}])
    _describe_wait(
        lambda: qs.describe_theme(AwsAccountId=account_id, ThemeId=theme_id),
        ("Theme", "Version", "Status"), {"CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"},
        {"CREATION_FAILED", "UPDATE_FAILED"}, "theme",
    )
    qs.update_theme_permissions(
        AwsAccountId=account_id, ThemeId=theme_id,
        GrantPermissions=[{"Principal": owner_arn, "Actions": THEME_ACTIONS}],
    )


def _upsert_data_source(qs: Any, account_id: str, source_id: str,
                        workgroup: str, owner_arn: str) -> None:
    common = {
        "AwsAccountId": account_id, "DataSourceId": source_id,
        "Name": "Quick Observability - Athena",
        "DataSourceParameters": {"AthenaParameters": {"WorkGroup": workgroup}},
        "SslProperties": {"DisableSsl": False},
    }
    try:
        qs.describe_data_source(AwsAccountId=account_id, DataSourceId=source_id)
        qs.update_data_source(**common)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_data_source(
            **common, Type="ATHENA",
            Permissions=_permissions(owner_arn, "datasource"),
        )
    _describe_wait(
        lambda: qs.describe_data_source(AwsAccountId=account_id, DataSourceId=source_id),
        ("DataSource", "Status"), {"CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"},
        {"CREATION_FAILED", "UPDATE_FAILED"}, "data source",
    )
    qs.update_data_source_permissions(
        AwsAccountId=account_id, DataSourceId=source_id,
        GrantPermissions=_permissions(owner_arn, "datasource"),
    )


def _dataset_payload(config: dict[str, Any], prefix: str, database: str,
                     source_arn: str) -> dict[str, Any]:
    physical = {"CustomSQL": {"CustomSql": {
        "DataSourceArn": source_arn, "Name": config["name"],
        "SqlQuery": config["sql"].format(database=database).strip(),
        "Columns": config["input_columns"],
    }}}
    payload: dict[str, Any] = {
        "DataSetId": f"{prefix}-{config['id_suffix']}", "Name": config["name"],
        "PhysicalTableMap": physical, "ImportMode": "SPICE",
    }
    projected = config.get("projected_columns")
    if projected:
        payload["LogicalTableMap"] = {"LogicalTable": {
            "Alias": config["name"],
            "DataTransforms": [{"ProjectOperation": {"ProjectedColumns": projected}}],
            "Source": {"PhysicalTableId": "CustomSQL"},
        }}
    return payload


def _upsert_dataset(qs: Any, account_id: str, config: dict[str, Any], prefix: str,
                    database: str, source_arn: str,
                    owner_arn: str) -> tuple[str, str | None]:
    payload = _dataset_payload(config, prefix, database, source_arn)
    data_set_id = payload["DataSetId"]
    try:
        qs.describe_data_set(AwsAccountId=account_id, DataSetId=data_set_id)
        result = qs.update_data_set(AwsAccountId=account_id, **payload)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        result = qs.create_data_set(
            AwsAccountId=account_id, **payload,
            Permissions=_permissions(owner_arn, "dataset"),
        )
    _retry_quicksight_conflict(
        lambda: qs.update_data_set_permissions(
            AwsAccountId=account_id, DataSetId=data_set_id,
            GrantPermissions=_permissions(owner_arn, "dataset"),
        ),
        f"dataset {data_set_id} permissions",
    )
    ingestion_id = result.get("IngestionId")
    schedule = {
        "ScheduleId": f"{prefix}-{config['id_suffix']}-daily",
        "ScheduleFrequency": {"Interval": "HOURLY", "Timezone": "UTC"},
        "RefreshType": "FULL_REFRESH",
    }
    try:
        qs.describe_refresh_schedule(
            AwsAccountId=account_id, DataSetId=data_set_id,
            ScheduleId=schedule["ScheduleId"],
        )
        qs.update_refresh_schedule(AwsAccountId=account_id, DataSetId=data_set_id, Schedule=schedule)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_refresh_schedule(AwsAccountId=account_id, DataSetId=data_set_id, Schedule=schedule)
    return (
        _arn(qs.meta.region_name, account_id, "dataset", data_set_id),
        ingestion_id,
    )


def _wait_for_ingestions(qs: Any, account_id: str,
                         pending: dict[str, str]) -> None:
    """Wait for all SPICE ingestions concurrently within one shared deadline."""
    deadline = time.monotonic() + 420
    remaining = dict(pending)
    while remaining and time.monotonic() < deadline:
        for data_set_id, ingestion_id in list(remaining.items()):
            ingestion = qs.describe_ingestion(
                AwsAccountId=account_id,
                DataSetId=data_set_id,
                IngestionId=ingestion_id,
            )["Ingestion"]
            status = ingestion["IngestionStatus"]
            if status == "COMPLETED":
                remaining.pop(data_set_id)
            elif status in {"FAILED", "CANCELLED"}:
                detail = ingestion.get("ErrorInfo", {}).get("Message", status)
                raise RuntimeError(
                    f"Dataset ingestion {data_set_id} failed: {detail[:500]}"
                )
        if remaining:
            time.sleep(POLL_SECONDS)
    if remaining:
        names = ", ".join(sorted(remaining))
        raise TimeoutError(f"Dataset ingestions did not complete: {names}")


def _upsert_analysis(qs: Any, account_id: str, analysis_id: str, definition: dict[str, Any],
                     theme_arn: str, owner_arn: str) -> None:
    common = {
        "AwsAccountId": account_id, "AnalysisId": analysis_id,
        "Name": "Quick Observability Analysis", "Definition": definition,
        "ThemeArn": theme_arn,
    }
    try:
        response = qs.describe_analysis(AwsAccountId=account_id, AnalysisId=analysis_id)
        if response.get("Analysis", {}).get("Status") == "DELETED":
            qs.restore_analysis(AwsAccountId=account_id, AnalysisId=analysis_id)
            _describe_wait(
                lambda: qs.describe_analysis(
                    AwsAccountId=account_id, AnalysisId=analysis_id
                ),
                ("Analysis", "Status"), {"CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"},
                {"CREATION_FAILED", "UPDATE_FAILED", "DELETE_FAILED"}, "analysis restore",
            )
        qs.update_analysis(**common)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_analysis(**common, Permissions=_permissions(owner_arn, "analysis"))
    _describe_wait(
        lambda: qs.describe_analysis(AwsAccountId=account_id, AnalysisId=analysis_id),
        ("Analysis", "Status"), {"CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"},
        {"CREATION_FAILED", "UPDATE_FAILED"}, "analysis",
    )
    qs.update_analysis_permissions(
        AwsAccountId=account_id, AnalysisId=analysis_id,
        GrantPermissions=_permissions(owner_arn, "analysis"),
    )


def _upsert_dashboard(qs: Any, account_id: str, dashboard_id: str,
                      definition: dict[str, Any], theme_arn: str,
                      owner_arn: str, namespace_arn: str) -> None:
    common = {
        "AwsAccountId": account_id, "DashboardId": dashboard_id,
        "Name": "Quick Observability Dashboard", "Definition": definition,
        "ThemeArn": theme_arn,
    }
    try:
        qs.describe_dashboard(AwsAccountId=account_id, DashboardId=dashboard_id)
        qs.update_dashboard(**common)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_dashboard(**common, Permissions=_permissions(owner_arn, "dashboard"))
    _describe_wait(
        lambda: qs.describe_dashboard(AwsAccountId=account_id, DashboardId=dashboard_id),
        ("Dashboard", "Version", "Status"),
        {"CREATION_SUCCESSFUL", "UPDATE_SUCCESSFUL"},
        {"CREATION_FAILED", "UPDATE_FAILED"}, "dashboard",
    )
    qs.update_dashboard_permissions(
        AwsAccountId=account_id, DashboardId=dashboard_id,
        GrantPermissions=_permissions(owner_arn, "dashboard"),
        GrantLinkPermissions=[{"Principal": namespace_arn, "Actions": LINK_ACTIONS}],
    )


def _topic_payload(prefix: str, region: str, account_id: str) -> dict[str, Any]:
    topic_datasets = []
    for config in DATASET_CONFIGS:
        columns = TOPIC_COLUMNS.get(config["id_suffix"], [])
        if not columns:
            continue
        dataset: dict[str, Any] = {
            "DatasetArn": _arn(region, account_id, "dataset", f"{prefix}-{config['id_suffix']}"),
            "DatasetName": config["name"], "DatasetDescription": config["description"],
            "Columns": columns,
        }
        column_names = {column["Name"] for column in config.get("input_columns", [])}
        if "event_time" in column_names:
            dataset["DataAggregation"] = {
                "DatasetRowDateGranularity": "DAY", "DefaultDateColumnName": "event_time"
            }
        topic_datasets.append(dataset)
    return {
        "Name": "Quick Observability",
        "Description": (
            "Unified topic for Quick Suite usage, adoption, satisfaction, cost, "
            "API activity, and performance metrics"
        ),
        "UserExperienceVersion": "NEW_READER_EXPERIENCE",
        "ConfigOptions": {"QBusinessInsightsEnabled": True},
        "DataSets": topic_datasets,
    }


def _upsert_topic(qs: Any, account_id: str, topic_id: str, prefix: str,
                  region: str, owner_arn: str) -> None:
    common = {
        "AwsAccountId": account_id, "TopicId": topic_id,
        "Topic": _topic_payload(prefix, region, account_id),
        "CustomInstructions": {"CustomInstructionsString": CUSTOM_INSTRUCTIONS},
    }
    try:
        qs.describe_topic(AwsAccountId=account_id, TopicId=topic_id)
        qs.update_topic(**common)
    except ClientError as error:
        if not _is_not_found(error):
            raise
        qs.create_topic(**common)
    deadline = time.monotonic() + QUICKSIGHT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            qs.describe_topic(AwsAccountId=account_id, TopicId=topic_id)
            break
        except ClientError as error:
            if not _is_not_found(error):
                raise
        time.sleep(POLL_SECONDS)
    else:
        raise TimeoutError("topic was not visible before the timeout")
    _retry_quicksight_conflict(
        lambda: qs.update_topic_permissions(
            AwsAccountId=account_id, TopicId=topic_id,
            GrantPermissions=_permissions(owner_arn, "topic"),
        ),
        "topic permissions",
    )


def _revoke_previous_permissions(
    qs: Any,
    account_id: str,
    prefix: str,
    old_owner_arn: str | None,
    old_namespace_arn: str | None,
    include_topic: bool,
) -> None:
    """Remove superseded grants only after replacement grants are established."""
    operations: list[tuple[str, Callable[[], Any]]] = []
    if old_owner_arn:
        operations.extend([
            ("theme owner revocation", lambda: qs.update_theme_permissions(
                AwsAccountId=account_id,
                ThemeId=f"{prefix}-observability-theme",
                RevokePermissions=[{"Principal": old_owner_arn, "Actions": THEME_ACTIONS}],
            )),
            ("data source owner revocation", lambda: qs.update_data_source_permissions(
                AwsAccountId=account_id,
                DataSourceId=f"{prefix}-athena-source",
                RevokePermissions=_permissions(old_owner_arn, "datasource"),
            )),
            ("analysis owner revocation", lambda: qs.update_analysis_permissions(
                AwsAccountId=account_id,
                AnalysisId=f"{prefix}-observability-analysis",
                RevokePermissions=_permissions(old_owner_arn, "analysis"),
            )),
            ("dashboard owner revocation", lambda: qs.update_dashboard_permissions(
                AwsAccountId=account_id,
                DashboardId=f"{prefix}-observability-dashboard",
                RevokePermissions=_permissions(old_owner_arn, "dashboard"),
            )),
        ])
        for config in DATASET_CONFIGS:
            data_set_id = f"{prefix}-{config['id_suffix']}"
            operations.append((
                f"dataset {data_set_id} owner revocation",
                lambda ds=data_set_id: qs.update_data_set_permissions(
                    AwsAccountId=account_id,
                    DataSetId=ds,
                    RevokePermissions=_permissions(old_owner_arn, "dataset"),
                ),
            ))
        if include_topic:
            operations.append(("topic owner revocation", lambda: qs.update_topic_permissions(
                AwsAccountId=account_id,
                TopicId=f"{prefix}-observability-topic",
                RevokePermissions=_permissions(old_owner_arn, "topic"),
            )))
    if old_namespace_arn:
        operations.append(("dashboard namespace revocation", lambda: qs.update_dashboard_permissions(
            AwsAccountId=account_id,
            DashboardId=f"{prefix}-observability-dashboard",
            RevokeLinkPermissions=[{"Principal": old_namespace_arn, "Actions": LINK_ACTIONS}],
        )))
    for label, operation in operations:
        _retry_quicksight_conflict(operation, label)


def _delete(ignore_not_found: Callable[[], Any]) -> None:
    try:
        ignore_not_found()
    except ClientError as error:
        if not _is_not_found(error):
            raise


def _resource_exists(describe: Callable[[], Any]) -> bool:
    try:
        response = describe()
        for value in response.values():
            if isinstance(value, dict) and value.get("Status") == "DELETED":
                return False
        return True
    except ClientError as error:
        if _is_not_found(error):
            return False
        raise


def _quicksight_collisions(qs: Any, account_id: str, prefix: str) -> list[str]:
    checks: dict[str, Callable[[], Any]] = {
        "theme": lambda: qs.describe_theme(
            AwsAccountId=account_id, ThemeId=f"{prefix}-observability-theme"
        ),
        "data source": lambda: qs.describe_data_source(
            AwsAccountId=account_id, DataSourceId=f"{prefix}-athena-source"
        ),
        "analysis": lambda: qs.describe_analysis(
            AwsAccountId=account_id, AnalysisId=f"{prefix}-observability-analysis"
        ),
        "dashboard": lambda: qs.describe_dashboard(
            AwsAccountId=account_id, DashboardId=f"{prefix}-observability-dashboard"
        ),
        "topic": lambda: qs.describe_topic(
            AwsAccountId=account_id, TopicId=f"{prefix}-observability-topic"
        ),
    }
    for config in DATASET_CONFIGS:
        data_set_id = f"{prefix}-{config['id_suffix']}"
        checks[f"dataset {data_set_id}"] = lambda ds=data_set_id: qs.describe_data_set(
            AwsAccountId=account_id, DataSetId=ds
        )
    return [name for name, check in checks.items() if _resource_exists(check)]


def _delete_quicksight(qs: Any, account_id: str, prefix: str) -> None:
    _log("QuickSight: deleting managed resources")
    _delete(lambda: qs.delete_topic(
        AwsAccountId=account_id, TopicId=f"{prefix}-observability-topic"
    ))
    _delete(lambda: qs.delete_dashboard(
        AwsAccountId=account_id, DashboardId=f"{prefix}-observability-dashboard"
    ))
    _delete(lambda: qs.delete_analysis(
        AwsAccountId=account_id, AnalysisId=f"{prefix}-observability-analysis"
    ))
    for config in reversed(DATASET_CONFIGS):
        data_set_id = f"{prefix}-{config['id_suffix']}"
        schedule_id = f"{prefix}-{config['id_suffix']}-daily"
        _delete(lambda ds=data_set_id, schedule=schedule_id: qs.delete_refresh_schedule(
            AwsAccountId=account_id, DataSetId=ds, ScheduleId=schedule
        ))
        _delete(lambda ds=data_set_id: qs.delete_data_set(
            AwsAccountId=account_id, DataSetId=ds
        ))
    _delete(lambda: qs.delete_data_source(
        AwsAccountId=account_id, DataSourceId=f"{prefix}-athena-source"
    ))
    _delete(lambda: qs.delete_theme(
        AwsAccountId=account_id, ThemeId=f"{prefix}-observability-theme"
    ))


def _quicksight(props: dict[str, Any], request_type: str,
                old_props: dict[str, Any] | None = None) -> dict[str, Any]:
    region = _prop(props, "Region", default=os.environ.get("AWS_REGION"))
    account_id = str(_prop(props, "AwsAccountId", "AccountId", required=True))
    prefix = str(_prop(props, "ResourcePrefix", "Prefix", default="quickobserve"))
    token = str(_prop(props, "_StackId", required=True))
    database = _validate_identifier(
        _prop(props, "DatabaseName", "Database", default="quickobserve_db"), "database name"
    )
    workgroup = _prop(props, "WorkGroup", "Workgroup", default="primary")
    owner_arn = _prop(props, "OwnerArn", "QuickSightOwnerArn", required=True)
    namespace = _prop(props, "Namespace", default="default")
    include_topic = _bool(_prop(props, "CreateTopic", "EnableTopic", default=False))
    qs = boto3.client("quicksight", region_name=region)
    ssm = boto3.client("ssm", region_name=region)
    owner_name = _ownership_parameter(prefix, "quicksight")
    ownership = _ownership_state(ssm, owner_name, token)

    if request_type == "Delete":
        if ownership != "owned":
            _log(f"QuickSight: skipping unowned prefix {prefix}")
            return {}
        _delete_quicksight(qs, account_id, prefix)
        _release_ownership(ssm, owner_name)
        return {}

    old_prefix = prefix
    if old_props:
        old_prefix = str(_prop(
            old_props, "ResourcePrefix", "Prefix", default=prefix
        ))
    previous_owner_arn = None
    previous_namespace_arn = None
    if request_type == "Update" and old_props and old_prefix == prefix:
        old_owner_arn = str(_prop(
            old_props, "OwnerArn", "QuickSightOwnerArn", default=owner_arn
        ))
        old_namespace = str(_prop(old_props, "Namespace", default=namespace))
        if old_owner_arn != owner_arn:
            previous_owner_arn = old_owner_arn
        if old_namespace != namespace:
            previous_namespace_arn = _arn(
                region, account_id, "namespace", old_namespace
            )
    if request_type == "Update" and old_prefix != prefix:
        old_owner_name = _ownership_parameter(old_prefix, "quicksight")
        if _ownership_state(ssm, old_owner_name, token) != "owned":
            raise RuntimeError("Previous QuickSight prefix ownership could not be verified")
        _delete_quicksight(qs, account_id, old_prefix)
        _release_ownership(ssm, old_owner_name)
        ownership = _ownership_state(ssm, owner_name, token)

    if ownership == "foreign":
        raise RuntimeError(f"QuickSight prefix {prefix} is owned by another deployment")
    if ownership == "unclaimed":
        collisions = _quicksight_collisions(qs, account_id, prefix)
        if collisions:
            names = ", ".join(collisions)
            raise RuntimeError(
                f"QuickSight resources already exist for prefix {prefix}: {names}"
            )
        _claim_ownership(ssm, owner_name, token)
    elif request_type == "Update" and ownership != "owned":
        raise RuntimeError("QuickSight update rejected because ownership could not be verified")

    theme_id = f"{prefix}-observability-theme"
    source_id = f"{prefix}-athena-source"
    analysis_id = f"{prefix}-observability-analysis"
    dashboard_id = f"{prefix}-observability-dashboard"
    topic_id = f"{prefix}-observability-topic"
    theme_arn = _arn(region, account_id, "theme", theme_id)
    source_arn = _arn(region, account_id, "datasource", source_id)
    namespace_arn = _arn(region, account_id, "namespace", namespace)

    _log("QuickSight: upserting theme and Athena data source")
    _upsert_theme(qs, account_id, theme_id, owner_arn)
    _upsert_data_source(qs, account_id, source_id, workgroup, owner_arn)
    pending_ingestions: dict[str, str] = {}
    for config in DATASET_CONFIGS:
        _log(f"QuickSight: upserting dataset {config['id_suffix']}")
        _, ingestion_id = _upsert_dataset(
            qs, account_id, config, prefix, database, source_arn, owner_arn
        )
        if ingestion_id:
            pending_ingestions[f"{prefix}-{config['id_suffix']}"] = ingestion_id
    if pending_ingestions:
        _log("QuickSight: waiting for SPICE ingestions")
        _wait_for_ingestions(qs, account_id, pending_ingestions)
    definition = build_definition(prefix, region, account_id)
    _log("QuickSight: upserting analysis and dashboard")
    _upsert_analysis(qs, account_id, analysis_id, definition, theme_arn, owner_arn)
    _upsert_dashboard(
        qs, account_id, dashboard_id, definition, theme_arn, owner_arn, namespace_arn
    )
    data = {
        "DashboardArn": _arn(region, account_id, "dashboard", dashboard_id),
        "AnalysisArn": _arn(region, account_id, "analysis", analysis_id),
        "ThemeArn": theme_arn,
        "TopicArn": "",
    }
    if include_topic:
        _log("QuickSight: upserting topic")
        _upsert_topic(qs, account_id, topic_id, prefix, region, owner_arn)
        data["TopicArn"] = _arn(region, account_id, "topic", topic_id)
    else:
        _delete(lambda: qs.delete_topic(AwsAccountId=account_id, TopicId=topic_id))
    _revoke_previous_permissions(
        qs,
        account_id,
        prefix,
        previous_owner_arn,
        previous_namespace_arn,
        include_topic,
    )
    return data


def handler(event: dict[str, Any], context: Any) -> None:
    physical_id = event.get("PhysicalResourceId") or _physical_id(event)
    try:
        request_type = event.get("RequestType")
        if request_type not in {"Create", "Update", "Delete"}:
            raise ValueError(f"Unsupported RequestType: {request_type}")
        props = dict(event.get("ResourceProperties", {}))
        props["_StackId"] = event.get("StackId", "")
        old_props = dict(event.get("OldResourceProperties", {}))
        if old_props:
            old_props["_StackId"] = event.get("StackId", "")
        kind = props.get("ResourceKind")
        _log(f"Handling {request_type} for {kind}")
        if kind == "catalog":
            data = _catalog(props, request_type, old_props)
        elif kind == "quicksight":
            data = _quicksight(props, request_type, old_props)
        else:
            raise ValueError(f"Unsupported ResourceKind: {kind}")
        _response(event, context, "SUCCESS", data=data, physical_id=physical_id)
    except Exception as error:
        message = f"{type(error).__name__}: {str(error)[:1000]}"
        _log(f"Request failed: {message}")
        try:
            _response(event, context, "FAILED", reason=message, physical_id=physical_id)
        except Exception as response_error:
            _log(f"CloudFormation response failed: {type(response_error).__name__}")
