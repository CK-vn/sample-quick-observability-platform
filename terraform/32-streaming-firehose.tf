locals {
  transform_lambda_arns = {
    logs       = aws_lambda_function.log_transform.arn
    cloudtrail = aws_lambda_function.cloudtrail_transform.arn
  }
}

resource "aws_kinesis_firehose_delivery_stream" "this" {
  for_each = local.firehose_streams

  name        = each.value.name
  destination = "extended_s3"

  server_side_encryption {
    enabled  = true
    key_type = "CUSTOMER_MANAGED_CMK"
    key_arn  = aws_kms_key.observability.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.data_lake.arn
    prefix              = each.value.prefix
    error_output_prefix = each.value.error_prefix
    buffering_size      = 1
    buffering_interval  = 60
    compression_format  = "GZIP"

    processing_configuration {
      enabled = true
      processors {
        type = "Lambda"
        parameters {
          parameter_name  = "LambdaArn"
          parameter_value = local.transform_lambda_arns[each.value.transform]
        }
      }
    }
  }

  depends_on = [aws_iam_role_policy.firehose, aws_s3_bucket_policy.data_lake]
}

resource "aws_cloudwatch_log_subscription_filter" "quick" {
  for_each = { for key, value in local.firehose_streams : key => value if key != "cloudtrail" }

  name            = "${var.resource_prefix}-${replace(each.key, "_", "-")}-to-firehose"
  log_group_name  = each.value.log_group_name
  filter_pattern  = ""
  destination_arn = aws_kinesis_firehose_delivery_stream.this[each.key].arn
  role_arn        = aws_iam_role.cloudwatch_logs.arn

  depends_on = [aws_cloudwatch_log_delivery.quick, aws_iam_role_policy.cloudwatch_logs]
}
