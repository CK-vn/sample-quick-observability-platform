data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "firehose_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "logs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["logs.${var.aws_region}.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "transform_lambda" {
  name               = "${local.pipeline_name}-Lambda-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "transform_lambda" {
  role = aws_iam_role.transform_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "${aws_cloudwatch_log_group.lambda["log_transform"].arn}:*",
          "${aws_cloudwatch_log_group.lambda["cloudtrail_transform"].arn}:*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
    ]
  })
}

resource "aws_iam_role" "firehose" {
  name               = "${local.pipeline_name}-Firehose-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume.json
}

resource "aws_iam_role_policy" "firehose" {
  role = aws_iam_role.firehose.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = aws_s3_bucket.data_lake.arn
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = [
          "${aws_s3_bucket.data_lake.arn}/cloudwatch-logs/*",
          "${aws_s3_bucket.data_lake.arn}/cloudtrail/*",
          "${aws_s3_bucket.data_lake.arn}/errors/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
      {
        Effect = "Allow"
        Action = ["lambda:GetFunctionConfiguration", "lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.log_transform.arn,
          "${aws_lambda_function.log_transform.arn}:*",
          aws_lambda_function.cloudtrail_transform.arn,
          "${aws_lambda_function.cloudtrail_transform.arn}:*",
        ]
      },
    ]
  })
}

resource "aws_iam_role" "cloudwatch_logs" {
  name               = "${local.pipeline_name}-CloudWatchLogs-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.logs_assume.json
}

resource "aws_iam_role_policy" "cloudwatch_logs" {
  role = aws_iam_role.cloudwatch_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
        Resource = [for key, stream in aws_kinesis_firehose_delivery_stream.this : stream.arn if key != "cloudtrail"]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
    ]
  })
}

resource "aws_iam_role" "eventbridge" {
  name               = "${local.pipeline_name}-EventBridge-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}

resource "aws_iam_role_policy" "eventbridge" {
  role = aws_iam_role.eventbridge.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
      Resource = aws_kinesis_firehose_delivery_stream.this["cloudtrail"].arn
    }]
  })
}

resource "aws_iam_role" "licensed_users_snapshot" {
  name               = "${local.pipeline_name}-LicensedUsersSnapshot-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "licensed_users_snapshot" {
  role = aws_iam_role.licensed_users_snapshot.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda["licensed_users_snapshot"].arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["quicksight:ListUsers"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.data_lake.arn}/licensed-users-snapshot/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
    ]
  })
}

resource "aws_iam_role" "provisioner" {
  name               = "${var.resource_prefix}-TerraformProvisioner-${var.aws_region}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "provisioner" {
  role = aws_iam_role.provisioner.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda["provisioner"].arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:DeleteParameter", "ssm:GetParameter", "ssm:PutParameter"]
        Resource = "arn:${local.partition}:ssm:${var.aws_region}:${local.account_id}:parameter/quick-observability/*"
      },
      {
        Effect = "Allow"
        Action = [
          "athena:GetQueryExecution", "athena:StartQueryExecution", "athena:StopQueryExecution",
        ]
        Resource = aws_athena_workgroup.observability.arn
      },
      {
        Effect = "Allow"
        Action = [
          "glue:CreateDatabase", "glue:DeleteDatabase", "glue:GetDatabase", "glue:GetDatabases",
          "glue:CreateTable", "glue:DeleteTable", "glue:GetTable", "glue:GetTables", "glue:UpdateTable",
          "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition", "glue:GetTableVersion", "glue:GetTableVersions",
        ]
        Resource = [
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:catalog",
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:database/${local.database_name}",
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:table/${local.database_name}/*",
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:userDefinedFunction/${local.database_name}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = [aws_s3_bucket.data_lake.arn, aws_s3_bucket.athena_results.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.data_lake.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.athena_results.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
      {
        Effect = "Allow"
        Action = [
          "quicksight:CreateAnalysis", "quicksight:DeleteAnalysis", "quicksight:DescribeAnalysis",
          "quicksight:RestoreAnalysis", "quicksight:UpdateAnalysis", "quicksight:UpdateAnalysisPermissions",
          "quicksight:CreateDashboard", "quicksight:DeleteDashboard", "quicksight:DescribeDashboard",
          "quicksight:UpdateDashboard", "quicksight:UpdateDashboardPermissions",
          "quicksight:CreateDataSet", "quicksight:DeleteDataSet", "quicksight:DescribeDataSet",
          "quicksight:UpdateDataSet", "quicksight:UpdateDataSetPermissions",
          "quicksight:CreateDataSource", "quicksight:DeleteDataSource", "quicksight:DescribeDataSource",
          "quicksight:UpdateDataSource", "quicksight:UpdateDataSourcePermissions",
          "quicksight:CreateRefreshSchedule", "quicksight:DeleteRefreshSchedule",
          "quicksight:DescribeRefreshSchedule", "quicksight:UpdateRefreshSchedule",
          "quicksight:DescribeIngestion", "quicksight:ListIngestions",
          "quicksight:CreateTheme", "quicksight:DeleteTheme", "quicksight:DescribeTheme",
          "quicksight:UpdateTheme", "quicksight:UpdateThemePermissions",
          "quicksight:CreateTopic", "quicksight:DeleteTopic", "quicksight:DescribeTopic",
          "quicksight:UpdateTopic", "quicksight:UpdateTopicPermissions",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "quicksight:PassDataSource"
        Resource = "arn:${local.partition}:quicksight:${var.aws_region}:${local.account_id}:datasource/${var.resource_prefix}-athena-source"
      },
      {
        Effect   = "Allow"
        Action   = "quicksight:PassDataSet"
        Resource = "arn:${local.partition}:quicksight:${var.aws_region}:${local.account_id}:dataset/${var.resource_prefix}-*"
      },
      {
        Effect   = "Allow"
        Action   = "quicksight:PassTheme"
        Resource = "arn:${local.partition}:quicksight:${var.aws_region}:${local.account_id}:theme/${var.resource_prefix}-observability-theme"
      },
    ]
  })
}

resource "aws_iam_role_policy" "quicksight_observability" {
  name = "${var.resource_prefix}-observability-access"
  role = "aws-quicksight-service-role-v0"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:GetDataCatalog",
          "athena:GetDatabase",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetTableMetadata",
          "athena:GetWorkGroup",
          "athena:ListDataCatalogs",
          "athena:ListDatabases",
          "athena:ListTableMetadata",
          "athena:ListWorkGroups",
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:BatchGetPartition",
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetTableVersion",
          "glue:GetTableVersions",
        ]
        Resource = [
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:catalog",
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:database/${local.database_name}",
          "arn:${local.partition}:glue:${var.aws_region}:${local.account_id}:table/${local.database_name}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = [aws_s3_bucket.data_lake.arn, aws_s3_bucket.athena_results.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.data_lake.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.athena_results.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.observability.arn
      },
    ]
  })
}
