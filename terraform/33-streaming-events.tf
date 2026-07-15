resource "aws_cloudwatch_event_rule" "quicksight_cloudtrail" {
  name        = "${local.pipeline_name}-CloudTrailEvents"
  description = "Capture Amazon QuickSight API calls and service events from CloudTrail"
  event_pattern = jsonencode({
    source      = ["aws.quicksight"]
    detail-type = ["AWS API Call via CloudTrail", "AWS Service Event via CloudTrail"]
  })
}

resource "aws_cloudwatch_event_target" "quicksight_cloudtrail" {
  rule     = aws_cloudwatch_event_rule.quicksight_cloudtrail.name
  arn      = aws_kinesis_firehose_delivery_stream.this["cloudtrail"].arn
  role_arn = aws_iam_role.eventbridge.arn

  depends_on = [aws_iam_role_policy.eventbridge]
}

resource "aws_cloudwatch_event_rule" "licensed_users_snapshot" {
  name                = "${local.pipeline_name}-LicensedUsersSnapshotSchedule"
  description         = "Hourly schedule at :55 to snapshot QuickSight licensed users"
  schedule_expression = "cron(55 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "licensed_users_snapshot" {
  rule = aws_cloudwatch_event_rule.licensed_users_snapshot.name
  arn  = aws_lambda_function.licensed_users_snapshot.arn
}

resource "aws_lambda_permission" "licensed_users_snapshot_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.licensed_users_snapshot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.licensed_users_snapshot.arn
}
