# Log Transform Lambda Function

## Overview

This Lambda function transforms CloudWatch Logs data from Kinesis Firehose into a structured JSON Lines format suitable for storage in S3 and querying with Athena.

## Functionality

- Decodes and decompresses CloudWatch Logs subscription filter payloads (base64 + gzip)
- Parses JSON log records from CloudWatch Logs `logEvents`
- Drops `CONTROL_MESSAGE` records (health checks sent by CloudWatch Logs)
- Extracts the event timestamp from the message payload's `event_timestamp` field (handles both millisecond and second formats), falling back to the CloudWatch log event envelope timestamp
- Maps field names (e.g., `accountId` → `account_id`, `logType` → `message_type`). INDEX_USAGE_LOGS uses snake_case natively (`log_type`, `account_id`), so both camelCase and snake_case conventions are handled.
- Strips sensitive message content fields (`user_message`, `system_text_message`) when `INCLUDE_MESSAGE_CONTENT` is `false`
- Serializes nested objects/lists as JSON strings
- Returns transformed records to Firehose in JSON Lines format

## Handler

- **File**: `index.py`
- **Function**: `lambda_handler(event, context)`
- **Runtime**: Python 3.14
- **Timeout**: 300 seconds
- **Memory**: 512 MB

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INCLUDE_MESSAGE_CONTENT` | Whether to keep user_message and system_text_message | `false` |

## Input Format

Kinesis Firehose transformation event with CloudWatch Logs subscription filter records (base64-encoded, gzip-compressed):

```json
{
  "records": [
    {
      "recordId": "...",
      "data": "base64-encoded-gzipped-log-data"
    }
  ]
}
```

## Output Format

Transformed records in JSON Lines format (one JSON object per line, base64-encoded):

```json
{
  "recordId": "...",
  "result": "Ok",
  "data": "base64-encoded-json-line"
}
```

Possible result values: `Ok` (transformed successfully), `Dropped` (control message or empty batch), `ProcessingFailed` (error during transformation).

## Deployment

Terraform packages and deploys this function from `lambda/log_transform/` as a Python 3.12 Lambda. Configure message retention through the `include_message_content` Terraform variable.

## Monitoring

- **CloudWatch Logs**: `/aws/lambda/{stack-name}-LogTransform`
- **Metrics**: Invocations, Duration, Errors, Throttles

## Troubleshooting

### Common Issues

1. **Parsing Errors**: Check log format matches expected structure
2. **Timeout**: Increase timeout or reduce Firehose batch size
3. **Memory**: Increase memory allocation if processing large batches

## Related Resources

- [Kinesis Firehose Data Transformation](https://docs.aws.amazon.com/firehose/latest/dev/data-transformation.html)
- [Lambda Performance Optimization](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
