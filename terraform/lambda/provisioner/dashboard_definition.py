"""Dashboard data and pure QuickSight-definition builders packaged with the Terraform provisioner."""

DATASET_CONFIGS = [
    {
        "id_suffix": "chat-activity",
        "name": "Chat Activity",
        "description": (
            "User conversations across features: Chat Agents, Flows, "
            "Connectors, Spaces, and web search with latency and surface type"
        ),
        "sql": """
SELECT
    from_iso8601_timestamp(timestamp) AS event_time,
    user_arn AS user_id,
    CASE WHEN user_arn LIKE '%/%' THEN ELEMENT_AT(SPLIT(user_arn, '/'), -1) ELSE user_arn END AS user_name,
    status_code AS status,
    conversation_id,
    user_message,
    agent_id,
    flow_id,
    action_connectors,
    namespace,
    CASE
        WHEN flow_id IS NOT NULL AND flow_id != '' AND flow_id != '-' THEN 'Flow'
        WHEN agent_id = 'SYSTEM' THEN 'System Chat Agent (My Assistant)'
        WHEN agent_id IS NOT NULL AND agent_id != '' AND agent_id != '-' THEN 'Custom Chat Agent'
        ELSE ''
    END AS feature,
    CAST(latency AS DOUBLE) AS latency_ms,
    CAST(time_to_first_token AS DOUBLE) AS time_to_first_token_ms,
    surface_type,
    web_search,
    message_scope,
    account_id,
    year, month, day
FROM {database}.chat_logs
WHERE timestamp IS NOT NULL
""",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "user_id", "Type": "STRING"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "status", "Type": "STRING"},
            {"Name": "conversation_id", "Type": "STRING"},
            {"Name": "user_message", "Type": "STRING"},
            {"Name": "agent_id", "Type": "STRING"},
            {"Name": "flow_id", "Type": "STRING"},
            {"Name": "action_connectors", "Type": "STRING"},
            {"Name": "namespace", "Type": "STRING"},
            {"Name": "feature", "Type": "STRING"},
            {"Name": "latency_ms", "Type": "DECIMAL"},
            {"Name": "time_to_first_token_ms", "Type": "DECIMAL"},
            {"Name": "surface_type", "Type": "STRING"},
            {"Name": "web_search", "Type": "STRING"},
            {"Name": "message_scope", "Type": "STRING"},
            {"Name": "account_id", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "user_name", "feature", "status",
            "conversation_id", "user_message", "agent_id", "flow_id",
            "latency_ms", "time_to_first_token_ms",
            "surface_type", "web_search", "message_scope",
            "action_connectors", "namespace", "account_id",
        ],
    },
    {
        "id_suffix": "feedback-analysis",
        "name": "Feedback Analysis",
        "description": (
            "User feedback including satisfaction ratings, reasons, "
            "and whether it relates to Research or Chat"
        ),
        "sql": """
SELECT
    from_iso8601_timestamp(timestamp) AS event_time,
    user_arn AS user_id,
    CASE WHEN user_arn LIKE '%/%' THEN ELEMENT_AT(SPLIT(user_arn, '/'), -1) ELSE user_arn END AS user_name,
    status_code AS status,
    conversation_id,
    research_id,
    CASE
        WHEN research_id IS NOT NULL AND research_id != '' AND research_id != '-' THEN 'Research'
        ELSE 'Chat'
    END AS feedback_source,
    feedback_type,
    feedback_reason AS reason,
    feedback_details AS details,
    rating,
    namespace,
    account_id,
    year, month, day
FROM {database}.feedback_logs
WHERE timestamp IS NOT NULL
""",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "user_id", "Type": "STRING"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "status", "Type": "STRING"},
            {"Name": "conversation_id", "Type": "STRING"},
            {"Name": "research_id", "Type": "STRING"},
            {"Name": "feedback_source", "Type": "STRING"},
            {"Name": "feedback_type", "Type": "STRING"},
            {"Name": "reason", "Type": "STRING"},
            {"Name": "details", "Type": "STRING"},
            {"Name": "rating", "Type": "STRING"},
            {"Name": "namespace", "Type": "STRING"},
            {"Name": "account_id", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "user_name", "status", "conversation_id",
            "research_id", "feedback_source", "feedback_type",
            "reason", "details", "rating", "namespace", "account_id",
        ],
    },
    {
        "id_suffix": "agent-hours-usage",
        "name": "Agent Hours Usage",
        "description": (
            "Hours consumption by service (Research, Chat, Automation, "
            "Spaces, Knowledge Bases) with resource type parsed from ARN"
        ),
        "sql": """
SELECT
    from_iso8601_timestamp(timestamp) AS event_time,
    user_arn AS user_id,
    CASE WHEN user_arn LIKE '%/%' THEN ELEMENT_AT(SPLIT(user_arn, '/'), -1) ELSE user_arn END AS user_name,
    subscription_type,
    reporting_service AS service,
    usage_group,
    usage_hours AS hours,
    service_resource_arn,
    CASE
        WHEN reporting_service = 'AUTOMATION' THEN 'Automation'
        WHEN reporting_service = 'FLOW' THEN 'Flow'
        WHEN reporting_service = 'RESEARCH' THEN 'Research'
        ELSE reporting_service
    END AS resource_type,
    CASE
        WHEN service_resource_arn LIKE '%/%'
            THEN ELEMENT_AT(SPLIT(service_resource_arn, '/'), -1)
        ELSE service_resource_arn
    END AS resource_id,
    account_id,
    year, month, day
FROM {database}.agent_hours_logs
WHERE timestamp IS NOT NULL
""",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "user_id", "Type": "STRING"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "subscription_type", "Type": "STRING"},
            {"Name": "service", "Type": "STRING"},
            {"Name": "usage_group", "Type": "STRING"},
            {"Name": "hours", "Type": "DECIMAL"},
            {"Name": "service_resource_arn", "Type": "STRING"},
            {"Name": "resource_type", "Type": "STRING"},
            {"Name": "resource_id", "Type": "STRING"},
            {"Name": "account_id", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "user_name", "service", "hours",
            "usage_group", "resource_type", "resource_id",
            "subscription_type", "service_resource_arn", "account_id",
        ],
    },
    {
        "id_suffix": "api-audit-trail",
        "name": "API Audit Trail",
        "description": (
            "Quick Sight API calls from CloudTrail with feature "
            "categorization based on API action names"
        ),
        "sql": """
SELECT
    from_iso8601_timestamp(timestamp) AS event_time,
    event_id,
    event_name AS api_action,
    event_source,
    event_type,
    user_name,
    user_type,
    source_ip,
    user_agent,
    aws_region,
    CASE WHEN read_only = true THEN 'Read' ELSE 'Write' END AS read_or_write,
    error_code,
    error_message,
    resource_type,
    resource_arn,
    request_parameters,
    recipient_account_id,
    shared_event_id,
    CASE
        WHEN (event_name LIKE '%Automation%' OR event_name LIKE '%Deployment%') AND event_name NOT LIKE 'Search%'
            THEN 'Automation'
        WHEN event_name LIKE '%PassAction%' THEN 'Connector'
        WHEN event_name LIKE '%Workflow%' THEN 'Workflow'
        WHEN event_name LIKE '%Research%' THEN 'Research'
        WHEN event_name LIKE '%Dashboard%' THEN 'Dashboard'
        WHEN event_name LIKE '%Analysis%' OR event_name LIKE '%Analys%' THEN 'Analysis'
        WHEN event_name LIKE '%DataSet%' OR event_name LIKE '%Dataset%' THEN 'Dataset'
        WHEN event_name LIKE '%DataSource%' THEN 'Data Source'
        WHEN event_name LIKE '%Ingestion%' OR event_name LIKE '%Refresh%' THEN 'Ingestion'
        WHEN event_name LIKE '%Topic%' THEN 'Topic'
        WHEN event_name LIKE '%Space' THEN 'Space'
        WHEN event_name LIKE '%KnowledgeBase%' OR event_name LIKE '%Knowledge%' THEN 'Knowledgebase'
        WHEN event_name LIKE '%Folder%' THEN 'Folder'
        WHEN event_name LIKE '%Template%' THEN 'Template'
        WHEN event_name LIKE '%Theme%' THEN 'Theme'
        WHEN event_name LIKE '%Embed%' THEN 'Embedding'
        WHEN event_name LIKE '%Authorization%' THEN 'Authorization'
        WHEN event_name LIKE 'Search%' THEN 'Search'
        WHEN event_name LIKE '%Database%' THEN 'Database'
        ELSE event_name
    END AS api_feature,
    account_id,
    year, month, day
FROM {database}.cloudtrail_events
""",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "event_id", "Type": "STRING"},
            {"Name": "api_action", "Type": "STRING"},
            {"Name": "event_source", "Type": "STRING"},
            {"Name": "event_type", "Type": "STRING"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "user_type", "Type": "STRING"},
            {"Name": "source_ip", "Type": "STRING"},
            {"Name": "user_agent", "Type": "STRING"},
            {"Name": "aws_region", "Type": "STRING"},
            {"Name": "read_or_write", "Type": "STRING"},
            {"Name": "error_code", "Type": "STRING"},
            {"Name": "error_message", "Type": "STRING"},
            {"Name": "resource_type", "Type": "STRING"},
            {"Name": "resource_arn", "Type": "STRING"},
            {"Name": "request_parameters", "Type": "STRING"},
            {"Name": "recipient_account_id", "Type": "STRING"},
            {"Name": "shared_event_id", "Type": "STRING"},
            {"Name": "api_feature", "Type": "STRING"},
            {"Name": "account_id", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "event_id", "api_action", "event_source",
            "event_type", "user_name", "user_type", "source_ip",
            "user_agent", "aws_region", "read_or_write", "error_code",
            "error_message", "resource_type", "resource_arn",
            "request_parameters", "recipient_account_id",
            "api_feature", "account_id",
        ],
    },
    {
        "id_suffix": "index-usage",
        "name": "Index Usage",
        "description": (
            "Per-source storage metrics for knowledge bases and Spaces "
            "including consumed index size, source size, and document counts"
        ),
        "sql": """
SELECT
    event_time,
    user_name,
    consumed_index_size,
    consumed_index_size_gb,
    consumed_index_size_mb,
    source_type,
    source_name,
    source_arn,
    consumed_source_size,
    consumed_source_size_gb,
    consumed_source_size_mb,
    consumed_source_doc_count,
    account_id,
    year, month, day
FROM {database}.index_usage
""",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "consumed_index_size", "Type": "INTEGER"},
            {"Name": "consumed_index_size_gb", "Type": "DECIMAL"},
            {"Name": "consumed_index_size_mb", "Type": "DECIMAL"},
            {"Name": "source_type", "Type": "STRING"},
            {"Name": "source_name", "Type": "STRING"},
            {"Name": "source_arn", "Type": "STRING"},
            {"Name": "consumed_source_size", "Type": "INTEGER"},
            {"Name": "consumed_source_size_gb", "Type": "DECIMAL"},
            {"Name": "consumed_source_size_mb", "Type": "DECIMAL"},
            {"Name": "consumed_source_doc_count", "Type": "INTEGER"},
            {"Name": "account_id", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "user_name", "consumed_index_size",
            "consumed_index_size_gb", "consumed_index_size_mb",
            "source_type", "source_name", "source_arn",
            "consumed_source_size", "consumed_source_size_gb",
            "consumed_source_size_mb", "consumed_source_doc_count",
            "account_id",
        ],
    },
    {
        "id_suffix": "licensed-users",
        "name": "Licensed Users",
        "description": (
            "Licensed Quick Sight users joined against their most recent "
            "activity timestamp and computed inactivity period"
        ),
        "sql": "SELECT * FROM {database}.licensed_users_activity",
        "input_columns": [
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "user_arn", "Type": "STRING"},
            {"Name": "email", "Type": "STRING"},
            {"Name": "role", "Type": "STRING"},
            {"Name": "last_activity_timestamp", "Type": "DATETIME"},
            {"Name": "first_seen_date", "Type": "DATETIME"},
            {"Name": "inactivity_period", "Type": "INTEGER"},
            {"Name": "account_id", "Type": "STRING"},
        ],
        "projected_columns": [
            "user_name", "user_arn", "email", "role",
            "last_activity_timestamp", "first_seen_date",
            "inactivity_period", "account_id",
        ],
    },
    {
        "id_suffix": "function-usage-distribution",
        "name": "Function Usage Distribution",
        "description": (
            "Combined Chat Activity and Agent Hours Usage records labeled "
            "by function category for a percentage-of-total breakdown"
        ),
        "sql": "SELECT * FROM {database}.function_usage_distribution",
        "input_columns": [
            {"Name": "event_time", "Type": "DATETIME"},
            {"Name": "user_name", "Type": "STRING"},
            {"Name": "category", "Type": "STRING"},
            {"Name": "year", "Type": "INTEGER"},
            {"Name": "month", "Type": "INTEGER"},
            {"Name": "day", "Type": "INTEGER"},
        ],
        "projected_columns": [
            "event_time", "user_name", "category",
        ],
    },
]

