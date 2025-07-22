import os
import json
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import all needed functions at once
from utils import (
    robust_float_parse, parse_term, parse_percentage,
    parse_emp_length, parse_state_code, is_self_employed_from_title,
    get_month_from_issue_date
)

logger = Logger(service="CleanFeatureEngineerLambda")
tracer = Tracer(service="CleanFeatureEngineerLambda")

# Field configuration for batch processing
FIELD_CONFIGS = {
    'loan_amnt': {'parser': robust_float_parse, 'default': 0.0},
    'term': {'parser': parse_term, 'default': 36},
    'int_rate': {'parser': parse_percentage, 'default': 0.0},
    'installment': {'parser': robust_float_parse, 'default': 0.0},
    'emp_length': {'parser': parse_emp_length, 'default': 0},
    'annual_inc': {'parser': robust_float_parse, 'default': 0.0},
    'dti': {'parser': parse_percentage, 'default': 0.0},
}

s3_client = boto3.client("s3")
S3_BUCKET = os.environ.get("S3_BUCKET")

def _parse_field(raw_value, parser_func, field_name, default_value):
    """Generic field parser with logging."""
    if raw_value is None:
        return default_value
    
    parsed = parser_func(raw_value)
    
    if parsed is None:
        logger.warning(
            f"{field_name} parsing of '{raw_value}' failed, using default {default_value}",
            extra={"field": field_name, "raw_value": raw_value, "default": default_value}
        )
        return default_value
    
    return parsed

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    """
    Clean and prepare loan application data for ML scoring.
    """
    # Validate input
    application_id = event.get("application_id")
    if not application_id:
        logger.error("Missing 'application_id' in event")
        raise ValueError("Event must include 'application_id'")

    raw_application = event.get('loanApplication')
    if not isinstance(raw_application, dict) or not raw_application:
        logger.error("Input 'loanApplication' is missing, not a dictionary, or empty.")
        raise ValueError("Input 'loanApplication' is missing, not a dictionary, or empty.")
    
    sqs_attrs = event.get("sqsMessageAttributes", {})
    message_id = sqs_attrs.get("messageId")
    if not message_id:
        logger.error("Missing 'messageId' in sqsMessageAttributes")
        raise ValueError("Event must include 'sqsMessageAttributes.messageId'")
    
    s3_key = f"applications/{application_id}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(raw_application).encode("utf-8"),
            ContentType="application/json"
        )
    except Exception as e:
        logger.exception("Failed to upload original_application to S3")
        # If S3 upload fails, we stop processing rather than proceed without storing the raw payload.
        raise

    try:
        # Process all standard fields
        cleaned_data = {}
        
        for field_name, config in FIELD_CONFIGS.items():
            raw_value = raw_application.get(field_name)
            cleaned_data[field_name] = _parse_field(
                raw_value,
                config['parser'],
                field_name,
                config['default']
            )
        
        # Special validations
        
        # Ensure loan amount is non-negative
        if cleaned_data['loan_amnt'] < 0:
            logger.warning(f"Negative loan amount {cleaned_data['loan_amnt']}, setting to 0.0")
            cleaned_data['loan_amnt'] = 0.0
        
        # Ensure annual income is positive for ratio calculations
        if cleaned_data['annual_inc'] <= 0:
            logger.info(
                f"annual_inc was {cleaned_data['annual_inc']}, setting to 1.0 for ratio calculation",
                extra={"original_annual_inc": cleaned_data['annual_inc']}
            )
            cleaned_data['annual_inc'] = 1.0

        if cleaned_data.get('int_rate') is not None:
            cleaned_data['int_rate'] = round(cleaned_data['int_rate'], 4)
        if cleaned_data.get('dti') is not None:
            cleaned_data['dti'] = round(cleaned_data['dti'], 4)   
        # Parse state code
        cleaned_data['addr_state'] = parse_state_code(
            raw_application.get('addr_state'),
            default_code='XX'
        )
        
        # Compute derived features
        computed_features = {}
        
        # Credit to income ratio
        if cleaned_data['annual_inc'] > 0: # Ensure annual_inc is positive
            ratio = cleaned_data['loan_amnt'] / cleaned_data['annual_inc']
            computed_features['credit_to_income_ratio'] = round(ratio, 4)
        else:
            computed_features['credit_to_income_ratio'] = 0.0
        
        # Self-employment flag
        computed_features['is_self_employed'] = is_self_employed_from_title(
            raw_application.get('emp_title')
        )
        
        # Loan month
        raw_issue_d = raw_application.get('issue_d')
        parsed_month = get_month_from_issue_date(raw_issue_d)
        
        if parsed_month is None and raw_issue_d is not None:
            logger.warning(
                f"issue_d parsing of '{raw_issue_d}' failed, using default 0",
                extra={"raw_issue_d": raw_issue_d}
            )
        
        computed_features['loan_month'] = parsed_month if parsed_month is not None else 0
        
        # Long-term loan flag
        computed_features['is_long_term'] = (cleaned_data['term'] >= 36)
        
        # Note: FICO features commented out as not in sample data
        # If FICO data becomes available, uncomment and add to FIELD_CONFIGS:
        # 'fico_range_low': {'parser': robust_float_parse, 'default': 300.0},
        # 'fico_range_high': {'parser': robust_float_parse, 'default': 300.0},
        # And compute: computed_features['fico_avg'] = (low + high) / 2.0
        
        # Prepare output
        features_for_scoring = {
            **cleaned_data,
            **computed_features
        }
        
        output = {
            'message_id': message_id,
            'application_id': application_id,
            'features_for_scoring': features_for_scoring
        }
        
        logger.info(
            "Data cleaning and feature engineering complete",
            extra={
                "application_id": application_id,
                "messageId": message_id,
            }
        )
        
        return output
        
    except Exception as e:
        logger.exception("Error during data cleaning and feature engineering")
        raise