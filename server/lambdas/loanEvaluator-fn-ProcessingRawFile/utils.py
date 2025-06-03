import csv
import io
import traceback
from typing import List, Set
import boto3

_s3 = boto3.client('s3')


def index_to_excel_col(idx: int) -> str:
    """Converts a 0-based index to an Excel-like column letter (A, B, …, Z, AA, AB, …)."""
    col_str = ""
    n = idx + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        col_str = chr(65 + remainder) + col_str
    return col_str


def excel_col_to_index(col_str: str) -> int:
    """
    Converts Excel column letters (A, B, …, Z, AA, AB, …) to a 0-based index.
    "A" → 0, "B" → 1, …, "Z" → 25, "AA" → 26, etc.
    """
    processed = col_str.strip().upper()
    if not processed:
        raise ValueError("Excel column string cannot be empty.")

    index = 0
    power = 1
    for ch in reversed(processed):
        if not ('A' <= ch <= 'Z'):
            raise ValueError(f"Invalid character '{ch}' in Excel column '{col_str}'. Only A–Z allowed.")
        index += (ord(ch) - ord('A') + 1) * power
        power *= 26
    return index - 1  # adjust to 0-based


def get_indices_to_remove(specs: List[str]) -> Set[int]:
    """
    Parses a list of column specs (e.g. ["A", "DT-EG"]) into a set of 0-based indices to skip.
    """
    to_skip: Set[int] = set()
    for spec in specs:
        spec = spec.strip().upper()
        if '-' in spec:
            try:
                start_col, end_col = spec.split('-')
                s_idx = excel_col_to_index(start_col)
                e_idx = excel_col_to_index(end_col)
                if s_idx <= e_idx:
                    for i in range(s_idx, e_idx + 1):
                        to_skip.add(i)
                else:
                    print(f"Warning: invalid range '{spec}' (start > end). Skipping it.")
            except Exception as e:
                print(f"Warning: cannot parse range '{spec}': {e}")
        else:
            try:
                idx = excel_col_to_index(spec)
                to_skip.add(idx)
            except Exception as e:
                print(f"Warning: cannot parse column '{spec}': {e}")
    return to_skip


def remove_columns_s3(
    input_bucket: str,
    input_key: str,
    output_bucket: str,
    output_key: str,
    columns_to_remove: List[str]
) -> None:
    """
    Streams the CSV from s3://input_bucket/input_key, removes columns specified by Excel-letter specs,
    and writes the cleaned CSV to s3://output_bucket/output_key.
    """
    skips = get_indices_to_remove(columns_to_remove)
    print(f"Will remove 0-based indices: {sorted(skips)}")

    # 1) Stream the CSV body from S3
    resp = _s3.get_object(Bucket=input_bucket, Key=input_key)
    body_stream = resp['Body'].iter_lines(chunk_size=1 << 13, keepends=True)

    # 2) Write into an in-memory buffer (StringIO) and then upload. 
    #    If handling extremely large files, consider a multipart‐upload or temporary file in /tmp.
    out_buffer = io.StringIO()
    writer = csv.writer(out_buffer)

    reader = csv.reader((line.decode('utf-8-sig') for line in body_stream))

    try:
        header = next(reader)
    except StopIteration:
        raise ValueError(f"Input CSV s3://{input_bucket}/{input_key} is empty or has no header.")

    new_header = [h for i, h in enumerate(header) if i not in skips]
    writer.writerow(new_header)
    print(f"Header: original={len(header)} columns, new={len(new_header)} columns")

    row_count = 0
    for row in reader:
        new_row = [v for i, v in enumerate(row) if i not in skips]
        writer.writerow(new_row)
        row_count += 1
        if row_count % 200_000 == 0:
            print(f"  …processed {row_count} rows…")

    print(f"Finished removing columns. Total rows processed: {row_count}")

    out_buffer.seek(0)
    _s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=out_buffer.getvalue().encode('utf-8-sig'),
        ContentType='text/csv'
    )
    print(f"Uploaded cleaned CSV to s3://{output_bucket}/{output_key}")


def extract_unique_values_s3(
    input_bucket: str,
    input_key: str,
    excel_column_letter: str,
    output_bucket: str,
    output_key: str
) -> None:
    """
    Streams the CSV from s3://input_bucket/input_key, extracts unique values for the specified column,
    and writes a one‐column CSV of those uniques to s3://output_bucket/output_key.
    """
    print(f"Extracting unique values from column '{excel_column_letter.upper()}'…")
    col_idx = excel_col_to_index(excel_column_letter)

    resp = _s3.get_object(Bucket=input_bucket, Key=input_key)
    body_stream = resp['Body'].iter_lines(chunk_size=1 << 13, keepends=True)
    reader = csv.reader((line.decode('utf-8-sig') for line in body_stream))

    try:
        header = next(reader)
    except StopIteration:
        raise ValueError(f"Input CSV s3://{input_bucket}/{input_key} is empty or has no header.")

    if col_idx < 0 or col_idx >= len(header):
        max_col = index_to_excel_col(len(header) - 1)
        raise IndexError(
            f"Column index {col_idx} (from '{excel_column_letter}') out of bounds. "
            f"Valid columns: A–{max_col}."
        )

    target_name = header[col_idx].strip()
    uniques = set()
    row_count = 0

    for row in reader:
        row_count += 1
        if col_idx < len(row):
            val = row[col_idx].strip()
            uniques.add(val)
        else:
            uniques.add("<_row_too_short_>")

        if row_count % 200_000 == 0:
            print(f"  …scanned {row_count} rows, unique so far: {len(uniques)}…")

    print(f"Total rows scanned: {row_count}, Unique values found: {len(uniques)}")

    if not uniques:
        raise ValueError(f"No unique values found in column '{target_name}'.")

    # Write uniques into a single‐column CSV in memory, then upload
    out_buffer = io.StringIO()
    writer = csv.writer(out_buffer)
    writer.writerow([target_name])
    for val in sorted(uniques):
        writer.writerow([val])

    out_buffer.seek(0)
    _s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=out_buffer.getvalue().encode('utf-8-sig'),
        ContentType='text/csv'
    )
    print(f"Uploaded unique‐values CSV to s3://{output_bucket}/{output_key}")