TOPIC_COLUMNS = {
    "chat-activity": [
        {"ColumnName": "event_time", "ColumnFriendlyName": "Event Time", "ColumnDescription": "Timestamp of the chat message", "ColumnSynonyms": ["date", "time", "when", "timestamp", "message date"], "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": True, "SemanticType": {"TypeName": "DATE"}, "TimeGranularity": "DAY", "DefaultFormatting": {"DisplayFormat": "DATE"}},
        {"ColumnName": "user_name", "ColumnFriendlyName": "User", "ColumnDescription": "Name of the user who sent the message", "ColumnSynonyms": ["person", "employee", "who", "sender"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "PERSON"}},
        {"ColumnName": "feature", "ColumnFriendlyName": "Feature", "ColumnDescription": "Which feature was used: Chat Agent, Flow, Automation, or Direct Chat", "ColumnSynonyms": ["product", "capability", "feature type", "what feature"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "status", "ColumnFriendlyName": "Status", "ColumnDescription": "Response status code (success, request_blocked, no_answer_found)", "ColumnSynonyms": ["result", "outcome", "status code"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "conversation_id", "ColumnFriendlyName": "Conversation", "ColumnDescription": "Unique conversation identifier", "ColumnSynonyms": ["chat", "session", "thread"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "agent_id", "ColumnFriendlyName": "Chat Agent", "ColumnDescription": "Chat agent that handled the message", "ColumnSynonyms": ["bot", "assistant", "agent", "q agent"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "flow_id", "ColumnFriendlyName": "Flow", "ColumnDescription": "Flow identifier used in the conversation", "ColumnSynonyms": ["workflow", "flow"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "action_connectors", "ColumnFriendlyName": "Action Connector", "ColumnDescription": "Automation action connector invoked during the conversation", "ColumnSynonyms": ["automation", "connector", "action"], "IsIncludedInTopic": True},
        {"ColumnDataRole": "MEASURE", "ColumnName": "latency_ms", "ColumnFriendlyName": "Latency (ms)", "ColumnDescription": "End-to-end response latency in milliseconds", "ColumnSynonyms": ["response time", "delay", "speed", "how long", "duration"], "IsIncludedInTopic": True, "Aggregation": "AVERAGE", "SemanticType": {"TypeName": "DURATION", "TypeParameters": {"Unit": "MILLISECOND"}}},
        {"ColumnDataRole": "MEASURE", "ColumnName": "time_to_first_token_ms", "ColumnFriendlyName": "Time to First Token (ms)", "ColumnDescription": "Time until the first response token in milliseconds", "ColumnSynonyms": ["ttft", "first token", "initial response time"], "IsIncludedInTopic": True, "Aggregation": "AVERAGE", "SemanticType": {"TypeName": "DURATION", "TypeParameters": {"Unit": "MILLISECOND"}}},
        {"ColumnName": "surface_type", "ColumnFriendlyName": "Surface Type", "ColumnDescription": "Where the chat originated (console, IDE, etc.)", "ColumnSynonyms": ["channel", "interface", "source", "origin"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "web_search", "ColumnFriendlyName": "Web Search Used", "ColumnDescription": "Whether web search was used for the response", "ColumnSynonyms": ["internet", "web", "search"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "message_scope", "ColumnFriendlyName": "Message Scope", "ColumnDescription": "Resource scope of the message: no_resources, all_resources, or specific_resource", "ColumnSynonyms": ["scope", "resource scope", "context"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "namespace", "ColumnFriendlyName": "Namespace", "IsIncludedInTopic": True},
        {"ColumnName": "account_id", "ColumnFriendlyName": "Account Id", "IsIncludedInTopic": False},
    ],
    "feedback-analysis": [
        {"ColumnName": "event_time", "ColumnFriendlyName": "Event Time", "ColumnDescription": "When the feedback was submitted", "ColumnSynonyms": ["date", "time", "when", "timestamp"], "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": True, "SemanticType": {"TypeName": "DATE"}, "TimeGranularity": "DAY"},
        {"ColumnName": "user_name", "ColumnFriendlyName": "User", "ColumnDescription": "User who submitted feedback", "ColumnSynonyms": ["person", "employee", "who", "reviewer"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "PERSON"}},
        {"ColumnName": "feedback_source", "ColumnFriendlyName": "Feedback Source", "ColumnDescription": "Whether feedback is for Research or Chat", "ColumnSynonyms": ["source", "from research", "from chat"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "reason", "ColumnFriendlyName": "Reason", "ColumnDescription": "Reason selected for the feedback", "ColumnSynonyms": ["why", "cause", "feedback reason"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "details", "ColumnFriendlyName": "Details", "ColumnDescription": "Free-text feedback details written by the user", "ColumnSynonyms": ["comment", "note", "text", "written feedback"], "IsIncludedInTopic": True},
        {"ColumnName": "rating", "ColumnFriendlyName": "Rating", "ColumnDescription": "Numeric rating if provided", "ColumnSynonyms": ["score", "stars", "numeric rating"], "IsIncludedInTopic": True},
        {"ColumnName": "status", "ColumnFriendlyName": "Status", "ColumnDescription": "Response status code for the feedback event", "ColumnSynonyms": ["result", "outcome", "status code"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "conversation_id", "ColumnFriendlyName": "Conversation", "ColumnDescription": "Conversation the feedback relates to", "ColumnSynonyms": ["chat", "session", "thread"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "research_id", "ColumnFriendlyName": "Research ID", "ColumnDescription": "Research session the feedback relates to", "ColumnSynonyms": ["research", "research session"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "namespace", "ColumnFriendlyName": "Namespace", "IsIncludedInTopic": True},
        {"ColumnName": "account_id", "ColumnFriendlyName": "Account Id", "IsIncludedInTopic": False},
        {"ColumnName": "feedback_type", "ColumnFriendlyName": "Feedback Type", "IsIncludedInTopic": True},
    ],
    "agent-hours-usage": [
        {"ColumnName": "event_time", "ColumnFriendlyName": "Event Time", "ColumnDescription": "When the usage was recorded", "ColumnSynonyms": ["date", "time", "when", "timestamp"], "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": True, "SemanticType": {"TypeName": "DATE"}, "TimeGranularity": "DAY"},
        {"ColumnName": "user_name", "ColumnFriendlyName": "User", "ColumnDescription": "User consuming agent hours", "ColumnSynonyms": ["person", "employee", "who", "consumer"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "PERSON"}},
        {"ColumnName": "subscription_type", "ColumnFriendlyName": "Subscription", "ColumnDescription": "Subscription tier (Pro, Reader, etc.)", "ColumnSynonyms": ["plan", "tier", "license"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "service", "ColumnFriendlyName": "Service", "ColumnDescription": "Service consuming hours: Research, Chat, Automation, Flows, etc.", "ColumnSynonyms": ["product", "feature", "reporting service", "research", "chat", "automation", "flows"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "usage_group", "ColumnFriendlyName": "Usage Group", "ColumnDescription": "Whether hours are included or extra", "ColumnSynonyms": ["included", "extra", "overage", "billing group"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnDataRole": "MEASURE", "ColumnName": "hours", "ColumnFriendlyName": "Hours", "ColumnDescription": "Number of agent hours consumed", "ColumnSynonyms": ["usage", "consumption", "time used", "agent hours", "cost"], "IsIncludedInTopic": True, "Aggregation": "SUM"},
        {"ColumnName": "resource_type", "ColumnFriendlyName": "Resource Type", "ColumnDescription": "Service consuming hours: Automation, Flow, Research", "ColumnSynonyms": ["resource", "asset", "service type"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "resource_id", "ColumnFriendlyName": "Resource ID", "ColumnDescription": "Specific resource identifier consuming hours", "ColumnSynonyms": ["resource name", "resource id"], "IsIncludedInTopic": True, "Aggregation": "DISTINCT_COUNT"},
        {"ColumnName": "service_resource_arn", "ColumnFriendlyName": "Service Resource Arn", "IsIncludedInTopic": True},
        {"ColumnName": "account_id", "ColumnFriendlyName": "Account Id", "IsIncludedInTopic": False},
    ],
    "api-audit-trail": [
        {"ColumnName": "event_time", "ColumnFriendlyName": "Event Time", "ColumnDescription": "When the API call occurred", "ColumnSynonyms": ["date", "time", "when", "timestamp"], "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": True, "SemanticType": {"TypeName": "DATE"}, "TimeGranularity": "DAY"},
        {"ColumnName": "event_id", "ColumnFriendlyName": "Event ID", "ColumnDescription": "Unique CloudTrail event identifier for cross-referencing", "ColumnSynonyms": ["event id", "trail id", "cloudtrail id"], "IsIncludedInTopic": True},
        {"ColumnName": "api_action", "ColumnFriendlyName": "API Action", "ColumnDescription": "Quick Sight API operation called (CreateDashboard, DescribeDataSet, etc.)", "ColumnSynonyms": ["operation", "action", "event", "api call", "method"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "event_source", "ColumnFriendlyName": "Event Source", "ColumnDescription": "AWS service that generated the event (quicksight.amazonaws.com)", "ColumnSynonyms": ["source service", "aws service"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "user_name", "ColumnFriendlyName": "Caller", "ColumnDescription": "IAM user or role that made the call", "ColumnSynonyms": ["who", "user", "caller", "identity", "principal"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "PERSON"}},
        {"ColumnName": "source_ip", "ColumnFriendlyName": "Source IP", "ColumnDescription": "IP address the call originated from", "ColumnSynonyms": ["ip", "ip address", "origin", "client ip"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "IP_ADDRESS"}},
        {"ColumnName": "aws_region", "ColumnFriendlyName": "Region", "ColumnDescription": "AWS region where the API call was made", "ColumnSynonyms": ["region", "location"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "error_code", "ColumnFriendlyName": "Error Code", "ColumnDescription": "Error code if the call failed", "ColumnSynonyms": ["error", "failure", "exception"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "read_or_write", "ColumnFriendlyName": "Read or Write", "ColumnDescription": "Whether the API call was read-only or a write operation", "ColumnSynonyms": ["read", "write", "mutation"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "resource_type", "ColumnFriendlyName": "Resource Type", "ColumnDescription": "Type of Quick Sight resource affected (dashboard, dataset, analysis, etc.)", "ColumnSynonyms": ["resource", "asset type"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "resource_arn", "ColumnFriendlyName": "Resource ARN", "ColumnDescription": "ARN of the primary Quick Sight resource affected", "ColumnSynonyms": ["arn", "resource"], "IsIncludedInTopic": True},
        {"ColumnName": "request_parameters", "ColumnFriendlyName": "Request Parameters", "ColumnDescription": "JSON payload of the API call showing what was requested", "ColumnSynonyms": ["parameters", "payload", "request", "what changed"], "IsIncludedInTopic": True},
        {"ColumnName": "recipient_account_id", "ColumnFriendlyName": "Recipient Account", "ColumnDescription": "Account that received the CloudTrail event (for cross-account scenarios)", "ColumnSynonyms": ["recipient", "target account", "cross account"], "IsIncludedInTopic": True},
        {"ColumnName": "user_agent", "ColumnFriendlyName": "User Agent", "ColumnDescription": "Client user agent string (SDK, console, CLI)", "ColumnSynonyms": ["client", "sdk", "tool"], "IsIncludedInTopic": True},
        {"ColumnName": "error_message", "ColumnFriendlyName": "Error Message", "ColumnDescription": "Detailed error message if the API call failed", "ColumnSynonyms": ["error detail", "failure message", "what went wrong"], "IsIncludedInTopic": True},
        {"ColumnName": "api_feature", "ColumnFriendlyName": "API Feature", "ColumnDescription": "Feature category of the API call: Dashboard, Space, Knowledge Base, Dataset, Q Topic, etc.", "ColumnSynonyms": ["feature", "category", "what feature", "space", "knowledge base", "dashboard"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "user_type", "ColumnFriendlyName": "User Type", "IsIncludedInTopic": True},
        {"ColumnName": "event_type", "ColumnFriendlyName": "Event Type", "IsIncludedInTopic": True},
        {"ColumnName": "account_id", "ColumnFriendlyName": "Account Id", "IsIncludedInTopic": False},
    ],
    "index-usage": [
        {"ColumnName": "event_time", "ColumnFriendlyName": "Event Time", "ColumnDescription": "Timestamp of the index usage measurement", "ColumnSynonyms": ["date", "time", "when", "timestamp", "measurement date"], "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": True, "SemanticType": {"TypeName": "DATE"}, "TimeGranularity": "DAY", "DefaultFormatting": {"DisplayFormat": "DATE"}},
        {"ColumnDataRole": "MEASURE", "ColumnName": "consumed_index_size_gb", "ColumnFriendlyName": "Index Size (GB)", "ColumnDescription": "Total consumed index size in gigabytes", "ColumnSynonyms": ["index size", "total size", "index gb", "storage size", "index storage"], "IsIncludedInTopic": True, "Aggregation": "SUM"},
        {"ColumnDataRole": "MEASURE", "ColumnName": "consumed_source_size_gb", "ColumnFriendlyName": "Source Size (GB)", "ColumnDescription": "Size consumed by this source in gigabytes", "ColumnSynonyms": ["source size", "source gb", "kb size", "space size", "data size"], "IsIncludedInTopic": True, "Aggregation": "SUM"},
        {"ColumnDataRole": "MEASURE", "ColumnName": "consumed_source_doc_count", "ColumnFriendlyName": "Document Count", "ColumnDescription": "Number of documents from this source", "ColumnSynonyms": ["docs", "documents", "doc count", "number of documents", "file count"], "IsIncludedInTopic": True, "Aggregation": "SUM"},
        {"ColumnName": "source_type", "ColumnFriendlyName": "Source Type", "ColumnDescription": "Type of source: KB (Knowledge Base) or SPACE", "ColumnSynonyms": ["type", "kb or space", "knowledge base", "space", "source category"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "CATEGORY"}},
        {"ColumnName": "source_name", "ColumnFriendlyName": "Source Name", "ColumnDescription": "Human-readable name of the knowledge base or Space", "ColumnSynonyms": ["name", "kb name", "space name", "source", "resource name"], "IsIncludedInTopic": True},
        {"ColumnName": "source_arn", "ColumnFriendlyName": "Source ARN", "ColumnDescription": "Full ARN of the source resource", "ColumnSynonyms": ["arn", "resource arn", "source resource"], "IsIncludedInTopic": True},
        {"ColumnName": "user_name", "ColumnFriendlyName": "User", "ColumnDescription": "User associated with the index usage event", "ColumnSynonyms": ["person", "employee", "who", "owner"], "IsIncludedInTopic": True, "SemanticType": {"TypeName": "PERSON"}},
        {"ColumnName": "account_id", "ColumnFriendlyName": "Account Id", "IsIncludedInTopic": False},
    ],
}

CUSTOM_INSTRUCTIONS = (
    "This topic answers questions about Amazon Quick Suite usage, adoption, "
    "satisfaction, and governance.\n\n"
    "Route questions to the appropriate dataset based on the question type:\n\n"
    "For questions about chat conversations, feature adoption, who is using "
    "Quick, top users, number of chat sessions, which chat agents or flows "
    "are used, latency, or surface type: use the Chat Activity dataset. "
    "The feature column has values: System Chat Agent (My Assistant), "
    "Custom Chat Agent, Flow. Use user_name for user identity "
    "and conversation_id for session counts.\n\n"
    "For questions about user satisfaction, feedback, thumbs up/down, "
    "useful vs not useful, feedback reasons (Inaccurate, Incomplete, "
    "Too wordy, Too slow, etc.), or feedback details/comments: use the "
    "Feedback Analysis dataset. The feedback_type column has values: "
    "Useful, Not Useful. The reason column has the specific feedback reason. "
    "The details column has verbatim user comments.\n\n"
    "For questions about agent hours, hours spent on Research, Flow, "
    "Automation, hours by resource type (Space, Knowledge Base, Dashboard), "
    "included vs extra hours, or top users by hours consumption: use the "
    "Agent Hours Usage dataset. The service column has values: RESEARCH, "
    "FLOW, AUTOMATION, CHAT. The usage_group column has: Included, Extra. "
    "The hours column is the numeric hours consumed.\n\n"
    "For questions about Quick Sight API activity, governance, who is "
    "creating or modifying assets, CRUD operations, API errors, "
    "feature-level API usage (Dashboard, Space, Knowledge Base, Flow, "
    "Automation, Connector), or read vs write operations: use the API "
    "Audit Trail dataset. The api_feature column categorizes the API call. "
    "The read_or_write column has values: Read, Write.\n\n"
    "For questions about storage, index size, knowledge base size, "
    "Space size, document count, GB consumed, top sources, top users "
    "by storage, or how much index capacity is used: use the Index Usage "
    "dataset. The consumed_index_size_gb column is the total index size "
    "in gigabytes. The consumed_source_size_gb column is the size consumed "
    "by an individual source. The source_type column has values: SPACE, KB "
    "(Knowledge Base). The source_name column is the human-readable name "
    "of the knowledge base or Space. The consumed_source_doc_count column "
    "is the number of documents from each source.\n\n"
    "When the user asks about 'features', show breakdown by the feature "
    "column from Chat Activity (System Chat Agent, Custom Chat Agent, "
    "Flow), or by service from Agent Hours (Research, Flow, "
    "Automation, Chat), or by api_feature from API Audit Trail.\n\n"
    "When the user asks about 'top users', use user_name from the "
    "relevant dataset with DISTINCT_COUNT or SUM as appropriate."
)

def _make_visual(visual_id, title, visual_type, field_wells, drill_path=None,
                  dataset=None, missing_data_treatment=None):
    """Build a simplified visual spec dict.
    
    drill_path: optional list of column names for drill-down hierarchy.
    E.g. ["feature", "user_name", "conversation_id"] lets users click
    feature → user → conversation.
    dataset: optional DATASET_CONFIGS id_suffix override. When omitted, the
    visual sources from its sheet's own dataset.
    missing_data_treatment: optional TreatmentOption (e.g. "SHOW_AS_ZERO")
    applied to a LINE visual's PrimaryYAxisMissingDataConfiguration.
    """
    return {
        "visual_id": visual_id,
        "title": title,
        "type": visual_type,
        "field_wells": field_wells,
        "drill_path": drill_path,
        "dataset": dataset,
        "missing_data_treatment": missing_data_treatment,
    }

SHEET_DEFS = [
    # ── Sheet 1: Adoption Story ──────────────────────────────────────────
    # "How is Amazon Quick being adopted across the organization?"
    {
        "id_suffix": "adoption",
        "name": "Chat Agents Usage",
        "dataset": "chat-activity",
        "visuals": [
            _make_visual("adopt-kpi-users", "Active Users", "KPI",
                         {"values": [{"field": "user_name", "agg": "DISTINCT_COUNT"}]}),
            _make_visual("adopt-kpi-convos", "Total Chat Sessions", "KPI",
                         {"values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}]}),
            _make_visual("adopt-trend", "Daily Active Users", "LINE",
                         {"category": "event_time", "values": [{"field": "user_name", "agg": "DISTINCT_COUNT"}]},
                         drill_path=["event_time", "feature", "user_name"],
                         missing_data_treatment="SHOW_AS_ZERO"),
            _make_visual("adopt-features", "Chat Sessions by Feature", "BAR",
                         {"category": "feature", "values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}]},
                         drill_path=["feature", "user_name"]),
            _make_visual("adopt-top-users", "Top Users by Chat Sessions", "BAR",
                         {"category": "user_name", "values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}]},
                         drill_path=["user_name", "feature"]),
            _make_visual("adopt-feature-trend", "Feature Adoption Over Time", "LINE",
                         {"category": "event_time", "values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}],
                          "group": "feature"},
                         drill_path=["event_time", "feature", "user_name"]),
            _make_visual("adopt-usage-volume-total", "Usage Volume by Day", "BAR",
                         {"category": "event_time", "values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}]},
                         drill_path=["event_time", "feature", "user_name"]),
            _make_visual("adopt-usage-volume-avg", "Average Daily Usage Volume", "KPI",
                         {"values": [{"field": "daily_avg_usage_volume", "agg": "NONE"}]}),
            _make_visual("adopt-function-distribution", "Function Usage Distribution", "PIE",
                         {"category": "category", "values": [{"field": "category", "agg": "COUNT"}]},
                         dataset="function-usage-distribution"),
            _make_visual("adopt-by-status", "Sessions by Status", "BAR",
                         {"category": "status", "values": [{"field": "conversation_id", "agg": "DISTINCT_COUNT"}]},
                         drill_path=["status", "user_name"]),
            _make_visual("adopt-details", "Chat Session Details", "TABLE",
                         {"category": "event_time",
                          "extra_dimensions": ["user_name", "feature", "status", "conversation_id", "user_message", "latency_ms", "surface_type"],
                          "values": [],
                          "sort_desc": "event_time"}),
        ],
    },
    # ── Sheet 2: Hours & Investment ──────────────────────────────────────
    # "Where are the agent hours going? Is the investment paying off?"
    {
        "id_suffix": "cost",
        "name": "Hours Spent on Research, Flow, Automation",
        "dataset": "agent-hours-usage",
        "visuals": [
            _make_visual("cost-kpi-hours", "Total Agent Hours", "KPI",
                         {"values": [{"field": "hours", "agg": "SUM"}]}),
            _make_visual("cost-by-service", "Agent Hours by Service", "PIE",
                         {"category": "service", "values": [{"field": "hours", "agg": "SUM"}]},
                         drill_path=["service", "resource_type", "user_name"]),
            _make_visual("cost-top-users", "Top Users by Agent Hours", "BAR",
                         {"category": "user_name", "values": [{"field": "hours", "agg": "SUM"}]},
                         drill_path=["user_name", "service"]),
            _make_visual("cost-by-group", "Included vs Extra Hours", "PIE",
                         {"category": "usage_group", "values": [{"field": "hours", "agg": "SUM"}]},
                         drill_path=["usage_group", "service", "user_name"]),
            _make_visual("cost-trend", "Agent Hours Trend by Service", "LINE",
                         {"category": "event_time", "values": [{"field": "hours", "agg": "SUM"}],
                          "group": "service"},
                         drill_path=["event_time", "service", "user_name"]),
            _make_visual("cost-hours-volume-total", "Agent Hours Volume by Day", "BAR",
                         {"category": "event_time", "values": [{"field": "hours", "agg": "SUM"}]},
                         drill_path=["event_time", "resource_type", "user_name"]),
            _make_visual("cost-hours-volume-avg", "Average Daily Agent Hours", "KPI",
                         {"values": [{"field": "daily_avg_agent_hours", "agg": "NONE"}]}),
            _make_visual("cost-details", "Agent Hours Details", "TABLE",
                         {"category": "event_time",
                          "extra_dimensions": ["user_name", "service", "hours", "usage_group", "resource_type", "resource_id"],
                          "values": [],
                          "sort_desc": "event_time"}),
        ],
    },
    # ── Sheet 3: User Satisfaction ───────────────────────────────────────
    # "Are users finding Quick useful? What's not working?"
    {
        "id_suffix": "satisfaction",
        "name": "User Feedback",
        "dataset": "feedback-analysis",
        "visuals": [
            _make_visual("sat-useful", "Satisfaction Distribution", "PIE",
                         {"category": "feedback_type", "values": [{"field": "feedback_type", "agg": "COUNT"}]},
                         drill_path=["feedback_type", "user_name"]),
            _make_visual("sat-reasons", "Top Feedback Reasons", "BAR",
                         {"category": "reason", "values": [{"field": "reason", "agg": "COUNT"}]},
                         drill_path=["reason", "user_name"]),
            _make_visual("sat-details", "Feedback Details", "TABLE",
                         {"category": "user_name",
                          "extra_dimensions": ["feedback_type", "feedback_source", "reason", "details"],
                          "values": []}),
        ],
    },
    # ── Sheet 4: Governance ──────────────────────────────────────────────
    # "Who is managing Quick Sight assets? What features are being adopted via API?"
    {
        "id_suffix": "governance",
        "name": "Governance & Admin Activity",
        "dataset": "api-audit-trail",
        "visuals": [
            _make_visual("gov-by-feature", "API Activity by Feature", "BAR",
                         {"category": "api_feature", "values": [{"field": "api_action", "agg": "COUNT"}]},
                         drill_path=["api_feature", "api_action", "user_name"]),
            _make_visual("gov-top-admins", "API Callers by Identity Type", "PIE",
                         {"category": "user_type", "values": [{"field": "api_action", "agg": "COUNT"}]},
                         drill_path=["user_type", "api_feature"]),
            _make_visual("gov-details", "Recent API Operations", "TABLE",
                         {"category": "event_time",
                          "extra_dimensions": ["event_id", "api_action", "api_feature", "user_name", "user_type", "read_or_write", "resource_arn", "error_code"],
                          "values": [],
                          "sort_desc": "event_time"}),
        ],
    },
    # ── Sheet 5: Index Storage Usage ─────────────────────────────────────
    # "How much index storage is consumed? Which sources are the largest?"
    {
        "id_suffix": "index-storage",
        "name": "Index Storage Usage",
        "dataset": "index-usage",
        "visuals": [
            _make_visual("idx-kpi-size", "Total Index Size (GB)", "KPI",
                         {"values": [{"field": "consumed_index_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-by-type", "Storage by Source Type", "PIE",
                         {"category": "source_type", "values": [{"field": "consumed_source_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-trend", "Index Storage Trend", "LINE",
                         {"category": "event_time", "values": [{"field": "consumed_index_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-top-kb", "Top Knowledge Bases by Size", "BAR",
                         {"category": "source_name", "values": [{"field": "consumed_source_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-top-spaces", "Top Spaces by Size", "BAR",
                         {"category": "source_name", "values": [{"field": "consumed_source_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-top-users", "Top Users by Storage", "BAR",
                         {"category": "user_name", "values": [{"field": "consumed_source_size_gb", "agg": "SUM"}]}),
            _make_visual("idx-details", "All Sources Detail", "TABLE",
                         {"category": "event_time",
                          "extra_dimensions": ["source_name", "source_type", "source_arn", "consumed_source_size_gb", "consumed_source_doc_count", "consumed_index_size_gb", "user_name"],
                          "values": [],
                          "sort_desc": "event_time"}),
        ],
        # Visual-scoped category filters for the KB and SPACE bar charts
        "visual_filters": [
            {"visual_id": "idx-top-kb", "column": "source_type", "values": ["KB"]},
            {"visual_id": "idx-top-spaces", "column": "source_type", "values": ["SPACE"]},
        ],
    },
    # ── Sheet 6: Licensed Users ──────────────────────────────────────────
    # "Which licensed users are inactive, and by how much, so licenses can
    # be reclaimed?" This sheet's dataset ("licensed-users") has no
    # event_time column — it is keyed on inactivity_period instead — so it
    # is excluded from the generic sheet-level date-range filter/controls
    # and instead gets its own InactivityThresholdDays slider + filter.
    {
        "id_suffix": "licensed-users",
        "name": "Licensed Users",
        "dataset": "licensed-users",
        "visuals": [
            _make_visual("licensed-kpi-total", "Total Licensed Users", "KPI",
                         {"values": [{"field": "user_name", "agg": "DISTINCT_COUNT"}]}),
            _make_visual("licensed-kpi-inactive", "Inactive Licensed Users", "KPI",
                         {"values": [{"field": "user_name", "agg": "DISTINCT_COUNT"}]}),
            _make_visual("licensed-inactive-table", "Inactive Licensed Users", "TABLE",
                         {"category": "user_name",
                          "extra_dimensions": ["role", "last_activity_timestamp", "inactivity_period"],
                          "values": [],
                          "sort_desc": "inactivity_period"}),
        ],
    },
]

OWNER_ACTIONS = {
    "datasource": [
        "quicksight:DescribeDataSource",
        "quicksight:DescribeDataSourcePermissions",
        "quicksight:PassDataSource",
        "quicksight:UpdateDataSource",
        "quicksight:UpdateDataSourcePermissions",
        "quicksight:DeleteDataSource",
    ],
    "dataset": [
        "quicksight:DescribeDataSet",
        "quicksight:DescribeDataSetPermissions",
        "quicksight:PassDataSet",
        "quicksight:DescribeIngestion",
        "quicksight:ListIngestions",
        "quicksight:UpdateDataSet",
        "quicksight:DeleteDataSet",
        "quicksight:CreateIngestion",
        "quicksight:CancelIngestion",
        "quicksight:UpdateDataSetPermissions",
    ],
    "dashboard": [
        "quicksight:DescribeDashboard",
        "quicksight:ListDashboardVersions",
        "quicksight:UpdateDashboardPermissions",
        "quicksight:QueryDashboard",
        "quicksight:UpdateDashboard",
        "quicksight:DeleteDashboard",
        "quicksight:UpdateDashboardPublishedVersion",
        "quicksight:DescribeDashboardPermissions",
    ],
    "analysis": [
        "quicksight:DescribeAnalysis",
        "quicksight:DescribeAnalysisPermissions",
        "quicksight:UpdateAnalysis",
        "quicksight:UpdateAnalysisPermissions",
        "quicksight:DeleteAnalysis",
        "quicksight:QueryAnalysis",
        "quicksight:RestoreAnalysis",
    ],
    "topic": [
        "quicksight:DescribeTopic",
        "quicksight:DescribeTopicRefresh",
        "quicksight:ListTopicRefreshSchedules",
        "quicksight:DescribeTopicRefreshSchedule",
        "quicksight:DeleteTopic",
        "quicksight:UpdateTopic",
        "quicksight:CreateTopicRefreshSchedule",
        "quicksight:DeleteTopicRefreshSchedule",
        "quicksight:UpdateTopicRefreshSchedule",
        "quicksight:DescribeTopicPermissions",
        "quicksight:UpdateTopicPermissions",
    ],
}

def _build_field_id(prefix, dataset_suffix, field_name):
    """Deterministic field ID for a dataset column."""
    return f"{prefix}-{dataset_suffix}-{field_name}"

def _build_measure(prefix, ds_suffix, spec):
    """Build a MeasureField from a visual field spec."""
    field = spec["field"]
    agg = spec.get("agg", "COUNT")
    fid = _build_field_id(prefix, ds_suffix, field) + f"-{agg.lower()}"
    col = {"DataSetIdentifier": ds_suffix, "ColumnName": field}

    if agg == "NONE":
        # Already-aggregated calculated field (e.g. a ratio of two
        # aggregates) -- QuickSight rejects stacking another
        # AggregationFunction on top of an aggregated calculated column.
        return {
            "NumericalMeasureField": {
                "FieldId": fid,
                "Column": col,
            }
        }

    if agg in ("COUNT", "DISTINCT_COUNT"):
        return {
            "CategoricalMeasureField": {
                "FieldId": fid,
                "Column": col,
                "AggregationFunction": agg,
            }
        }

    return {
        "NumericalMeasureField": {
            "FieldId": fid,
            "Column": col,
            "AggregationFunction": {
                "SimpleNumericalAggregation": agg,
            },
        }
    }

def _build_dimension(prefix, ds_suffix, col_name):
    """Build a DimensionField for a category column."""
    fid = _build_field_id(prefix, ds_suffix, col_name)
    col = {"DataSetIdentifier": ds_suffix, "ColumnName": col_name}
    if col_name in ("event_time",):
        return {"DateDimensionField": {"FieldId": fid, "Column": col, "DateGranularity": "DAY", "HierarchyId": fid}}
    return {"CategoricalDimensionField": {"FieldId": fid, "Column": col}}

def _build_visual_definition(prefix, ds_suffix, visual):
    """Convert simplified visual spec into a Quick Sight visual definition."""
    # A visual may override the sheet's own dataset via visual["dataset"],
    # e.g. to source from a different DATASET_CONFIGS entry than its sheet.
    ds_suffix = visual.get("dataset") or ds_suffix
    vid = f"{prefix}-{visual['visual_id']}"
    fw = visual["field_wells"]
    vtype = visual["type"]
    drill_path = visual.get("drill_path")
    title_config = {"Visibility": "VISIBLE", "FormatText": {"PlainText": visual["title"]}}

    # Business-friendly axis labels (replaces "field_name (Aggregation)")
    AXIS_LABELS = {
        "user_name-DISTINCT_COUNT": "Unique Users",
        "user_name-COUNT": "Users",
        "conversation_id-DISTINCT_COUNT": "Chat Sessions",
        "conversation_id-COUNT": "Chat Sessions",
        "satisfaction-COUNT": "Feedback Responses",
        "feedback_type-COUNT": "Feedback Responses",
        "reason-COUNT": "Feedback Responses",
        "feedback_source-COUNT": "Feedback Responses",
        "hours-SUM": "Agent Hours",
        "api_action-COUNT": "API Calls",
        "api_feature-COUNT": "API Calls",
        "user_type-COUNT": "API Calls",
        "read_or_write-COUNT": "API Calls",
        "usage_group-COUNT": "Records",
        "consumed_index_size_gb-SUM": "Index Size (GB)",
        "consumed_source_size_gb-SUM": "Source Size (GB)",
    }

    # Build drill-down hierarchies
    column_hierarchies = []

    # Datetime category fields require DateTimeHierarchy for drill-down
    if vtype not in ("KPI", "TABLE") and fw.get("category") == "event_time":
        dt_field_id = _build_field_id(prefix, ds_suffix, "event_time")
        column_hierarchies.append({
            "DateTimeHierarchy": {
                "HierarchyId": dt_field_id,
            }
        })

    # Build axis label overrides for measures
    def _axis_labels_for_measures(measures_specs):
        """Build ChartAxisLabelOptions for value axis with business-friendly labels."""
        labels = []
        for spec in measures_specs:
            field = spec["field"]
            agg = spec.get("agg", "COUNT")
            fid = _build_field_id(prefix, ds_suffix, field) + f"-{agg.lower()}"
            label_key = f"{field}-{agg}"
            custom_label = AXIS_LABELS.get(label_key)
            if custom_label:
                labels.append({
                    "CustomLabel": custom_label,
                    "ApplyTo": {
                        "FieldId": fid,
                        "Column": {"DataSetIdentifier": ds_suffix, "ColumnName": field},
                    }
                })
        if labels:
            return {"Visibility": "VISIBLE", "AxisLabelOptions": labels}
        return None

    if vtype == "KPI":
        measures = [_build_measure(prefix, ds_suffix, v) for v in fw["values"]]
        trend_dims = [_build_dimension(prefix, ds_suffix, fw["trend"])] if "trend" in fw else []
        return {
            "KPIVisual": {
                "VisualId": vid,
                "Title": title_config,
                "ChartConfiguration": {
                    "FieldWells": {
                        "Values": measures,
                        "TrendGroups": trend_dims,
                    }
                },
            }
        }

    category_dims = [_build_dimension(prefix, ds_suffix, fw["category"])]
    measures = [_build_measure(prefix, ds_suffix, v) for v in fw["values"]]
    group_dims = [_build_dimension(prefix, ds_suffix, fw["group"])] if "group" in fw else []

    if vtype == "LINE":
        chart_config = {
            "FieldWells": {
                "LineChartAggregatedFieldWells": {
                    "Category": category_dims,
                    "Values": measures,
                    "Colors": group_dims,
                }
            }
        }
        value_labels = _axis_labels_for_measures(fw["values"])
        if value_labels:
            chart_config["PrimaryYAxisLabelOptions"] = value_labels
        missing_data_treatment = visual.get("missing_data_treatment")
        if missing_data_treatment:
            chart_config["PrimaryYAxisDisplayOptions"] = {
                "MissingDataConfigurations": [
                    {"TreatmentOption": missing_data_treatment}
                ]
            }
        result = {
            "LineChartVisual": {
                "VisualId": vid,
                "Title": title_config,
                "ChartConfiguration": chart_config,
            }
        }
        if column_hierarchies:
            result["LineChartVisual"]["ColumnHierarchies"] = column_hierarchies
        return result

    if vtype in ("BAR", "STACKED_BAR"):
        chart_config = {
            "FieldWells": {
                "BarChartAggregatedFieldWells": {
                    "Category": category_dims,
                    "Values": measures,
                    "Colors": group_dims,
                }
            }
        }
        value_labels = _axis_labels_for_measures(fw["values"])
        if value_labels:
            chart_config["ValueLabelOptions"] = value_labels
        result = {
            "BarChartVisual": {
                "VisualId": vid,
                "Title": title_config,
                "ChartConfiguration": chart_config,
            }
        }
        if column_hierarchies:
            result["BarChartVisual"]["ColumnHierarchies"] = column_hierarchies
        return result

    if vtype == "PIE":
        result = {
            "PieChartVisual": {
                "VisualId": vid,
                "Title": title_config,
                "ChartConfiguration": {
                    "FieldWells": {
                        "PieChartAggregatedFieldWells": {
                            "Category": category_dims,
                            "Values": measures,
                        }
                    }
                },
            }
        }
        if column_hierarchies:
            result["PieChartVisual"]["ColumnHierarchies"] = column_hierarchies
        return result

    # TABLE — show raw detail rows when extra_dimensions is present
    if vtype == "TABLE":
        extra_dims = fw.get("extra_dimensions", [])
        if extra_dims:
            # Unaggregated table: show individual rows with multiple columns
            all_cols = [fw["category"]] + extra_dims
            unagg_fields = []
            for col_name in all_cols:
                fid = _build_field_id(prefix, ds_suffix, col_name) + "-unagg"
                unagg_fields.append({
                    "Column": {"DataSetIdentifier": ds_suffix, "ColumnName": col_name},
                    "FieldId": fid,
                })
            table_config = {
                "FieldWells": {
                    "TableUnaggregatedFieldWells": {
                        "Values": unagg_fields,
                    }
                },
            }
            # Add sort if specified
            sort_col = fw.get("sort_desc")
            if sort_col:
                sort_fid = _build_field_id(prefix, ds_suffix, sort_col) + "-unagg"
                table_config["SortConfiguration"] = {
                    "RowSort": [{
                        "FieldSort": {
                            "FieldId": sort_fid,
                            "Direction": "DESC",
                        }
                    }]
                }
            return {
                "TableVisual": {
                    "VisualId": vid,
                    "Title": title_config,
                    "ChartConfiguration": table_config,
                }
            }
        # Aggregated table fallback
        return {
            "TableVisual": {
                "VisualId": vid,
                "Title": title_config,
                "ChartConfiguration": {
                    "FieldWells": {
                        "TableAggregatedFieldWells": {
                            "GroupBy": category_dims,
                            "Values": measures,
                        }
                    }
                },
            }
        }

    # Fallback
    return {
        "TableVisual": {
            "VisualId": vid,
            "Title": title_config,
            "ChartConfiguration": {
                "FieldWells": {
                    "TableAggregatedFieldWells": {
                        "GroupBy": category_dims,
                        "Values": measures,
                    }
                }
            },
        }
    }

def _build_grid_layout(prefix, sheet_def):
    """Build GridLayout elements for a sheet.

    Layout rules (36-column grid):
    - KPI visuals: row 0, split evenly across 36 columns, 6 rows tall
    - Chart visuals: paired in 2-column layout, each 18 columns wide, 12 rows tall
    - Table visuals: full width 36 columns, 12 rows tall
    """
    elements = []

    # Collect KPIs and non-KPIs separately
    kpis = [(f"{prefix}-{v['visual_id']}", v) for v in sheet_def["visuals"] if v["type"] == "KPI"]
    charts = [(f"{prefix}-{v['visual_id']}", v) for v in sheet_def["visuals"] if v["type"] != "KPI"]

    # KPIs: split row 0 evenly
    if kpis:
        kpi_width = 36 // len(kpis) if kpis else 36
        for i, (vid, _) in enumerate(kpis):
            elements.append({
                "ElementId": vid,
                "ElementType": "VISUAL",
                "ColumnIndex": i * kpi_width,
                "RowIndex": 0,
                "ColumnSpan": kpi_width,
                "RowSpan": 6,
            })

    # Charts: paired side-by-side, 18 cols each, 12 rows tall
    chart_row = 6 if kpis else 0
    chart_col = 0
    for vid, visual in charts:
        vtype = visual["type"]
        if vtype == "TABLE":
            # If previous chart row has an unpaired chart, advance past it
            if chart_col > 0:
                chart_row += 12
                chart_col = 0
            elements.append({
                "ElementId": vid,
                "ElementType": "VISUAL",
                "ColumnIndex": 0,
                "RowIndex": chart_row,
                "ColumnSpan": 36,
                "RowSpan": 12,
            })
            chart_row += 12
        else:
            elements.append({
                "ElementId": vid,
                "ElementType": "VISUAL",
                "ColumnIndex": chart_col,
                "RowIndex": chart_row,
                "ColumnSpan": 18,
                "RowSpan": 12,
            })
            chart_col += 18
            if chart_col >= 36:
                chart_col = 0
                chart_row += 12

    return elements
