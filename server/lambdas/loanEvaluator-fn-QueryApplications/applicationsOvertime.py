# applicationsOverTime_simplified.py
from typing import Dict, Any, List, Tuple
from aws_lambda_powertools import Logger, Tracer
from db_connection import get_aurora_connection
from datetime import datetime, timezone, date, time
from utils import execute_query, check_unsafe_params  # Import specific functions instead of *

logger = Logger(service="ApplicationsOverTimeSimplified")
tracer = Tracer(service="ApplicationsOverTimeSimplified")

@tracer.capture_method
def process(action: str, body: Dict[str, Any]) -> List[Dict[str, Any]]:

    conn = None
    try:
        conn = get_aurora_connection()
        
        start_date_str = body.get('startDate')
        end_date_str = body.get('endDate')

        if not start_date_str or not end_date_str:
            raise ValueError("startDate and endDate are required for applicationsOverTime.")

        try:
            start_dt = datetime.combine(date.fromisoformat(start_date_str), time.min, tzinfo=timezone.utc)
            end_dt = datetime.combine(date.fromisoformat(end_date_str), time.max, tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"Invalid date format for startDate or endDate: {start_date_str}, {end_date_str}")
            raise ValueError("Invalid date format. Please use YYYY-MM-DD.")

        params = [start_dt, end_dt]
        where_clause = "WHERE processing_timestamp >= %s AND processing_timestamp <= %s"
        
        time_group_sql = "DATE_TRUNC('hour', processing_timestamp)" 

        query = f"""
            SELECT
                {time_group_sql} AS time_group,
                COUNT(*) AS count
            FROM scored_loan_applications
            {where_clause}
            GROUP BY time_group
            ORDER BY time_group ASC;
        """
        
        db_records = execute_query(conn, query, params)  # Note: as_dict=True might not be supported

        data_points: List[Dict[str, Any]] = []
        for record in db_records:
            time_group_dt = record[0]  # Assuming tuple results
            count_val = record[1]
            if time_group_dt is not None and count_val is not None:
                if isinstance(time_group_dt, datetime):
                    if time_group_dt.tzinfo is None:
                        time_group_dt = time_group_dt.replace(tzinfo=timezone.utc)
                    iso_time_group = time_group_dt.isoformat().replace("+00:00", "Z")
                else:
                    iso_time_group = str(time_group_dt) 
                
                data_points.append({
                    "timeGroup": iso_time_group,
                    "count": int(count_val)
                })
        
        logger.info(f"Returning {len(data_points)} data_points.")
        return data_points
        
    except ValueError as ve:
        logger.error(f"ValueError: {str(ve)}")
        raise 
    except Exception as e:
        logger.exception(f"Unhandled error: {str(e)}")
        raise 
    finally:
        if conn:
            conn.close()