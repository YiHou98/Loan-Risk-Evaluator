# listApplications.py
from typing import Dict, Any, List, Tuple, Optional
from aws_lambda_powertools import Logger, Tracer
from db_connection import get_aurora_connection
from datetime import datetime, timezone, date, time
from decimal import Decimal
from utils import execute_query, execute_scalar, check_unsafe_params

logger = Logger(service="ListApplications")
tracer = Tracer(service="ListApplications")

# Constants
ALLOWED_SORT_COLUMNS = ["application_id", "loan_amnt", "int_rate", "risk_score", "processing_timestamp"]
DEFAULT_LIMIT = 1000

@tracer.capture_method
def process(action: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """List applications with filters and pagination"""
    
    # Check for unsafe parameters
    if check_unsafe_params(body):
        return {"statusCode": 500, "body": "Invalid characters in query parameters"}
    
    conn = None
    try:
        # Get database connection
        conn = get_aurora_connection()
        
        # Extract required date filters
        start_date_str = body.get('startDate')
        end_date_str = body.get('endDate')
        
        if not start_date_str or not end_date_str:
            raise ValueError("startDate and endDate are required")
        
        # Parse dates
        try:
            start_dt = datetime.combine(date.fromisoformat(start_date_str), time.min, tzinfo=timezone.utc)
            end_dt = datetime.combine(date.fromisoformat(end_date_str), time.max, tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"Invalid date format: {start_date_str}, {end_date_str}")
            raise ValueError("Invalid date format. Please use YYYY-MM-DD.")
        
        # Extract optional filters
        risk_level = body.get('riskLevel')
        address_state = body.get('addressState')
        
        # Extract pagination params
        limit = body.get('limit', DEFAULT_LIMIT)
        offset = body.get('offset', 0)
        
        # Validate limit and offset
        try:
            limit = int(limit)
            offset = int(offset)
            offset = max(0, offset)  # Must be non-negative
        except (ValueError, TypeError):
            limit = DEFAULT_LIMIT
            offset = 0
        
        # Extract and validate sort params
        sort_by = body.get('sortBy', 'processing_timestamp')
        sort_order = body.get('sortOrder', 'desc')
        
        # Validate sort column
        if sort_by not in ALLOWED_SORT_COLUMNS:
            sort_by = 'processing_timestamp'
        
        # Validate sort order
        sort_order = sort_order.lower() if isinstance(sort_order, str) else 'desc'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'
        
        # Build WHERE clause and params
        where_conditions = ["processing_timestamp >= %s", "processing_timestamp <= %s"]
        params = [start_dt, end_dt]
        
        # Add optional filters
        if risk_level:
            where_conditions.append("risk_level = %s")
            params.append(risk_level)
        
        if address_state:
            where_conditions.append("addr_state = %s")
            params.append(address_state)
        
        where_sql = "WHERE " + " AND ".join(where_conditions)
        
        logger.info(f"Querying applications with filters: dates={start_date_str} to {end_date_str}, "
                   f"risk_level={risk_level}, state={address_state}, "
                   f"limit={limit}, offset={offset}, sort={sort_by} {sort_order}")
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM scored_loan_applications {where_sql}"
        total_count = execute_scalar(conn, count_query, params)
        
        # Get paginated data
        data_query = f"""
            SELECT 
                application_id,
                message_id,
                loan_amnt,
                term,
                int_rate,
                installment,
                emp_length,
                annual_inc,
                dti,
                addr_state,
                credit_to_income_ratio,
                is_self_employed,
                loan_month,
                is_long_term,
                risk_score,
                risk_level,
                processing_timestamp
            FROM scored_loan_applications
            {where_sql}
            ORDER BY {sort_by} {sort_order}
            LIMIT %s OFFSET %s
        """
        
        # Add limit and offset to params
        query_params = params + [limit, offset]
        
        # Execute query
        records = execute_query(conn, data_query, query_params)
        
        # Map records to response format
        applications = []
        for record in records:
            app = {
                "applicationId": record[0],
                "messageId": record[1],
                "loanAmount": float(record[2]) if record[2] is not None else None,
                "term": record[3],
                "interestRate": float(record[4]) if record[4] is not None else None,
                "installment": float(record[5]) if record[5] is not None else None,
                "employmentLength": record[6],
                "annualIncome": float(record[7]) if record[7] is not None else None,
                "dti": float(record[8]) if record[8] is not None else None,
                "addressState": record[9],
                "creditToIncomeRatio": float(record[10]) if record[10] is not None else None,
                "isSelfEmployed": record[11],
                "loanMonth": record[12],
                "isLongTerm": record[13],
                "riskScore": float(record[14]) if record[14] is not None else None,
                "riskLevel": record[15],
                "processingTimestamp": record[16].isoformat() if record[16] else None
            }
            applications.append(app)
        
        
        return {
            "totalCount": total_count,
            "limit": limit,
            "offset": offset,
            "applications": applications
        }
        
    except ValueError as ve:
        logger.error(f"ValueError: {str(ve)}")
        return {
            "statusCode": 400,
            "body": str(ve)
        }
    except Exception as e:
        logger.exception("Error querying applications")
        return {
            "statusCode": 500,
            "body": f"Database error: {str(e)}"
        }
    finally:
        if conn:
            conn.close()