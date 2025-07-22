# test/test_clean_feature_engineer_lambda.py

import sys
import types
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# ────────────────────────────────────────────────────────────────────────────────
# STUB aws_lambda_powertools.Logger and Tracer so we don't need the real package
# ────────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

fake_powertools = types.ModuleType("aws_lambda_powertools")

class FakeLogger:
    def __init__(self, service: str):
        pass

    def inject_lambda_context(self, log_event=False):
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

    def debug(self, *args, **kwargs):
        pass

class FakeTracer:
    def __init__(self, service: str):
        pass

    def capture_lambda_handler(self, fn):
        return fn  # no-op decorator

    def capture_method(self, fn):
        return fn  # no-op decorator

fake_powertools.Logger = FakeLogger
fake_powertools.Tracer = FakeTracer

fake_typing = types.ModuleType("aws_lambda_powertools.utilities.typing")
fake_typing.LambdaContext = type("LambdaContext", (), {})

sys.modules["aws_lambda_powertools"] = fake_powertools
sys.modules["aws_lambda_powertools.utilities"] = types.ModuleType("aws_lambda_powertools.utilities")
sys.modules["aws_lambda_powertools.utilities.typing"] = fake_typing

# ────────────────────────────────────────────────────────────────────────────────
# Now import the lambda under test and utilities (they will pick up our stubs)
# ────────────────────────────────────────────────────────────────────────────────

import lambda_function   # CleanFeatureEngineerLambda
import utils             # Utility parsing functions


class TestLambdaHandler(unittest.TestCase):
    def setUp(self):
        # Set environment variable for S3_BUCKET
        os.environ["S3_BUCKET"] = "test-bucket"
        lambda_function.S3_BUCKET = os.environ["S3_BUCKET"]

        # Patch boto3.client("s3") to use a MagicMock s3_client
        self.s3_patcher = patch("lambda_function.s3_client")
        self.mock_s3_client = self.s3_patcher.start()

    def tearDown(self):
        self.s3_patcher.stop()
        os.environ.pop("S3_BUCKET", None)

    def test_missing_application_id_raises(self):
        event = {
            "loanApplication": {"loan_amnt": "1000"},
            "sqsMessageAttributes": {"messageId": "msg-1"}
        }
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event, context={})
        self.assertIn("Event must include 'application_id'", str(cm.exception))

    def test_missing_loan_application_raises(self):
        event = {"application_id": "app-1", "sqsMessageAttributes": {"messageId": "msg-2"}}
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event, context={})
        self.assertIn("Input 'loanApplication' is missing", str(cm.exception))

    def test_missing_message_id_raises(self):
        event = {
            "application_id": "app-2",
            "loanApplication": {"loan_amnt": "500"},
            "sqsMessageAttributes": {}
        }
        with self.assertRaises(ValueError) as cm:
            lambda_function.lambda_handler(event, context={})
        self.assertIn("Event must include 'sqsMessageAttributes.messageId'", str(cm.exception))

    def test_s3_put_failure_raises(self):
        self.mock_s3_client.put_object.side_effect = RuntimeError("S3 error")
        event = {
            "application_id": "app-3",
            "loanApplication": {"loan_amnt": "1000"},
            "sqsMessageAttributes": {"messageId": "msg-3"}
        }
        with self.assertRaises(RuntimeError) as cm:
            lambda_function.lambda_handler(event, context={})
        self.assertIn("S3 error", str(cm.exception))
        expected_key = "applications/app-3.json"
        self.mock_s3_client.put_object.assert_called_once()
        args, kwargs = self.mock_s3_client.put_object.call_args
        self.assertEqual(kwargs["Bucket"], "test-bucket")
        self.assertEqual(kwargs["Key"], expected_key)

    def test_successful_clean_and_feature_engineer(self):
        raw_app = {
            "loan_amnt": "2000",
            "term": "36 months",
            "int_rate": "13.56%",
            "installment": "100.5",
            "emp_length": "10+ years",
            "annual_inc": "50000",
            "dti": "18.5%",
            "addr_state": " ca ",
            "emp_title": "Owner of MyBusiness",
            "issue_d": "Dec-2020"
        }
        event = {
            "application_id": "app-4",
            "loanApplication": raw_app.copy(),
            "sqsMessageAttributes": {"messageId": "msg-4"}
        }
        self.mock_s3_client.put_object.return_value = {}

        result = lambda_function.lambda_handler(event, context={})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["application_id"], "app-4")
        self.assertEqual(result["message_id"], "msg-4")
        features = result["features_for_scoring"]
        self.assertEqual(features["loan_amnt"], 2000.0)
        self.assertEqual(features["term"], 36)
        self.assertAlmostEqual(features["int_rate"], 0.1356, places=4)
        self.assertEqual(features["installment"], 100.5)
        self.assertEqual(features["emp_length"], 10)
        self.assertEqual(features["annual_inc"], 50000.0)
        self.assertAlmostEqual(features["dti"], 0.185, places=4)
        self.assertEqual(features["addr_state"], "CA")
        self.assertAlmostEqual(features["credit_to_income_ratio"], round(2000.0 / 50000.0, 4), places=4)
        self.assertTrue(features["is_self_employed"])
        self.assertEqual(features["loan_month"], 12)
        self.assertTrue(features["is_long_term"])

    def test_clean_with_negative_and_zero_values(self):
        raw_app = {
            "loan_amnt": "-500",
            "term": "60 months",
            "int_rate": "10%",
            "installment": None,
            "emp_length": "< 1 year",
            "annual_inc": "0",
            "dti": "inf",
            "addr_state": None,
            "emp_title": "Worker",
            "issue_d": "BadDate"
        }
        event = {
            "application_id": "app-5",
            "loanApplication": raw_app.copy(),
            "sqsMessageAttributes": {"messageId": "msg-5"}
        }
        self.mock_s3_client.put_object.return_value = {}

        result = lambda_function.lambda_handler(event, context={})
        features = result["features_for_scoring"]
        self.assertEqual(features["loan_amnt"], 0.0)
        self.assertEqual(features["term"], 60)
        self.assertAlmostEqual(features["int_rate"], 0.10, places=4)
        self.assertEqual(features["installment"], 0.0)
        self.assertEqual(features["emp_length"], 0)
        self.assertEqual(features["annual_inc"], 1.0)
        self.assertEqual(features["dti"], 0.0)
        self.assertEqual(features["addr_state"], "XX")
        self.assertEqual(features["credit_to_income_ratio"], 0.0)
        self.assertEqual(features["loan_month"], 0)
        self.assertTrue(features["is_long_term"])


