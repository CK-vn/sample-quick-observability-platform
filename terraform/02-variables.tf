variable "aws_region" {
  description = "AWS Region containing the Amazon Quick subscription."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Optional shared AWS configuration profile. Leave null for the standard credential chain."
  type        = string
  default     = null
  nullable    = true
}

variable "resource_prefix" {
  description = "Lowercase prefix used for all resource names."
  type        = string
  default     = "quickobserve"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.resource_prefix))
    error_message = "resource_prefix must be 3-20 lowercase letters, numbers, or hyphens and start with a letter."
  }
}

variable "quicksight_owner_arn" {
  description = "ARN of the Amazon QuickSight user that owns the analysis, dashboard, datasets, theme, and topic."
  type        = string

  validation {
    condition     = can(regex("^arn:[^:]+:quicksight:[^:]+:[0-9]{12}:user/", var.quicksight_owner_arn))
    error_message = "quicksight_owner_arn must be a QuickSight user ARN."
  }
}

variable "quicksight_namespace" {
  description = "QuickSight namespace used for licensed-user snapshots and dashboard link sharing."
  type        = string
  default     = "default"
}

variable "database_name" {
  description = "Glue/Athena database name. Defaults to the resource prefix with hyphens replaced by underscores."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.database_name == null || can(regex("^[A-Za-z][A-Za-z0-9_]*$", var.database_name))
    error_message = "database_name must start with a letter and contain only letters, numbers, and underscores."
  }
}

variable "data_lake_bucket_name" {
  description = "Optional globally unique data-lake bucket name."
  type        = string
  default     = null
  nullable    = true
}

variable "athena_results_bucket_name" {
  description = "Optional globally unique Athena results bucket name."
  type        = string
  default     = null
  nullable    = true
}

variable "include_message_content" {
  description = "Retain user_message and system_text_message in the data lake and Athena table. Enabled by default; set false to exclude message text. Chat Activity and Chat Session Details expose user_message; topics and Agent Hours exclude message content."
  type        = bool
  default     = true
}

variable "create_quicksight_topic" {
  description = "Create the conversational analytics topic with the dashboard resources."
  type        = bool
  default     = true
}

variable "force_destroy_buckets" {
  description = "Delete data-lake and Athena result objects during terraform destroy. Keep false to protect collected data."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Retention for CloudWatch log groups managed by this deployment."
  type        = number
  default     = 30
}

variable "log_group_names" {
  description = "Amazon Quick vended-log group names."
  type = object({
    chat        = string
    feedback    = string
    agent_hours = string
    index_usage = string
  })
  default = {
    chat        = "/aws/vendedlogs/quick/chat"
    feedback    = "/aws/vendedlogs/quick/feedback"
    agent_hours = "/aws/vendedlogs/quick/agent-hours"
    index_usage = "/aws/vendedlogs/quick/index-usage"
  }
}

variable "tags" {
  description = "Additional tags applied to supported resources."
  type        = map(string)
  default     = {}
}
