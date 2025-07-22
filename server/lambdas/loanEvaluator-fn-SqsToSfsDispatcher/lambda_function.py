import json
import boto3
import os
from datetime import datetime
import uuid 

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# ─── Idempotency imports ───────────────────────────────────────────────────────
from aws_lambda_powertools.utilities.idempotency import (
    IdempotencyConfig,
    DynamoDBPersistenceLayer,
    idempotent_function,
)
# ────────────────────────────────────────────────────────────────────────────────

from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord

# --- Powertools Configuration ---
logger = Logger(service="SqsToStepDispatcher")
# logger = Logger(service="SqsToStepDispatcher", level="DEBUG")
tracer = Tracer(service="SqsToStepDispatcher")
processor = BatchProcessor(event_type=EventType.SQS)

try:
    STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
    IDEMPOTENCY_TABLE_NAME_DISPATCHER = os.environ["IDEMPOTENCY_DISPATCHER_DYNAMODB"]
except KeyError as e:
    logger.critical("Configuration error on Lambda load.", extra={"error": str(e)})
    raise

# --- AWS Clients ---
stepfunctions_client = boto3.client("stepfunctions")

# --- Idempotency Configuration for Dispatcher ---
idempotency_config = IdempotencyConfig(
    event_key_jmespath="messageId",  # Uses SQSRecord.message_id
    expires_after_seconds=60 * 60 * 1,  # Keep idempotency records for 1 hour
)

idempotency_persistence_layer = DynamoDBPersistenceLayer(
    table_name=IDEMPOTENCY_TABLE_NAME_DISPATCHER
)

@tracer.capture_method
@idempotent_function(
    data_keyword_argument="record",
    config=idempotency_config,
    persistence_store=idempotency_persistence_layer,
)
def start_step_function_for_message(record: SQSRecord, context: LambdaContext):
    message_id = record.message_id
    message_body_str = record.body

    if not message_body_str:
        logger.warning(
            "SQS message body is empty. Skipping Step Function start.",
            extra={"messageId": message_id},
        )
        return {"messageId": message_id, "status": "SKIPPED_EMPTY_BODY"}

    try:
        payload = json.loads(message_body_str)
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to decode JSON from SQS message body.",
            extra={
                "messageId": message_id,
                "bodyPreview": message_body_str[:200],
                "error": str(e),
            },
        )
        raise ValueError(f"Invalid JSON in SQS message body for ID: {message_id}") from e

    # If producer wrapped it correctly, use the nested object. Otherwise, treat
    # the entire payload as the loanApplication payload.
    if "loanApplication" in payload and isinstance(payload["loanApplication"], dict):
        application_data = payload["loanApplication"]
    elif isinstance(payload, dict):
        # Assume flat JSON is already the loan object
        application_data = payload
    else:
        logger.error(
            "Missing or invalid 'loanApplication' field in SQS body.",
            extra={
                "messageId": message_id,
                "parsedSqsBodyPreview": str(payload)[:200],
            },
        )
        raise ValueError(
            f"Missing or invalid 'loanApplication' in SQS message body for ID: {message_id}"
        )

    # Build a unique execution name
    generated_id = str(uuid.uuid4())

    step_function_input = {
        "sqsMessageAttributes": {
            "messageId": message_id,
            "receiptHandle": record.receipt_handle,
            "approximateReceiveCount": record.attributes.get("ApproximateReceiveCount"),
        },
        "loanApplication": application_data,
        "application_id": generated_id,
    }

    try:
        response = stepfunctions_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"loanRiskRun-{generated_id}",
            input=json.dumps(step_function_input),
        )
        logger.info(
            "Successfully started Step Function execution.",
            extra={"executionArn": response["executionArn"], "app_id": generated_id, "messageId": message_id},
        )
        return {"messageId": message_id, "app_id": generated_id, "executionArn": response["executionArn"], "status": "SUCCESS"}
    except Exception as e_sfn:
        logger.exception(
            "Error starting Step Function execution.",
            extra={
                "messageId": message_id,
                "error": str(e_sfn),
            },
        )
        raise

@logger.inject_lambda_context()
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    idempotency_config.register_lambda_context(context)
    # IMPORTANT: Pass raw event dict. BatchProcessor will detect SQS internally.
    return process_partial_response(
        event=event,
        # NOTE: now passing both record and context as keyword arguments
        record_handler=lambda record: start_step_function_for_message(record=record, context=context),
        processor=processor,
        context=context
    )
