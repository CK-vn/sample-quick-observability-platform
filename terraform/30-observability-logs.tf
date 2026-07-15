resource "aws_cloudwatch_log_group" "vended" {
  for_each = var.log_group_names

  name              = each.value
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.observability.arn
}

resource "aws_cloudwatch_log_delivery_source" "quick" {
  for_each = local.vended_logs

  name         = each.value.source_name
  log_type     = each.value.log_type
  resource_arn = local.quicksight_account_arn
}

resource "aws_cloudwatch_log_delivery_destination" "quick" {
  for_each = local.vended_logs

  name          = each.value.destination_name
  output_format = "json"
  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.vended[each.key].arn
  }
}

resource "aws_cloudwatch_log_delivery" "quick" {
  for_each = local.vended_logs

  delivery_source_name     = aws_cloudwatch_log_delivery_source.quick[each.key].name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.quick[each.key].arn
  record_fields            = each.value.record_fields
}
