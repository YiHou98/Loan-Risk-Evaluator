import json

def lambda_handler(event, context):
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
import json
from datetime import datetime, timezone

import psycopg2 # type: ignore
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from db_connection import get_aurora_connection  # Connection helper

logger = Logger(service="PersistenceLambda")
tracer = Tracer(service="PersistenceLambda")

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext):
    logger.info("PersistScoredApplicationLambda invoked.")

    # Extract and validate inputs
    cleaned_data       = event.get('features_for_scoring', {})
    risk_score_obj     = event.get('risk_score', {})
    application_id = event.get('application_id')
    message_id = event.get('message_id')


    if not risk_score_obj or 'risk_score' not in risk_score_obj:
        logger.error("Risk score missing.")
        raise ValueError("Risk score is missing and required for persistence.")

    risk_score_value = risk_score_obj['risk_score']

    # SQL statement (INSERT ... ON CONFLICT)
    sql = """
    INSERT INTO scored_loan_applications (
        application_id, message_id, loan_amnt, term, int_rate, installment, emp_length,
        annual_inc, dti, addr_state,
        credit_to_income_ratio, is_self_employed, loan_month, is_long_term,
        risk_score, processing_timestamp
    ) VALUES (
        %(app_id)s, %(msg_id)s, %(loan_amnt)s, %(term)s, %(int_rate)s, %(installment)s, %(emp_length)s,
        %(annual_inc)s, %(dti)s, %(addr_state)s,
        %(cred_to_inc)s, %(is_self_emp)s, %(loan_month)s, %(is_long_term)s,
        %(risk_score)s, %(proc_ts)s
    )
    ON CONFLICT (application_id) DO UPDATE SET
        message_id = EXCLUDED.message_id, 
        loan_amnt = EXCLUDED.loan_amnt,
        term = EXCLUDED.term,
        int_rate = EXCLUDED.int_rate,
        installment = EXCLUDED.installment,
        emp_length = EXCLUDED.emp_length,
        annual_inc = EXCLUDED.annual_inc,
        dti = EXCLUDED.dti,
        addr_state = EXCLUDED.addr_state,
        credit_to_income_ratio = EXCLUDED.credit_to_income_ratio,
        is_self_employed = EXCLUDED.is_self_employed,
        loan_month = EXCLUDED.loan_month,
        is_long_term = EXCLUDED.is_long_term,
        risk_score = EXCLUDED.risk_score,
        processing_timestamp = EXCLUDED.processing_timestamp;
    """

    # Build parameter dictionary
    params = {
        "app_id": application_id,
        "msg_id": message_id,
        "loan_amnt": cleaned_data.get('loan_amnt'),
        "term": cleaned_data.get('term'),
        "int_rate": cleaned_data.get('int_rate'),
        "installment": cleaned_data.get('installment'),
        "emp_length": cleaned_data.get('emp_length'),
        "annual_inc": cleaned_data.get('annual_inc'),
        "dti": cleaned_data.get('dti'),
        "addr_state": cleaned_data.get('addr_state'),
        "cred_to_inc": cleaned_data.get('credit_to_income_ratio'),
        "is_self_emp": cleaned_data.get('is_self_employed'),
        "loan_month": cleaned_data.get('loan_month'),
        "is_long_term": cleaned_data.get('is_long_term'),
        "risk_score": risk_score_value,
        "proc_ts": datetime.now(timezone.utc).isoformat(),
    }

    conn = None
    try:
        # Acquire (or reuse) a connection
        conn = get_aurora_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        logger.info("Successfully persisted application to DB.", extra={"application_id": application_id})
        return {"application_id": application_id, "persistence_status": "SUCCESS"}

    except Exception as e:
        # Determine if this was a psycopg2‐specific error
        is_db_error = isinstance(e, psycopg2.Error)
        if is_db_error:
            log_msg = "Database error during persistence."
            wrapped_msg = f"DatabaseWriteError: {str(e)}"
        else:
            log_msg = "Unexpected error during persistence."
            wrapped_msg = None  # We’ll re‐raise the original exception below

        # Log with context
        logger.exception(log_msg, extra={"application_id": application_id, "error": str(e)})

        # Attempt rollback if the connection is open
        if conn is not None and not getattr(conn, "closed", True):
            try:
                conn.rollback()
            except psycopg2.Error as rb_err:
                logger.error(f"Rollback failed: {rb_err}")

        # Re‐raise either as a DatabaseWriteError or simply propagate
        if is_db_error:
            raise Exception(wrapped_msg)
        else:
            raise
