locals {
  lambda_log_groups = {
    log_transform           = "/aws/lambda/${local.pipeline_name}-LogTransform"
    cloudtrail_transform    = "/aws/lambda/${local.pipeline_name}-CloudTrailTransform"
    licensed_users_snapshot = "/aws/lambda/${local.pipeline_name}-LicensedUsersSnapshot"
    provisioner             = "/aws/lambda/${var.resource_prefix}-TerraformProvisioner"
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.lambda_log_groups

  name              = each.value
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.observability.arn
}

data "archive_file" "log_transform" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/log_transform"
  output_path = "${path.module}/log_transform.zip"
}

data "archive_file" "cloudtrail_transform" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/cloudtrail_transform"
  output_path = "${path.module}/cloudtrail_transform.zip"
}

data "archive_file" "licensed_users_snapshot" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/licensed_users_snapshot"
  output_path = "${path.module}/licensed_users_snapshot.zip"
}

data "archive_file" "provisioner" {
  type        = "zip"
  output_path = "${path.module}/provisioner.zip"

  source {
    content  = file("${path.module}/lambda/provisioner/index.py")
    filename = "index.py"
  }

  source {
    content  = file("${path.module}/lambda/provisioner/dashboard_definition.py")
    filename = "dashboard_definition.py"
  }

  dynamic "source" {
    for_each = fileset("${path.module}/../sql", "*.sql")
    content {
      content  = file("${path.module}/../sql/${source.value}")
      filename = "sql/${source.value}"
    }
  }
}

resource "aws_lambda_function" "log_transform" {
  function_name    = "${local.pipeline_name}-LogTransform"
  filename         = data.archive_file.log_transform.output_path
  source_code_hash = data.archive_file.log_transform.output_base64sha256
  role             = aws_iam_role.transform_lambda.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 300
  kms_key_arn      = aws_kms_key.observability.arn

  environment {
    variables = {
      INCLUDE_MESSAGE_CONTENT = tostring(var.include_message_content)
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.transform_lambda]
}

resource "aws_lambda_function" "cloudtrail_transform" {
  function_name    = "${local.pipeline_name}-CloudTrailTransform"
  filename         = data.archive_file.cloudtrail_transform.output_path
  source_code_hash = data.archive_file.cloudtrail_transform.output_base64sha256
  role             = aws_iam_role.transform_lambda.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 300
  kms_key_arn      = aws_kms_key.observability.arn

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.transform_lambda]
}

resource "aws_lambda_function" "licensed_users_snapshot" {
  function_name    = "${local.pipeline_name}-LicensedUsersSnapshot"
  filename         = data.archive_file.licensed_users_snapshot.output_path
  source_code_hash = data.archive_file.licensed_users_snapshot.output_base64sha256
  role             = aws_iam_role.licensed_users_snapshot.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 300
  kms_key_arn      = aws_kms_key.observability.arn

  environment {
    variables = {
      AWS_ACCOUNT_ID       = local.account_id
      DATA_LAKE_BUCKET     = aws_s3_bucket.data_lake.id
      QUICKSIGHT_NAMESPACE = var.quicksight_namespace
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.licensed_users_snapshot]
}

resource "aws_lambda_function" "provisioner" {
  function_name    = "${var.resource_prefix}-TerraformProvisioner"
  filename         = data.archive_file.provisioner.output_path
  source_code_hash = data.archive_file.provisioner.output_base64sha256
  role             = aws_iam_role.provisioner.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 900
  kms_key_arn      = aws_kms_key.observability.arn

  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.provisioner]
}

resource "aws_lambda_permission" "provisioner_cloudformation" {
  statement_id   = "AllowCloudFormationCustomResource"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.provisioner.function_name
  principal      = "cloudformation.amazonaws.com"
  source_account = local.account_id
}
