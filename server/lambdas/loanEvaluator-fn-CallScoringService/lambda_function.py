import os
import json
import urllib3

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service="ScoringServiceCallerLambda")
tracer = Tracer(service="ScoringServiceCallerLambda")

# Reuse this PoolManager across warm invocations for connection pooling
http = urllib3.PoolManager()
SCORING_SERVICE_API_URL = os.environ.get("SCORING_SERVICE_API_URL")

class ScoringServiceCallFailed(Exception):
    """Raised when the scoring service returns HTTP 429 (Too Many Requests)."""

class ScoringServiceResponseError(Exception):
    """Raised when the scoring service returns any other non-200 status."""

@logger.inject_lambda_context()
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    This Lambda now expects 'event' == features_for_scoring (12-field dict).
    1. Validate that 'event' is a non-empty dict of features.
    2. Send it as JSON to SCORING_SERVICE_API_URL (POST).
    3. Parse response JSON, extract "risk_score", and return {"risk_score": <float>}.
    """

    # 1. Validate input: 'event' should be the features dict itself
    if not isinstance(event, dict) or not event:
        logger.error(
            "Invalid or missing features_for_scoring payload",
            extra={"event_received": event}
        )
        raise ValueError("Payload must be a non-empty dict of features_for_scoring")  # :contentReference[oaicite:5]{index=5}

    # 2. Convert the features dict (which is 'event') to JSON bytes
    try:
        body_bytes = json.dumps(event).encode("utf-8")
    except (TypeError, ValueError) as e:
        logger.error(
            "Failed to serialize features_for_scoring to JSON",
            extra={"error": str(e), "features_payload": event}
        )
        raise ValueError("Could not JSON-encode features_for_scoring") from e  # :contentReference[oaicite:6]{index=6}

    # 3–5. Send POST, check HTTP status, parse JSON, extract risk_score
    try:
        logger.info(
            "Calling scoring service",
            extra={"url": SCORING_SERVICE_API_URL, "feature_count": len(event)}
        )
        response = http.request(
            "POST",
            SCORING_SERVICE_API_URL,
            body=body_bytes,
            headers={"Content-Type": "application/json"},
            timeout=urllib3.Timeout(connect=2.0, read=5.0)
        )

        if response.status == 429:
            logger.warning("Scoring service throttled (HTTP 429)", extra={"url": SCORING_SERVICE_API_URL})
            raise ScoringServiceCallFailed("Scoring service returned HTTP 429 (Too Many Requests)")

        if response.status != 200:
            logger.error("Scoring service returned non-200 status", extra={"status": response.status, "data_excerpt": response.data[:200]})
            raise ScoringServiceResponseError(f"Scoring service returned HTTP {response.status}")

        # 5. Parse JSON, extract risk_score
        data = json.loads(response.data.decode("utf-8"))
        raw_score = data.get("risk_score")
        if raw_score is None:
            logger.error(
                "Response missing 'risk_score'",
                extra={"response_payload": data}
            )
            raise ScoringServiceResponseError("Missing 'risk_score' in scoring response")

        risk_score = float(raw_score)
        logger.info("Successfully retrieved risk score", extra={"risk_score": risk_score})
        return {"risk_score": risk_score}

    except ScoringServiceCallFailed:
        # Let Step Functions Retry block catch this
        raise
    except ScoringServiceResponseError:
        # Let Step Functions Retry block catch this as well
        raise
    except (urllib3.exceptions.HTTPError, json.JSONDecodeError, TypeError, ValueError) as e:
        logger.exception("Error during scoring service call or response parsing")
        raise RuntimeError(f"Scoring service error: {e}") from e
    
