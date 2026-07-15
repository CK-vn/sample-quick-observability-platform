locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  database_name               = coalesce(var.database_name, replace(var.resource_prefix, "-", "_"))
  data_lake_bucket_name       = coalesce(var.data_lake_bucket_name, "${var.resource_prefix}-datalake-${local.account_id}-${var.aws_region}")
  athena_results_bucket_name  = coalesce(var.athena_results_bucket_name, "${var.resource_prefix}-athena-${local.account_id}-${var.aws_region}")
  pipeline_name               = "${var.resource_prefix}-pipeline"
  quicksight_account_arn      = "arn:${local.partition}:quicksight:${var.aws_region}:${local.account_id}:account/${local.account_id}"
  quicksight_namespace_arn    = "arn:${local.partition}:quicksight:${var.aws_region}:${local.account_id}:namespace/${var.quicksight_namespace}"
  quicksight_service_role_arn = aws_iam_role.quicksight_athena.arn

  tags = merge(
    {
      project   = "quick-observability"
      managedBy = "terraform"
    },
    var.tags,
  )

  firehose_streams = {
    chat = {
      name           = "${local.pipeline_name}-chat-logs"
      prefix         = "cloudwatch-logs/chat/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
      error_prefix   = "errors/chat/"
      transform      = "logs"
      log_group_name = var.log_group_names.chat
    }
    feedback = {
      name           = "${local.pipeline_name}-feedback-logs"
      prefix         = "cloudwatch-logs/feedback/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
      error_prefix   = "errors/feedback/"
      transform      = "logs"
      log_group_name = var.log_group_names.feedback
    }
    agent_hours = {
      name           = "${local.pipeline_name}-agent-hours"
      prefix         = "cloudwatch-logs/agent-hours/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
      error_prefix   = "errors/agent-hours/"
      transform      = "logs"
      log_group_name = var.log_group_names.agent_hours
    }
    index_usage = {
      name           = "${local.pipeline_name}-index-usage"
      prefix         = "cloudwatch-logs/index-usage/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
      error_prefix   = "errors/index-usage/"
      transform      = "logs"
      log_group_name = var.log_group_names.index_usage
    }
    cloudtrail = {
      name           = "${local.pipeline_name}-cloudtrail-events"
      prefix         = "cloudtrail/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
      error_prefix   = "errors/cloudtrail/"
      transform      = "cloudtrail"
      log_group_name = null
    }
  }

  vended_logs = {
    chat = {
      log_type         = "CHAT_LOGS"
      source_name      = "${var.resource_prefix}-chat-logs"
      destination_name = "${var.resource_prefix}-chat-destination"
      log_group_name   = var.log_group_names.chat
      record_fields = concat([
        "user_arn", "user_type", "status_code", "conversation_id",
        "system_message_id", "user_message_id", "agent_id", "flow_id",
        "message_scope", "user_selected_resources", "action_connectors",
        "cited_resource", "file_attachment", "resource_arn",
        "event_timestamp", "logType", "accountId", "namespace", "latency",
        "time_to_first_token", "surface_type", "web_search",
      ], var.include_message_content ? ["user_message", "system_text_message"] : [])
    }
    feedback = {
      log_type         = "FEEDBACK_LOGS"
      source_name      = "${var.resource_prefix}-feedback-logs"
      destination_name = "${var.resource_prefix}-feedback-destination"
      log_group_name   = var.log_group_names.feedback
      record_fields = [
        "user_arn", "user_type", "status_code", "conversation_id",
        "system_message_id", "user_message_id", "research_id",
        "feedback_type", "feedback_reason", "feedback_details", "rating",
        "resource_arn", "event_timestamp", "logType", "accountId", "namespace",
      ]
    }
    agent_hours = {
      log_type         = "AGENT_HOURS_LOGS"
      source_name      = "${var.resource_prefix}-agent-hours-logs"
      destination_name = "${var.resource_prefix}-agent-hours-destination"
      log_group_name   = var.log_group_names.agent_hours
      record_fields = [
        "user_arn", "subscription_type", "reporting_service", "usage_group",
        "usage_hours", "service_resource_arn", "resource_arn",
        "event_timestamp", "logType", "accountId",
      ]
    }
    index_usage = {
      log_type         = "INDEX_USAGE_LOGS"
      source_name      = "${var.resource_prefix}-index-usage-logs"
      destination_name = "${var.resource_prefix}-index-usage-destination"
      log_group_name   = var.log_group_names.index_usage
      record_fields = [
        "resource_arn", "event_timestamp", "log_type", "account_id", "user_arn",
        "consumed_index_size", "source_type", "source_name", "source_arn",
        "consumed_source_size", "consumed_source_doc_count",
      ]
    }
  }
}
