# test/test_applicationsimulater.py

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure lambda_function.py and utils.py are on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import lambda_function
import utils


class TestCalculateApplicationsForWindow(unittest.TestCase):
    @patch('lambda_function.random.uniform', return_value=1.0)
    def test_midday_weekday(self, mock_uniform):
        """
        For hour=12 (dist=0.125), dow=2 (mult=1.0), daily_target=6000 → hourly_apps=750, window_apps=12.5 → 12
        """
        result = lambda_function.calculate_applications_for_window(hour=12, minute=0, dow=2, daily_target=6000)
        self.assertEqual(result, 12)

    @patch('lambda_function.random.uniform', return_value=0.7)
    def test_early_morning_weekend(self, mock_uniform):
        """
        For hour=6 (dist=0.01), dow=6 (mult=0.2), daily_target=8000 → hourly_apps=16, window≈0.2667 *0.7≈0.1867 → 0
        """
        result = lambda_function.calculate_applications_for_window(hour=6, minute=30, dow=6, daily_target=8000)
        self.assertEqual(result, 0)


class TestSendToSqs(unittest.TestCase):
    @patch.object(utils, '_sqs_client')
    def test_all_messages_sent(self, mock_sqs_client):
        """
        If send_message_batch returns no failures, sent count == number of items.
        """
        mock_sqs_client.send_message_batch.return_value = {'Failed': []}
        apps = [{'id': '1'}, {'id': '2'}, {'id': '3'}]
        sent = utils.send_to_sqs(queue_url='dummy-url', applications=apps)
        self.assertEqual(sent, 3)
        mock_sqs_client.send_message_batch.assert_called_once()

    @patch.object(utils, '_sqs_client')
    def test_partial_failures(self, mock_sqs_client):
        """
        If one message fails, sent count = total - len(failed).
        """
        mock_sqs_client.send_message_batch.return_value = {'Failed': [{'Id': '0'}]}
        apps = [{'id': 'a'}, {'id': 'b'}]
        sent = utils.send_to_sqs(queue_url='dummy-url', applications=apps)
        self.assertEqual(sent, 1)
        mock_sqs_client.send_message_batch.assert_called_once()


class TestDynamoDbState(unittest.TestCase):
    @patch.object(utils, '_dynamodb_resource')
    def test_get_simulator_state_missing_item(self, mock_ddb_resource):
        """
        If get_item returns no 'Item', returns default state.
        """
        fake_table = MagicMock()
        fake_table.get_item.return_value = {}  # no 'Item'
        mock_ddb_resource.Table.return_value = fake_table

        state = utils.get_simulator_state(table_name='tbl', simulator_id='sim1')
        expected = {
            's3StartByteOffset': 0,
            'lastProcessedLineIndex': -1,
            'headerCached': None,
            'partialLineCarryOver': ''
        }
        self.assertDictEqual(state, expected)

    @patch.object(utils, '_dynamodb_resource')
    def test_get_simulator_state_existing_item(self, mock_ddb_resource):
        """
        If get_item returns an 'Item', fields are parsed and returned.
        """
        fake_item = {
            's3StartByteOffset': '100',
            'lastProcessedLineIndex': '5',
            'headerCached': 'hdr1,hdr2',
            'partialLineCarryOver': 'leftover'
        }
        fake_table = MagicMock()
        fake_table.get_item.return_value = {'Item': fake_item}
        mock_ddb_resource.Table.return_value = fake_table

        state = utils.get_simulator_state(table_name='tbl', simulator_id='sim1')
        self.assertEqual(state['s3StartByteOffset'], 100)
        self.assertEqual(state['lastProcessedLineIndex'], 5)
        self.assertEqual(state['headerCached'], 'hdr1,hdr2')
        self.assertEqual(state['partialLineCarryOver'], 'leftover')

    @patch.object(utils, '_dynamodb_resource')
    def test_update_simulator_state_puts_item(self, mock_ddb_resource):
        """
        update_simulator_state calls put_item with correct attributes.
        """
        fake_table = MagicMock()
        mock_ddb_resource.Table.return_value = fake_table

        utils.update_simulator_state(
            table_name='tbl',
            simulator_id='simX',
            byte_offset=200,
            line_index=10,
            partial_line='abc',
            header_line='colA,colB'
        )

        fake_table.put_item.assert_called_once()
        put_args = fake_table.put_item.call_args[1]['Item']
        self.assertEqual(put_args['simulatorId'], 'simX')
        self.assertEqual(put_args['s3StartByteOffset'], 200)
        self.assertEqual(put_args['lastProcessedLineIndex'], 10)
        self.assertEqual(put_args['partialLineCarryOver'], 'abc')
        self.assertEqual(put_args['headerCached'], 'colA,colB')
        self.assertIn('lastUpdateTime', put_args)


