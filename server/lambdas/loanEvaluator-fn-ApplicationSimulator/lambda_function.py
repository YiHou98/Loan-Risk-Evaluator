import os
import json
from datetime import datetime, timezone

from utils import *

# Configuration (pulled from environment variables)
DYNAMODB_TABLE_NAME = os.environ.get('SIMULATOR_DYNAMODB_TABLE')
SIMULATOR_ID = os.environ.get('SIMULATOR_ID')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
S3_BUCKET = os.environ.get('BUCKET_NAME')
S3_CSV_KEY = os.environ.get('S3_CSV_KEY')
DAILY_TARGET = int(os.environ.get('DAILY_TARGET', '7500'))

# Constants
HEADER_READ_BYTES = 4095       # Read this many bytes to capture the header
MIN_CHUNK_SIZE = 8 * 1024      # 8KB
MAX_CHUNK_SIZE = 256 * 1024    # 256KB

# Global cache for header line (persisted for the duration of the Lambda container’s lifetime)
CACHED_HEADER = None

def lambda_handler(event, context):
    """
    Entry point for Lambda, triggered every 5 minutes.
    Reads simulator state, computes how many applications to send, reads that chunk from S3,
    pushes messages to SQS, and updates DynamoDB with new offsets.
    """
    global CACHED_HEADER

    # 1) Compute how many applications to send right now
    now = datetime.now(timezone.utc)
    apps_to_send = calculate_applications_for_window(
        now.hour, now.minute, now.weekday(), DAILY_TARGET
    )
    print(f"Target: {apps_to_send} applications at {now.strftime('%H:%M')} UTC")

    if apps_to_send == 0:
        return {'statusCode': 200, 'body': json.dumps({'sent': 0})}

    # 2) Fetch current simulator state from DynamoDB
    state = get_simulator_state(DYNAMODB_TABLE_NAME, SIMULATOR_ID)

    # 3) If header not cached in this container, either pull from state or read fresh
    if not CACHED_HEADER:
        if state.get('headerCached'):
            CACHED_HEADER = state['headerCached']
        else:
            CACHED_HEADER = read_csv_header(S3_BUCKET, S3_CSV_KEY)
            # The byte offset immediately after the header line (plus BOM length)
            state['s3StartByteOffset'] = len(CACHED_HEADER.encode('utf-8-sig')) + 1

    # 4) Determine how many bytes to read: add a buffer of 20% to account for variability
    estimated_bytes = int(apps_to_send * AVERAGE_BYTES_PER_ROW * 1.2)
    chunk_size = max(MIN_CHUNK_SIZE, min(estimated_bytes, MAX_CHUNK_SIZE))

    # 5) Read that chunk of rows from S3 (starting from the last saved offset)
    applications, new_byte_offset, new_partial_line = read_applications(
        bucket_name=S3_BUCKET,
        csv_key=S3_CSV_KEY,
        start_byte=state.get('s3StartByteOffset', 0),
        partial_line=state.get('partialLineCarryOver', ''),
        count_needed=apps_to_send,
        chunk_size=chunk_size,
        header_line=CACHED_HEADER
    )

    # 6) Push the parsed application dicts to SQS
    sent_count = send_to_sqs(SQS_QUEUE_URL, applications)

    # 7) Update DynamoDB with the new offset, last line index, and any leftover partial line
    update_simulator_state(
        table_name=DYNAMODB_TABLE_NAME,
        simulator_id=SIMULATOR_ID,
        byte_offset=new_byte_offset,
        line_index=state.get('lastProcessedLineIndex', -1) + sent_count,
        partial_line=new_partial_line,
        header_line=CACHED_HEADER
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'sent': sent_count,
            'target': apps_to_send
        })
    }
