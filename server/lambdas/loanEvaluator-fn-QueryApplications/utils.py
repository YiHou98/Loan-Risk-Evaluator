# utils.py
import re
from datetime import datetime, timedelta, timezone # Ensure all three are imported
from decimal import Decimal
from typing import Dict, Any, List, Tuple, Optional, Union
from collections.abc import ValuesView 
from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="Utils")
tracer = Tracer(service="Utils")

# --- Constants ---
ALLOWED_SORT_COLUMNS = [
    "application_id", "loan_amnt", "int_rate", "risk_score", "processing_timestamp"
]

# --- Security & Validation Utilities ---
@tracer.capture_method
def check_unsafe_params(parameter_to_check: Any) -> bool:
    if isinstance(parameter_to_check, str):
        if re.search(r"[;'\\ ]", parameter_to_check): 
            logger.warning(f"Unsafe parameter detected in string: {parameter_to_check}")
            return True
    elif isinstance(parameter_to_check, dict):
        for value in parameter_to_check.values():
            if check_unsafe_params(value): return True
    elif isinstance(parameter_to_check, (list, tuple, ValuesView, set)):
        for item in parameter_to_check:
            if check_unsafe_params(item): return True
    return False

# --- Date Utilities ---
def _parse_date_to_datetime(date_str: Optional[str], is_end_date: bool = False) -> Optional[datetime]:
    if not date_str: return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
        )
        if is_end_date: dt += timedelta(days=1)
        return dt
    except ValueError:
        logger.warning(f"Invalid date string format: {date_str}. Expected YYYY-MM-DD.")
        return None

# --- Database Execution Utilities (keep as previously refined) ---
@tracer.capture_method
def execute_query(conn, query: str, params: List[Any] = None) -> List[Tuple]:
    with conn.cursor() as cursor:
        try:
            # Safe logging of query and params
            log_query = query
            if hasattr(cursor, 'mogrify'):
                try: log_query = cursor.mogrify(query, params or []).decode()
                except: pass # Mogrify can fail if connection is bad

            cursor.execute(query, params or [])
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to execute query. Error: {e}")
            raise

@tracer.capture_method
def execute_scalar(conn, query: str, params: List[Any] = None) -> Any:
    with conn.cursor() as cursor:
        try:
            log_query = query
            if hasattr(cursor, 'mogrify'):
                try: log_query = cursor.mogrify(query, params or []).decode()
                except: pass
            logger.debug(f"Executing scalar query: {log_query}")
            cursor.execute(query, params or [])
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to execute scalar query. Error: {e}")
            logger.error(f"Query (template): {query}, Params Count: {len(params or [])}")
            raise