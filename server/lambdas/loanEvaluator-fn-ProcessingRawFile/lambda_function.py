import json
import traceback
from typing import Any, Dict

from utils import (
    remove_columns_s3,
    extract_unique_values_s3
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Expects `event` with keys depending on `action`:

      Common required:
        • action (str): "clean" or "unique"
        • input_bucket (str): S3 bucket where the source CSV resides
        • input_key (str): S3 key of the source CSV

      If action == "clean", also requires:
        • output_bucket (str): S3 bucket for cleaned CSV
        • output_key (str): S3 key for cleaned CSV
        • columns_to_remove (list[str]): Excel-style specs (e.g. ["A","DT-EG"])

      If action == "unique", also requires:
        • unique_column (str): A single Excel-style column letter (e.g. "I")
        • unique_output_bucket (str): S3 bucket for unique‐values CSV
        • unique_output_key (str): S3 key for unique‐values CSV

    Returns 200 on success, or 400/500 with a JSON body on error.
    """
    # 1) Check for top-level "action"
    action = event.get("action")
    if action not in ("clean", "unique"):
        return {
            "statusCode": 400,
            "body": json.dumps({"detail": "Missing or invalid 'action'. Must be 'clean' or 'unique'."})
        }

    # 2) Common required inputs
    input_bucket = event.get("input_bucket")
    input_key = event.get("input_key")
    if not input_bucket or not input_key:
        return {
            "statusCode": 400,
            "body": json.dumps({"detail": "Missing 'input_bucket' or 'input_key'."})
        }

    result: Dict[str, Any] = {}
    try:
        if action == "clean":
            # Required for cleaning
            output_bucket = event.get("output_bucket")
            output_key = event.get("output_key")
            specs = event.get("columns_to_remove")

            missing = [k for k in ("output_bucket", "output_key", "columns_to_remove") if not event.get(k)]
            if missing:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"detail": f"Missing for clean: {', '.join(missing)}"})
                }

            # Call the utility to remove columns
            remove_columns_s3(
                input_bucket=input_bucket,
                input_key=input_key,
                output_bucket=output_bucket,
                output_key=output_key,
                columns_to_remove=specs
            )
            result["cleaned_csv_s3"] = f"s3://{output_bucket}/{output_key}"

        elif action == "unique":
            # Required for unique extraction
            unique_column = event.get("unique_column")
            unique_out_bucket = event.get("unique_output_bucket")
            unique_out_key = event.get("unique_output_key")

            missing = [k for k in ("unique_column", "unique_output_bucket", "unique_output_key") if not event.get(k)]
            if missing:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"detail": f"Missing for unique: {', '.join(missing)}"})
                }

            # Call the utility to extract uniques
            extract_unique_values_s3(
                input_bucket=input_bucket,
                input_key=input_key,
                excel_column_letter=unique_column,
                output_bucket=unique_out_bucket,
                output_key=unique_out_key
            )
            result["unique_values_s3"] = f"s3://{unique_out_bucket}/{unique_out_key}"

        # 3) Return success
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        # Print stack trace to CloudWatch Logs, then return 500 with error detail
        print(f"Exception in handler for action '{action}': {e}")
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"detail": f"Internal error: {str(e)}"})
        }
