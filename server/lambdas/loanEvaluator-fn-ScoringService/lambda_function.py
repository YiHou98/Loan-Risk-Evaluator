import os
import json
from typing import Dict, Any, List

from mock_model import MockBinaryModel

# Initialize the model once, using exactly the same logic as in FastAPI
seed_env = os.environ.get("MODEL_SEED")
MODEL_SEED = int(seed_env) if seed_env is not None and seed_env.isdigit() else None
model = MockBinaryModel(seed=MODEL_SEED)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Expects `event` itself to be a flat dict of features.
    Returns {"risk_score": <float>} directly, with try/except around model invocation.
    """

    # 1. Ensure `event` is a non-empty dict
    if not isinstance(event, dict) or not event:
        raise ValueError("Event must be a non-empty dict of features.")

    # 2. Wrap in list for the model
    input_for_model: List[Dict[str, Any]] = [event]
    try:
        # 3. Call predict_proba → pick probability of class=1
        probabilities = model.predict_proba(input_for_model)

        # 4. Validate model output shape
        if (
            probabilities is None
            or not hasattr(probabilities, "shape")
            or probabilities.shape[0] == 0
            or probabilities.shape[1] < 2
        ):
            return {
                "statusCode": 500,
                "body": json.dumps({"detail": "Model output was not in expected format."})
            }

        risk_score = float(probabilities[0][1])
        risk_score_value = round(risk_score, 6)

        return {
            "statusCode": 200,
            "body": json.dumps({"risk_score": risk_score_value})
        }
    except Exception as e:
        message = str(e).lower()
        if "429" in message or "too many requests" in message or "rate limit" in message:
            return {
                "statusCode": 429,
                "body": json.dumps({"detail": "Rate limit exceeded. Try again later."})
            }
        return {
            "statusCode": 500,
            "body": json.dumps({"detail": f"An internal error occurred during scoring: {str(e)}"})
        }
