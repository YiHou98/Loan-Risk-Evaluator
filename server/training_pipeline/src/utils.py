import re
import math
import sys
from datetime import datetime

# Install required packages if not available
try:
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import LabelEncoder
except ImportError as e:
    print(f"Missing required package in utils.py: {e}")
    print("Installing packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "numpy", "scikit-learn"])
    
    # Try importing again
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import LabelEncoder

# Try to import AWS dependencies, fall back to simple logging if not available
try:
    from aws_lambda_powertools import Logger, Tracer
    logger = Logger(service="CleanFeatureEngineerLambdaUtils")
    tracer = Tracer(service="CleanFeatureEngineerLambdaUtils")
    
    def log_info(msg):
        logger.info(msg)
    def log_warning(msg):
        logger.warning(msg)
    def log_debug(msg):
        logger.debug(msg)
        
except ImportError:
    # Simple logging fallback for SageMaker environment
    def log_info(msg):
        print(f"INFO: {msg}")
    def log_warning(msg):
        print(f"WARNING: {msg}")
    def log_debug(msg):
        print(f"DEBUG: {msg}")
    
    # Create a proper mock tracer that doesn't break decorators
    class MockTracer:
        def capture_method(self, func):
            return func
    tracer = MockTracer()

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
            log_warning(f"Invalid numeric percentage: {value_input}")
            return None
        return float(value_input) / 100.0
    
    # Handle string input
    if isinstance(value_input, str):
        cleaned = value_input.replace('%', '').strip()
        if _is_problematic_value(cleaned):
            log_warning(f"Problematic percentage string: '{value_input}'")
            return None
        
        try:
            result = float(cleaned)
            if _is_invalid_numeric(result):
                log_warning(f"Percentage string '{value_input}' converted to invalid number")
                return None
            return result / 100.0
        except ValueError:
            log_warning(f"Could not parse percentage: '{value_input}'")
            return None
    
    log_warning(f"Invalid type for percentage: {type(value_input)}")
    return None

@tracer.capture_method
def robust_float_parse(value_input):
    """
    Parse value to float. Returns None if invalid.
    """
    # Handle numeric input
    if isinstance(value_input, (int, float)):
        if _is_invalid_numeric(value_input):
            log_warning(f"Invalid numeric value: {value_input}")
            return None
        return float(value_input)
    
    # Handle string input
    if isinstance(value_input, str):
        cleaned = value_input.strip()
        if _is_problematic_value(cleaned):
            log_warning(f"Problematic string value: '{value_input}'")
            return None
        
        try:
            result = float(cleaned)
            if _is_invalid_numeric(result):
                log_warning(f"String '{value_input}' converted to invalid number")
                return None
            return result
        except ValueError:
            log_warning(f"Could not parse to float: '{value_input}'")
            return None
    
    log_warning(f"Invalid type for float: {type(value_input)}")
    return None

@tracer.capture_method
def parse_term(term_input):
    """
    Parses a loan term (e.g., "36 months" or 36) into an integer.
    Returns None if parsing fails.
    """
    if isinstance(term_input, (int, float)):
        if _is_invalid_numeric(term_input):
            log_warning(f"Term input is NaN/Inf: {term_input}")
            return None
        try:
            return int(term_input)
        except ValueError:
            log_warning(f"Could not convert term to int: {term_input}")
            return None
    
    if isinstance(term_input, str):
        match = TERM_PATTERN.search(term_input)
        if match:
            return int(match.group(0))
    
    log_debug(f"Could not parse term: {term_input}")
    return None

@tracer.capture_method
def parse_emp_length(emp_length_input):
    """
    Parses employment length (e.g., "10+ years", "< 1 year") into integer years.
    Returns None if parsing fails.
    """
    if not isinstance(emp_length_input, str):
        log_debug(f"emp_length is not a string: '{emp_length_input}'")
        return None
    
    emp_length_lower = emp_length_input.lower().strip()
    
    if not emp_length_lower:
        log_debug(f"emp_length is empty after strip: '{emp_length_input}'")
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
    
    log_debug(f"Could not parse emp_length: '{emp_length_input}'")
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
        log_debug(f"issue_d is not valid or empty: '{issue_d_input}'")
        return None
    
    date_str = issue_d_input.strip()
    
    if _is_problematic_value(date_str):
        log_debug(f"issue_d contains problematic value: '{issue_d_input}'")
        return None
    
    # Primary format: Mon-YYYY (e.g., Dec-2018)
    try:
        return datetime.strptime(date_str, "%b-%Y").month
    except ValueError:
        # Fallback: Full month name (e.g., December-2018)
        try:
            return datetime.strptime(date_str, "%B-%Y").month
        except ValueError:
            log_warning(f"Could not parse month from issue_d: {issue_d_input} (expected Mon-YYYY format)")
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
        log_warning(f"Unexpected state type: {type(state_input)}, using {default_code}")
        return default_code


# ========== DATA PREPROCESSING FUNCTIONS FOR TRAINING ==========

def get_essential_features():
    """Return the list of essential features for training."""
    return [
        # Core loan features
        'loan_amnt', 'funded_amnt', 'installment', 'term',
        # Borrower features  
        'annual_inc', 'dti', 'emp_length',
        # Credit features
        'open_acc', 'pub_rec', 'revol_bal', 'revol_util', 'total_acc',
        'delinq_2yrs', 'inq_last_6mths',
        # Categorical features (will need encoding)
        'grade', 'sub_grade', 'home_ownership', 'purpose', 'addr_state', 'verification_status'
    ]

def preprocess_raw_fields(df):
    """Process raw fields using parsing functions."""
    print("Processing raw fields with proper parsing...")
    
    # Parse term (e.g., " 36 months" -> 36)
    if 'term' in df.columns:
        df['term_parsed'] = df['term'].apply(parse_term)
        df['term_parsed'] = df['term_parsed'].fillna(36)  # Default to 36 months
        print(f"Term parsing: {df['term'].iloc[0]} -> {df['term_parsed'].iloc[0]}")
    
    # Parse emp_length (e.g., "< 1 year" -> 0, "2 years" -> 2)
    if 'emp_length' in df.columns:
        df['emp_length_parsed'] = df['emp_length'].apply(parse_emp_length)
        df['emp_length_parsed'] = df['emp_length_parsed'].fillna(0)  # Default to 0 years
        print(f"Employment length parsing: {df['emp_length'].iloc[1]} -> {df['emp_length_parsed'].iloc[1]}")
    
    # Parse percentages properly
    if 'dti' in df.columns:
        df['dti_parsed'] = df['dti'].apply(robust_float_parse)
        df['dti_parsed'] = df['dti_parsed'].fillna(df['dti_parsed'].median())
    
    if 'revol_util' in df.columns:
        df['revol_util_parsed'] = df['revol_util'].apply(robust_float_parse)
        df['revol_util_parsed'] = df['revol_util_parsed'].fillna(df['revol_util_parsed'].median())
    
    return df

def update_feature_columns_with_parsed(feature_columns, df):
    """Update feature columns to use parsed versions."""
    feature_columns_updated = []
    for col in feature_columns:
        if col == 'term' and 'term_parsed' in df.columns:
            feature_columns_updated.append('term_parsed')
        elif col == 'emp_length' and 'emp_length_parsed' in df.columns:
            feature_columns_updated.append('emp_length_parsed')
        elif col == 'dti' and 'dti_parsed' in df.columns:
            feature_columns_updated.append('dti_parsed')
        elif col == 'revol_util' and 'revol_util_parsed' in df.columns:
            feature_columns_updated.append('revol_util_parsed')
        else:
            feature_columns_updated.append(col)
    
    return [col for col in feature_columns_updated if col in df.columns]

def add_engineered_features(df, feature_columns):
    """Add engineered features like CleanAndTransform lambda."""
    print("Adding engineered features...")
    
    # Credit to income ratio
    if 'loan_amnt' in df.columns and 'annual_inc' in df.columns:
        df['annual_inc'] = df['annual_inc'].fillna(1.0).clip(lower=1.0)  # Avoid division by zero
        df['credit_to_income_ratio'] = df['loan_amnt'] / df['annual_inc']
        feature_columns.append('credit_to_income_ratio')
    
    # Self-employment flag
    if 'emp_title' in df.columns:
        df['is_self_employed'] = df['emp_title'].apply(is_self_employed_from_title).astype(int)
        feature_columns.append('is_self_employed')
    
    # Loan month (seasonal factor)
    if 'issue_d' in df.columns:
        df['loan_month'] = df['issue_d'].apply(get_month_from_issue_date)
        df['loan_month'] = df['loan_month'].fillna(6)  # Default to June
        feature_columns.append('loan_month')
    
    # Long-term loan flag
    if 'term_parsed' in df.columns:
        df['is_long_term'] = (df['term_parsed'] >= 36).astype(int)
        feature_columns.append('is_long_term')
    
    return feature_columns

def handle_missing_and_infinite_values(df, feature_columns):
    """Handle missing and infinite values in features."""
    print("Checking for missing values in processed features...")
    missing_counts = df[feature_columns].isnull().sum()
    columns_with_missing = missing_counts[missing_counts > 0]
    if len(columns_with_missing) > 0:
        print(f"Found missing values in {len(columns_with_missing)} columns:")
        for col, count in columns_with_missing.items():
            print(f"  - {col}: {count} missing values")
        
        # Fill missing values with median for numeric columns
        df[feature_columns] = df[feature_columns].fillna(df[feature_columns].median())
        print("Missing values filled with median values")
    
    # Handle infinite values (only for numeric columns)
    print("Checking for infinite values...")
    for col in feature_columns:
        if col in df.columns and df[col].dtype in ['float64', 'float32', 'int64', 'int32']:
            try:
                inf_count = np.isinf(df[col]).sum()
                if inf_count > 0:
                    print(f"Found {inf_count} infinite values in {col}")
                    # Replace infinite values with median
                    median_val = df[col].replace([np.inf, -np.inf], np.nan).median()
                    df[col] = df[col].replace([np.inf, -np.inf], median_val)
            except TypeError:
                # Skip non-numeric columns
                continue
    
    # Final validation
    print("Final data validation...")
    for col in feature_columns:
        if col in df.columns:
            nan_count = df[col].isnull().sum()
            if nan_count > 0:
                print(f"Warning: {col} still has {nan_count} NaN values")
                # Force fill any remaining issues
                if df[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                    df[col] = df[col].fillna(df[col].median())
                else:
                    # For categorical columns, fill with mode or 'Unknown'
                    mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else 'Unknown'
                    df[col] = df[col].fillna(mode_val)
            
            # Check infinite values only for numeric columns
            if df[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                try:
                    inf_count = np.isinf(df[col]).sum()
                    if inf_count > 0:
                        print(f"Warning: {col} still has {inf_count} infinite values")
                        df[col] = df[col].replace([np.inf, -np.inf], df[col].median())
                except TypeError:
                    continue

def encode_categorical_features(df, feature_columns):
    """Handle categorical features with Label Encoding."""
    print("Processing categorical features...")
    categorical_features = ['grade', 'sub_grade', 'home_ownership', 'purpose', 'addr_state', 'verification_status']
    available_categorical = [col for col in categorical_features if col in df.columns]
    label_encoders = {}
    
    if available_categorical:
        for col in available_categorical:
            if col in df.columns:
                # Fill missing values with 'Unknown'
                df[col] = df[col].fillna('Unknown')
                
                # Label encode categorical variables
                le = LabelEncoder()
                df[col + '_encoded'] = le.fit_transform(df[col].astype(str))
                label_encoders[col] = le
                
                # Add encoded column to feature list
                feature_columns.append(col + '_encoded')
                
                # Remove original categorical column from feature list
                if col in feature_columns:
                    feature_columns.remove(col)
                
                print(f"  - {col}: {len(le.classes_)} categories encoded")
    
    return feature_columns, label_encoders

def preprocess_training_data(df):
    """Complete preprocessing pipeline for training data."""
    # Get initial feature list
    essential_features = get_essential_features()
    feature_columns = [col for col in essential_features if col in df.columns]
    
    print(f"Essential features requested: {len(essential_features)}")
    print(f"Available features in dataset: {len(feature_columns)}")
    print(f"Initial features: {feature_columns[:10]}...")
    
    # Process raw fields
    df = preprocess_raw_fields(df)
    
    # Update feature columns with parsed versions
    feature_columns = update_feature_columns_with_parsed(feature_columns, df)
    
    # Add engineered features
    feature_columns = add_engineered_features(df, feature_columns)
    
    # Handle missing and infinite values
    handle_missing_and_infinite_values(df, feature_columns)
    
    # Encode categorical features
    feature_columns, label_encoders = encode_categorical_features(df, feature_columns)
    
    print(f"Final feature count: {len(feature_columns)}")
    print(f"Final features: {feature_columns[:15]}...")
    
    return df, feature_columns, label_encoders