class TestLambdaHandler(unittest.TestCase):
    @patch('lambda_function.calculate_applications_for_window', return_value=0)
    def test_lambda_handler_no_apps(self, mock_calc):
        """
        If calculate_applications returns 0, lambda_handler returns sent=0 immediately.
        """
        os.environ['SIMULATOR_DYNAMODB_TABLE'] = 'tbl'
        os.environ['SIMULATOR_ID'] = 'sim'
        os.environ['SQS_QUEUE_URL'] = 'url'
        os.environ['BUCKET_NAME'] = 'bucket'
        os.environ['S3_CSV_KEY'] = 'key'
        os.environ['DAILY_TARGET'] = '100'

        resp = lambda_function.lambda_handler(event={}, context={})
        self.assertEqual(resp['statusCode'], 200)
        self.assertIn('"sent": 0', resp['body'])

    @patch('lambda_function.calculate_applications_for_window', return_value=2)
    @patch('lambda_function.get_simulator_state')
    @patch('lambda_function.update_simulator_state')
    @patch('lambda_function.read_csv_header')
    @patch('lambda_function.read_applications')
    @patch('lambda_function.send_to_sqs')
    def test_lambda_handler_with_apps(self,
                                      mock_send_sqs,
                                      mock_read_apps,
                                      mock_read_hdr,
                                      mock_update_state,
                                      mock_get_state,
                                      mock_calc):
        """
        Simulate lambda_handler when 2 apps should be sent:
        - get_simulator_state returns a state with headerCached
        - read_applications returns 2 dummy applications and new offsets
        - send_to_sqs returns 2
        - update_simulator_state is called
        """
        os.environ['SIMULATOR_DYNAMODB_TABLE'] = 'tbl'
        os.environ['SIMULATOR_ID'] = 'sim'
        os.environ['SQS_QUEUE_URL'] = 'url'
        os.environ['BUCKET_NAME'] = 'bucket'
        os.environ['S3_CSV_KEY'] = 'key'
        os.environ['DAILY_TARGET'] = '100'

        mock_get_state.return_value = {
            's3StartByteOffset': 0,
            'lastProcessedLineIndex': 0,
            'headerCached': 'h1,h2',
            'partialLineCarryOver': ''
        }
        dummy_apps = [{'id': '1'}, {'id': '2'}]
        mock_read_apps.return_value = (dummy_apps, 50, '')

        mock_send_sqs.return_value = 2

        resp = lambda_function.lambda_handler(event={}, context={})
        self.assertEqual(resp['statusCode'], 200)
        self.assertIn('"sent": 2', resp['body'])
        self.assertIn('"target": 2', resp['body'])

        mock_read_hdr.assert_not_called()
        mock_update_state.assert_called_once()
        args, kwargs = mock_update_state.call_args
        self.assertEqual(kwargs['byte_offset'], 50)
        self.assertEqual(kwargs['partial_line'], '')


if __name__ == '__main__':
    unittest.main()
