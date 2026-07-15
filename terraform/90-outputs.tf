output "data_lake_bucket" {
  description = "S3 data-lake bucket receiving transformed observability records."
  value       = aws_s3_bucket.data_lake.id
}

output "athena_results_bucket" {
  description = "S3 bucket used by the managed Athena workgroup."
  value       = aws_s3_bucket.athena_results.id
}

output "athena_database" {
  description = "Glue/Athena observability database."
  value       = local.database_name
}

output "athena_workgroup" {
  description = "Athena workgroup used by QuickSight and provisioning."
  value       = aws_athena_workgroup.observability.name
}

output "kms_key_arn" {
  description = "Customer-managed key used by the deployment."
  value       = aws_kms_key.observability.arn
}

output "dashboard_arn" {
  description = "QuickSight dashboard ARN."
  value       = try(aws_cloudformation_stack.provisioning.outputs["DashboardArn"], null)
}

output "analysis_arn" {
  description = "QuickSight analysis ARN."
  value       = try(aws_cloudformation_stack.provisioning.outputs["AnalysisArn"], null)
}

output "topic_arn" {
  description = "QuickSight topic ARN when create_quicksight_topic is enabled."
  value       = try(aws_cloudformation_stack.provisioning.outputs["TopicArn"], null)
}

output "firehose_stream_arns" {
  description = "Firehose delivery stream ARNs keyed by source."
  value       = { for key, stream in aws_kinesis_firehose_delivery_stream.this : key => stream.arn }
}
