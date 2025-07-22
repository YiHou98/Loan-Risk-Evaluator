import os
import csv
import random
from io import StringIO
from datetime import datetime, timezone
import json

import boto3

# Constants based on your data
AVERAGE_BYTES_PER_ROW = 510

# AWS resource/clients
_s3_client = boto3.client('s3')
_dynamodb_resource = boto3.resource('dynamodb')
_sqs_client = boto3.client('sqs')

def calculate_applications_for_window(hour: int, minute: int, dow: int, daily_target: int) -> int:
    """
    Calculate how many applications to send in the current 1-minute window,
    based on an hourly distribution, day-of-week multiplier, and a random factor.
    """
    hourly_dist = {
        0: 0.003, 1: 0.002, 2: 0.002, 3: 0.002, 4: 0.002, 5: 0.003,
        6: 0.010, 7: 0.015, 8: 0.025,
        9: 0.070, 10: 0.065, 11: 0.065,
        12: 0.125, 13: 0.125,
        14: 0.050, 15: 0.050, 16: 0.050,
        17: 0.100, 18: 0.100, 19: 0.050,
        20: 0.025, 21: 0.020, 22: 0.015, 23: 0.010
    }
    day_mult = [1.1, 1.0, 1.0, 1.0, 0.9, 0.3, 0.2]
    
    hourly_apps = daily_target * hourly_dist.get(hour, 0.01) * day_mult[dow]
    window_apps = hourly_apps / 60
    window_apps *= random.uniform(0.7, 1.3)
    
    return max(0, int(round(window_apps)))

def read_csv_header(bucket_name: str, csv_key: str) -> str:
    """
    Fetch just the first line (header) of the CSV from S3 by requesting a byte range.
    """
    response = _s3_client.get_object(
        Bucket=bucket_name,
        Key=csv_key,
        Range='bytes=0-4095'
    )
    content = response['Body'].read().decode('utf-8-sig')
    header_line = content.split('\n')[0]
    return header_line

def read_applications(bucket_name: str,
                      csv_key: str,
                      start_byte: int,
                      partial_line: str,
                      count_needed: int,
                      chunk_size: int,
                      header_line: str) -> tuple[list[dict], int, str]:
    """
    Read a chunk of the CSV starting from `start_byte`, 
    append any carried-over partial line, and parse up to `count_needed` rows.
    Returns: (list_of_application_dicts, new_byte_offset, leftover_partial_line)
    """
    applications: list[dict] = []
    buffer = partial_line
    current_byte = start_byte
    
    try:
        end_byte = current_byte + chunk_size - 1
        response = _s3_client.get_object(
            Bucket=bucket_name,
            Key=csv_key,
            Range=f'bytes={current_byte}-{end_byte}'
        )
        chunk = response['Body'].read().decode('utf-8-sig', errors='replace')
        buffer += chunk
        
        lines = buffer.split('\n')
        if not chunk.endswith('\n'):
            buffer = lines[-1]
            lines = lines[:-1]
        else:
            buffer = ''
        
        keys = header_line.split(',')
        for line in lines:
            if not line.strip():
                continue
            if len(applications) >= count_needed:
                break
            try:
                values = list(csv.reader(StringIO(line)))[0]
                if len(values) == len(keys):  # Expecting same number of columns as header
                    app = { key.strip('"'): values[i] for i, key in enumerate(keys) }
                    applications.append(app)
            except Exception:
                # Skip malformed lines
                continue
        
        bytes_processed = len(chunk.encode('utf-8-sig')) - len(buffer.encode('utf-8-sig'))
        new_byte_offset = current_byte + bytes_processed
        
    except Exception as e:
        # If there’s an S3 read error, we don’t advance the offset
        print(f"Error reading S3: {e}")
        new_byte_offset = current_byte
    
    return applications[:count_needed], new_byte_offset, buffer

def send_to_sqs(queue_url: str, applications: list[dict]) -> int:
    """
    Send application dictionaries to SQS in batches of up to 10 messages.
    Returns the number of successfully sent messages.
    """
    sent = 0
    for i in range(0, len(applications), 10):
        batch = applications[i:i+10]
        entries = [
            {
                'Id': str(idx),
                'MessageBody': json.dumps(app)
            }
            for idx, app in enumerate(batch)
        ]
        try:
            response = _sqs_client.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            failed = response.get('Failed', [])
            sent += (len(batch) - len(failed))
        except Exception as e:
            print(f"SQS error: {e}")
    return sent

def get_simulator_state(table_name: str, simulator_id: str) -> dict:
    """
    Fetches the state item from DynamoDB if it exists, otherwise returns defaults.
    """
    table = _dynamodb_resource.Table(table_name)
    try:
        response = table.get_item(Key={'simulatorId': simulator_id})
        if 'Item' in response:
            item = response['Item']
            return {
                's3StartByteOffset': int(item.get('s3StartByteOffset', 0)),
                'lastProcessedLineIndex': int(item.get('lastProcessedLineIndex', -1)),
                'headerCached': item.get('headerCached'),
                'partialLineCarryOver': item.get('partialLineCarryOver', '')
            }
    except Exception:
        pass
    
    return {
        's3StartByteOffset': 0,
        'lastProcessedLineIndex': -1,
        'headerCached': None,
        'partialLineCarryOver': ''
    }

def update_simulator_state(table_name: str,
                           simulator_id: str,
                           byte_offset: int,
                           line_index: int,
                           partial_line: str,
                           header_line: str = None) -> None:
    """
    Overwrites (or creates) the DynamoDB item corresponding to this simulator’s state.
    """
    table = _dynamodb_resource.Table(table_name)
    try:
        item = {
            'simulatorId': simulator_id,
            's3StartByteOffset': byte_offset,
            'lastProcessedLineIndex': line_index,
            'partialLineCarryOver': partial_line,
            'lastUpdateTime': datetime.now(timezone.utc).isoformat()
        }
        if header_line:
            item['headerCached'] = header_line
        table.put_item(Item=item)
    except Exception as e:
        print(f"DynamoDB error: {e}")
