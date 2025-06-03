import re
import math
from datetime import datetime
from aws_lambda_powertools import Logger, Tracer

# Initialize Powertools
logger = Logger(service="CleanFeatureEngineerLambdaUtils")
tracer = Tracer(service="CleanFeatureEngineerLambdaUtils")

# Pre-compiled regex patterns for better performance
TERM_PATTERN = re.compile(r'\d+')
EMP_LENGTH_PATTERN = re.compile(r'\d+')

# Cached problematic values for O(1) lookup
PROBLEMATIC_VALUES = frozenset(['nan', 'inf', '-inf', 'infinity', '-infinity', 'na', 'n/a', 'none', 'null'])

def _is_problematic_value(value_str):
    """Check if a string represents a missing/invalid value."""
    if not value_str:
        return True
    return value_str.lower() in PROBLEMATIC_VALUES

def _is_invalid_numeric(value):
    """Check if a numeric value is NaN or Inf."""
    return math.isnan(value) or math.isinf(value)

@tracer.capture_method
def parse_percentage(value_input):
    """
    Parses value into decimal percentage (13.5 -> 0.135).
    Returns None if parsing fails.
    """
    # Handle numeric input
    if isinstance(value_input, (int, float)):
        if _is_invalid_numeric(value_input):
            logger.warning(f"Invalid numeric percentage: {value_input}")
            return None
        return float(value_input) / 100.0
    
    # Handle string input
    if isinstance(value_input, str):
        cleaned = value_input.replace('%', '').strip()
        if _is_problematic_value(cleaned):
            logger.warning(f"Problematic percentage string: '{value_input}'")
            return None
        
        try:
            result = float(cleaned)
            if _is_invalid_numeric(result):
                logger.warning(f"Percentage string '{value_input}' converted to invalid number")
                return None
            return result / 100.0
        except ValueError:
            logger.warning(f"Could not parse percentage: '{value_input}'")
            return None
    
    logger.warning(f"Invalid type for percentage: {type(value_input)}")
    return None

@tracer.capture_method
def robust_float_parse(value_input):
    """
    Parse value to float. Returns None if invalid.
    """
    # Handle numeric input
    if isinstance(value_input, (int, float)):
        if _is_invalid_numeric(value_input):
            logger.warning(f"Invalid numeric value: {value_input}")
            return None
        return float(value_input)
    
    # Handle string input
    if isinstance(value_input, str):
        cleaned = value_input.strip()
        if _is_problematic_value(cleaned):
            logger.warning(f"Problematic string value: '{value_input}'")
            return None
        
        try:
            result = float(cleaned)
            if _is_invalid_numeric(result):
                logger.warning(f"String '{value_input}' converted to invalid number")
                return None
            return result
        except ValueError:
            logger.warning(f"Could not parse to float: '{value_input}'")
            return None
    
    logger.warning(f"Invalid type for float: {type(value_input)}")
    return None

@tracer.capture_method
def parse_term(term_input):
    """
    Parses a loan term (e.g., "36 months" or 36) into an integer.
    Returns None if parsing fails.
    """
    if isinstance(term_input, (int, float)):
        if _is_invalid_numeric(term_input):
            logger.warning(f"Term input is NaN/Inf: {term_input}")
            return None
        try:
            return int(term_input)
        except ValueError:
            logger.warning(f"Could not convert term to int: {term_input}")
            return None
    
    if isinstance(term_input, str):
        match = TERM_PATTERN.search(term_input)
        if match:
            return int(match.group(0))
    
    logger.debug(f"Could not parse term: {term_input}")
    return None

@tracer.capture_method
def parse_emp_length(emp_length_input):
    """
    Parses employment length (e.g., "10+ years", "< 1 year") into integer years.
    Returns None if parsing fails.
    """
    if not isinstance(emp_length_input, str):
        logger.debug(f"emp_length is not a string: '{emp_length_input}'")
        return None
    
    emp_length_lower = emp_length_input.lower().strip()
    
    if not emp_length_lower:
        logger.debug(f"emp_length is empty after strip: '{emp_length_input}'")
        return None
    
    # Special cases
    if "< 1 year" in emp_length_lower or "<1 year" in emp_length_lower:
        return 0
    if "10+ years" in emp_length_lower:
        return 10
    
    # Extract numeric value
    match = EMP_LENGTH_PATTERN.search(emp_length_lower)
    if match:
        return int(match.group(0))
    
    logger.debug(f"Could not parse emp_length: '{emp_length_input}'")
    return None

@tracer.capture_method
def is_self_employed_from_title(emp_title_input):
    """
    Determines if an employment title suggests self-employment.
    """
    if not isinstance(emp_title_input, str) or not emp_title_input.strip():
        return False
    
    title_lower = emp_title_input.lower()
    keywords = [
        "self-employed", "self employed", "owner", "freelance",
        "sole proprietor", "entrepreneur", "selfemployee",
        "selfemployer", "self-contract",
        "self emploed", "self emplyed"
    ]
    return any(keyword in title_lower for keyword in keywords)

@tracer.capture_method
def get_month_from_issue_date(issue_d_input):
    """
    Extracts the month (1-12) from a date string in Mon-YYYY format.
    Returns None if parsing fails.
    """
    if not isinstance(issue_d_input, str) or not issue_d_input.strip():
        logger.debug(f"issue_d is not valid or empty: '{issue_d_input}'")
        return None
    
    date_str = issue_d_input.strip()
    
    if _is_problematic_value(date_str):
        logger.debug(f"issue_d contains problematic value: '{issue_d_input}'")
        return None
    
    # Primary format: Mon-YYYY (e.g., Dec-2018)
    try:
        return datetime.strptime(date_str, "%b-%Y").month
    except ValueError:
        # Fallback: Full month name (e.g., December-2018)
        try:
            return datetime.strptime(date_str, "%B-%Y").month
        except ValueError:
            logger.warning(f"Could not parse month from issue_d: {issue_d_input} (expected Mon-YYYY format)")
            return None

@tracer.capture_method
def parse_state_code(state_input, default_code='XX'):
    """
    Parses state to standardized 2-character uppercase string.
    """
    if isinstance(state_input, str):
        processed = state_input.strip().upper()
        
        if not processed or _is_problematic_value(processed):
            return default_code
            
        return processed[:2]
    
    elif state_input is None:
        return default_code
    
    else:
        logger.warning(f"Unexpected state type: {type(state_input)}, using {default_code}")
        return default_code