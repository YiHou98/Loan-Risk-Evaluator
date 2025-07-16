import boto3
import json
import os
import tempfile
from sagemaker.sklearn import SKLearnModel
import sagemaker

# Configuration
aws_region = 'eu-north-1'
role_name = 'SageMakerExecutionRoleForLoanProject'
endpoint_name = 'loan-risk-predictor-simple'

# Get the latest training job name dynamically
sagemaker_client = boto3.client('sagemaker', region_name=aws_region)

def get_latest_training_job():
    """Get the most recent completed training job"""
    try:
        response = sagemaker_client.list_training_jobs(
            SortBy='CreationTime',
            SortOrder='Descending',
            StatusEquals='Completed',
            MaxResults=1
        )
        if response['TrainingJobSummaries']:
            return response['TrainingJobSummaries'][0]['TrainingJobName']
        else:
            raise Exception("No completed training jobs found")
    except Exception as e:
        print(f"Error getting latest training job: {e}")
        raise

training_job_name = get_latest_training_job()
print(f"Using latest training job: {training_job_name}")

# Get IAM role
iam_client = boto3.client('iam')
role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']

# Create a simple inference script that works
simple_inference_script = '''
import joblib
import os
import json
import pandas as pd
import numpy as np

def model_fn(model_dir):
    """Load model from model directory"""
    model = joblib.load(os.path.join(model_dir, 'model.joblib'))
    
    # Try to load feature names if available
    try:
        feature_names = joblib.load(os.path.join(model_dir, 'feature_names.joblib'))
        return {"model": model, "feature_names": feature_names}
    except:
        return {"model": model, "feature_names": None}

def input_fn(request_body, request_content_type='application/json'):
    """Parse input data"""
    if request_content_type == 'application/json':
        input_data = json.loads(request_body)
        return pd.DataFrame([input_data])
    elif request_content_type == 'application/x-npy':
        import numpy as np
        import io
        # Handle numpy array format
        input_data = np.load(io.BytesIO(request_body), allow_pickle=True)
        if isinstance(input_data, dict):
            return pd.DataFrame([input_data])
        else:
            # If it's just an array, create a basic DataFrame
            return pd.DataFrame(input_data)
    else:
        # Default to JSON parsing
        try:
            input_data = json.loads(request_body)
            return pd.DataFrame([input_data])
        except:
            raise ValueError(f"Unsupported content type: {request_content_type}")

def predict_fn(input_data, model_dict):
    """Make prediction"""
    model = model_dict["model"]
    feature_names = model_dict["feature_names"]
    
    # If we have feature names from training, use them to prepare the data
    if feature_names is not None:
        # Create a DataFrame with all expected features, filled with defaults
        prepared_data = pd.DataFrame(columns=feature_names)
        
        # Fill with default values (0 for numeric)
        for col in feature_names:
            prepared_data[col] = [0.0]
        
        # Update with provided values
        for col in input_data.columns:
            if col in feature_names:
                prepared_data[col] = input_data[col].iloc[0]
        
        # Make prediction
        prediction = model.predict(prepared_data)
    else:
        # Fallback: use only numeric columns and hope for the best
        numeric_data = input_data.select_dtypes(include=[np.number]).fillna(0)
        prediction = model.predict(numeric_data)
    
    # Handle both numeric and string predictions
    pred_value = prediction[0]
    if isinstance(pred_value, (int, float)):
        return {"prediction": float(pred_value)}
    else:
        # For string predictions (like loan status), return as string
        return {"prediction": str(pred_value), "prediction_type": "classification"}

def output_fn(prediction, accept='application/json'):
    """Format output"""
    if accept == 'application/json':
        return json.dumps(prediction)
    elif accept == 'application/x-npy':
        import numpy as np
        import io
        # Convert to numpy format
        output = io.BytesIO()
        np.save(output, prediction, allow_pickle=True)
        return output.getvalue()
    else:
        # Default to JSON for any other type
        return json.dumps(prediction)
'''

# Write the simple inference script
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(simple_inference_script)
    temp_inference_path = f.name

try:
    # Create the model
    sklearn_model = SKLearnModel(
        model_data=f"s3://loanevaluator-raw-data/models/{training_job_name}/output/model.tar.gz",
        role=role_arn,
        entry_point=temp_inference_path,
        framework_version='0.23-1',
        py_version='py3'
    )
    
    # Check if endpoint exists and handle accordingly
    def endpoint_exists(endpoint_name):
        try:
            sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
            return True
        except sagemaker_client.exceptions.ClientError:
            return False
    
    if endpoint_exists(endpoint_name):
        print(f"Endpoint {endpoint_name} already exists. Updating with new model...")
        # Update existing endpoint
        predictor = sklearn_model.deploy(
            initial_instance_count=1,
            instance_type='ml.m5.large',
            endpoint_name=endpoint_name,
            update_endpoint=True
        )
    else:
        print(f"Creating new endpoint: {endpoint_name}")
        # Create new endpoint
        predictor = sklearn_model.deploy(
            initial_instance_count=1,
            instance_type='ml.m5.large',
            endpoint_name=endpoint_name
        )
    
    print(f"Model deployed successfully!")
    print(f"Endpoint name: {endpoint_name}")
    
    # Set JSON serializers for testing
    from sagemaker.serializers import JSONSerializer
    from sagemaker.deserializers import JSONDeserializer
    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()
    
    # Test the endpoint with all essential features
    test_data = {
        "loan_amnt": 10000,         # Loan amount
        "funded_amnt": 10000,       # Amount funded
        "installment": 300.25,      # Monthly installment
        "annual_inc": 50000,        # Annual income
        "dti": 18.2,               # Debt-to-income ratio
        "open_acc": 6,             # Number of open accounts
        "pub_rec": 0,              # Number of public records
        "revol_bal": 8500,         # Revolving credit balance
        "revol_util": 55.8,        # Revolving utilization rate
        "total_acc": 12,           # Total number of accounts
        "delinq_2yrs": 0,          # Delinquencies in past 2 years
        "inq_last_6mths": 1        # Credit inquiries in last 6 months
    }
    
    try:
        result = predictor.predict(test_data)
        print(f"Test prediction result: {result}")
    except Exception as e:
        print(f"Test prediction failed: {e}")
    
except Exception as e:
    print(f"Error during deployment: {e}")
finally:
    # Clean up temp file
    if os.path.exists(temp_inference_path):
        os.unlink(temp_inference_path)