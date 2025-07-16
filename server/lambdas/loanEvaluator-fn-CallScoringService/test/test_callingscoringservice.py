# test/test_callingscoringservice.py

import sys
import types
import os
import json
import unittest
from unittest.mock import patch, MagicMock

import urllib3

# ────────────────────────────────────────────────────────────────────────────────
# STUB aws_lambda_powertools.Logger and Tracer so we don't need the real package
# ────────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
fake_powertools = types.ModuleType("aws_lambda_powertools")

class FakeLogger:
    def __init__(self, service: str):
        pass

    def inject_lambda_context(self):
        def decorator(fn):
            return fn
        return decorator

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass

class FakeTracer:
    def __init__(self, service: str):
        pass

    def capture_lambda_handler(self, fn):
        return fn  # no-op decorator

fake_powertools.Logger = FakeLogger
fake_powertools.Tracer = FakeTracer

fake_typing = types.ModuleType("aws_lambda_powertools.utilities.typing")
fake_typing.LambdaContext = type("LambdaContext", (), {})

sys.modules["aws_lambda_powertools"] = fake_powertools
sys.modules["aws_lambda_powertools.utilities"] = types.ModuleType("aws_lambda_powertools.utilities")
sys.modules["aws_lambda_powertools.utilities.typing"] = fake_typing

# ────────────────────────────────────────────────────────────────────────────────
# Now import the lambda under test (it will pick up our stubs above)
# ────────────────────────────────────────────────────────────────────────────────

import lambda_function  # your ScoringServiceCallerLambda code


class TestScoringServiceCallerLambda(unittest.TestCase):
    def setUp(self):
        os.environ["SCORING_SERVICE_API_URL"] = "https://example.com/score"
        # Override module-level constant to pick up the new env var
        lambda_function.SCORING_SERVICE_API_URL = os.environ["SCORING_SERVICE_API_URL"]

    def tearDown(self):
        os.environ.pop("SCORING_SERVICE_API_URL", None)

    def test_invalid_input_none(self):
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event=None, context={})
        self.assertIn("Payload must be a non-empty dict", str(cm.exception))

    def test_invalid_input_empty_dict(self):
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event={}, context={})
        self.assertIn("Payload must be a non-empty dict", str(cm.exception))

    def test_invalid_serialization(self):
        bad_event = {"feature1": {1, 2, 3}}
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event=bad_event, context={})
        self.assertIn("Could not JSON-encode features_for_scoring", str(cm.exception))

    @patch.object(lambda_function.http, "request")
    def test_http_429_response(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status = 429
        mock_resp.data = b"{}"
        mock_request.return_value = mock_resp

        valid_event = {"f1": 1, "f2": 2}
        with self.assertRaises(lambda_function.ScoringServiceCallFailed):
            lambda_function.lambda_handler(event=valid_event, context={})

        mock_request.assert_called_once()
        args, _ = mock_request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], os.environ["SCORING_SERVICE_API_URL"])

    @patch.object(lambda_function.http, "request")
    def test_http_non200_response(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.data = b'{"error": "server error"}'
        mock_request.return_value = mock_resp

        valid_event = {"f1": 1, "f2": 2}
        with self.assertRaises(lambda_function.ScoringServiceResponseError) as cm:
            lambda_function.lambda_handler(event=valid_event, context={})
        self.assertIn("Scoring service returned HTTP 500", str(cm.exception))

    @patch.object(lambda_function.http, "request")
    def test_missing_risk_score_in_response(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.data = json.dumps({"score": 0.5}).encode("utf-8")
        mock_request.return_value = mock_resp

        valid_event = {"f1": 1, "f2": 2}
        with self.assertRaises(lambda_function.ScoringServiceResponseError) as cm:
            lambda_function.lambda_handler(event=valid_event, context={})
        self.assertIn("Missing 'risk_score'", str(cm.exception))

    @patch.object(lambda_function.http, "request")
    def test_successful_response(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.data = json.dumps({"risk_score": "0.85"}).encode("utf-8")
        mock_request.return_value = mock_resp

        valid_event = {"f1": 1, "f2": 2}
        result = lambda_function.lambda_handler(event=valid_event, context={})
        self.assertIsInstance(result, dict)
        self.assertIn("risk_score", result)
        self.assertAlmostEqual(result["risk_score"], 0.85)

    @patch.object(lambda_function.http, "request")
    def test_http_exception_raises_runtime_error(self, mock_request):
        mock_request.side_effect = urllib3.exceptions.HTTPError("connection failed")

        valid_event = {"f1": 1, "f2": 2}
        with self.assertRaises(RuntimeError) as cm:
            lambda_function.lambda_handler(event=valid_event, context={})
        self.assertIn("Scoring service error", str(cm.exception))


if __name__ == "__main__":
    unittest.main()