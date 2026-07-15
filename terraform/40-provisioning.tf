locals {
  provisioning_template = {
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "Lifecycle bridge for Terraform-managed observability provisioning Lambda"
    Resources = {
      Catalog = {
        Type = "Custom::QuickObservabilityCatalog"
        Properties = {
          ServiceToken          = aws_lambda_function.provisioner.arn
          ServiceTimeout        = 900
          ResourceKind          = "catalog"
          ResourcePrefix        = var.resource_prefix
          ConfigurationHash     = data.archive_file.provisioner.output_base64sha256
          Region                = var.aws_region
          DatabaseName          = local.database_name
          BucketName            = aws_s3_bucket.data_lake.id
          WorkGroup             = aws_athena_workgroup.observability.name
          AthenaOutputLocation  = "s3://${aws_s3_bucket.athena_results.id}/results/"
          IncludeMessageContent = tostring(var.include_message_content)
        }
      }
      QuickSight = {
        Type      = "Custom::QuickObservabilityQuickSight"
        DependsOn = "Catalog"
        Properties = {
          ServiceToken      = aws_lambda_function.provisioner.arn
          ServiceTimeout    = 900
          ResourceKind      = "quicksight"
          ConfigurationHash = data.archive_file.provisioner.output_base64sha256
          Region            = var.aws_region
          AwsAccountId      = local.account_id
          ResourcePrefix    = var.resource_prefix
          DatabaseName      = local.database_name
          WorkGroup         = aws_athena_workgroup.observability.name
          OwnerArn          = var.quicksight_owner_arn
          Namespace         = var.quicksight_namespace
          CreateTopic       = tostring(var.create_quicksight_topic)
        }
      }
    }
    Outputs = merge(
      {
        DashboardArn = { Value = { "Fn::GetAtt" = ["QuickSight", "DashboardArn"] } }
        AnalysisArn  = { Value = { "Fn::GetAtt" = ["QuickSight", "AnalysisArn"] } }
        ThemeArn     = { Value = { "Fn::GetAtt" = ["QuickSight", "ThemeArn"] } }
      },
      var.create_quicksight_topic ? {
        TopicArn = { Value = { "Fn::GetAtt" = ["QuickSight", "TopicArn"] } }
      } : {},
    )
  }
}

resource "aws_cloudformation_stack" "provisioning" {
  name               = "${var.resource_prefix}-terraform-provisioning"
  template_body      = jsonencode(local.provisioning_template)
  timeout_in_minutes = 60

  depends_on = [
    aws_lambda_permission.provisioner_cloudformation,
    aws_iam_role_policy.quicksight_observability,
    aws_s3_bucket_policy.data_lake,
    aws_s3_bucket_policy.athena_results,
    aws_cloudwatch_log_delivery.quick,
    aws_cloudwatch_log_subscription_filter.quick,
    aws_cloudwatch_event_target.quicksight_cloudtrail,
  ]
}
