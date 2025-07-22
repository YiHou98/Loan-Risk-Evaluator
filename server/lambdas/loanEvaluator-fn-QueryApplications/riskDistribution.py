# riskDistribution_simplified.py
from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Tracer
from db_connection import get_aurora_connection
from datetime import datetime, timezone, date, time
from utils import execute_query, check_unsafe_params

logger = Logger(service="RiskDistributionSimplified")
tracer = Tracer(service="RiskDistributionSimplified")

@tracer.capture_method
def process(action: str, body: Dict[str, Any]) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = get_aurora_connection()

        start_date_str = body.get('startDate')
        end_date_str = body.get('endDate')

        if not start_date_str or not end_date_str:
            raise ValueError("startDate and endDate are required for riskDistribution.")

        try:
            start_dt = datetime.combine(date.fromisoformat(start_date_str), time.min, tzinfo=timezone.utc)
            end_dt = datetime.combine(date.fromisoformat(end_date_str), time.max, tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"Invalid date format for startDate or endDate: {start_date_str}, {end_date_str}")
            raise ValueError("Invalid date format. Please use YYYY-MM-DD.")

        params = [start_dt, end_dt]
        where_clause = "WHERE processing_timestamp >= %s AND processing_timestamp <= %s"
        
        # Buckets for risk_score (DECIMAL(7,6)), assuming a 0-1 range
        risk_bucket_sql = """
            CASE
                WHEN risk_score >= 0.0 AND risk_score < 0.2 THEN '0.0-0.2'
                WHEN risk_score >= 0.2 AND risk_score < 0.4 THEN '0.2-0.4'
                WHEN risk_score >= 0.4 AND risk_score < 0.6 THEN '0.4-0.6'
                WHEN risk_score >= 0.6 AND risk_score < 0.8 THEN '0.6-0.8'
                WHEN risk_score >= 0.8 AND risk_score <= 1.0 THEN '0.8-1.0' 
            END
        """
        bucket_order = ['0.0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0']

        query = f"""
            SELECT
                {risk_bucket_sql} AS risk_bucket,
                COUNT(*) AS count
            FROM scored_loan_applications
            {where_clause}
            GROUP BY risk_bucket;
        """
        
        records = execute_query(conn, query, params)

        # Process tuple results - assuming first column is risk_bucket, second is count
        result_map: Dict[str, int] = {}
        for record in records:
            risk_bucket = record[0]
            count = record[1]
            if risk_bucket is not None and count is not None:
                result_map[risk_bucket] = int(count)
        
        # Build ordered output with all buckets (0 for missing ones)
        data_points: List[Dict[str, Any]] = []
        for bucket_name in bucket_order:
            data_points.append({
                "riskBucket": bucket_name,
                "count": result_map.get(bucket_name, 0)
            })

        logger.info(f"Returning risk distribution with {len(data_points)} buckets.")
        return data_points
        
    except ValueError as ve:
        logger.error(f"ValueError: {str(ve)}")
        raise 
    except Exception as e:
        logger.exception(f"Error in RiskDistribution: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()