class TestUtilsFunctions(unittest.TestCase):
    def test_parse_percentage(self):
        self.assertAlmostEqual(utils.parse_percentage(13.5), 0.135)
        self.assertAlmostEqual(utils.parse_percentage("20%"), 0.20)
        self.assertIsNone(utils.parse_percentage("nan"))
        self.assertIsNone(utils.parse_percentage("bad"))
        self.assertIsNone(utils.parse_percentage(None))

    def test_robust_float_parse(self):
        self.assertEqual(utils.robust_float_parse(100), 100.0)
        self.assertEqual(utils.robust_float_parse("  45.6 "), 45.6)
        self.assertIsNone(utils.robust_float_parse("inf"))
        self.assertIsNone(utils.robust_float_parse("foo"))
        self.assertIsNone(utils.robust_float_parse({"a": 1}))

    def test_parse_term(self):
        self.assertEqual(utils.parse_term("36 months"), 36)
        self.assertEqual(utils.parse_term(60), 60)
        self.assertIsNone(utils.parse_term("bad"))

    def test_parse_emp_length(self):
        self.assertEqual(utils.parse_emp_length("< 1 year"), 0)
        self.assertEqual(utils.parse_emp_length("10+ years"), 10)
        self.assertEqual(utils.parse_emp_length("3 years"), 3)
        self.assertIsNone(utils.parse_emp_length(5))
        self.assertIsNone(utils.parse_emp_length(""))

    def test_is_self_employed_from_title(self):
        self.assertTrue(utils.is_self_employed_from_title("Owner of Shop"))
        self.assertTrue(utils.is_self_employed_from_title("Freelance Designer"))
        self.assertFalse(utils.is_self_employed_from_title("Software Engineer"))
        self.assertFalse(utils.is_self_employed_from_title(""))

    def test_get_month_from_issue_date(self):
        self.assertEqual(utils.get_month_from_issue_date("Dec-2018"), 12)
        self.assertEqual(utils.get_month_from_issue_date("December-2019"), 12)
        self.assertIsNone(utils.get_month_from_issue_date("BadDate"))
        self.assertIsNone(utils.get_month_from_issue_date(""))

    def test_parse_state_code(self):
        self.assertEqual(utils.parse_state_code(" ca "), "CA")
        self.assertEqual(utils.parse_state_code(None), "XX")
        self.assertEqual(utils.parse_state_code(""), "XX")
        self.assertEqual(utils.parse_state_code("New York"), "NE")
        self.assertEqual(utils.parse_state_code(123), "XX")


if __name__ == "__main__":
    unittest.main()