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
secret_name = 'loan-evaluator/anthropic-api-key'  # AWS Secrets Manager secret name

# Get the latest training job name dynamically
sagemaker_client = boto3.client('sagemaker', region_name=aws_region)

def get_secret(secret_name, region_name):
    """Retrieve secret from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name=region_name)
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        raise

# Get API key from Secrets Manager
print(f"Retrieving API key from Secrets Manager: {secret_name}")
anthropic_api_key = get_secret(secret_name, aws_region)

def get_latest_training_job():
    """Get the most recent training job and wait for completion if needed"""
    try:
        # First get the most recent training job regardless of status
        response = sagemaker_client.list_training_jobs(
            SortBy='CreationTime',
            SortOrder='Descending',
            MaxResults=1
        )
        
        if not response['TrainingJobSummaries']:
            raise Exception("No training jobs found")
        
        job_name = response['TrainingJobSummaries'][0]['TrainingJobName']
        job_status = response['TrainingJobSummaries'][0]['TrainingJobStatus']
        
        print(f"Found training job: {job_name}, Status: {job_status}")
        
        if job_status == 'Completed':
            return job_name
        elif job_status in ['InProgress', 'Stopping']:
            print(f"Training job is {job_status}. Waiting for completion...")
            # Wait for job completion
            waiter = sagemaker_client.get_waiter('training_job_completed_or_stopped')
            waiter.wait(TrainingJobName=job_name)
            
            # Check final status
            final_response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
            final_status = final_response['TrainingJobStatus']
            
            if final_status == 'Completed':
                print(f"Training job completed successfully!")
                return job_name
            else:
                raise Exception(f"Training job failed with status: {final_status}")
        else:
            raise Exception(f"Training job in unexpected status: {job_status}")
            
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

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("WARNING: anthropic library not available, using fallback explanations")

# Simple embedded policies for RAG
POLICIES = {
    "credit_policy": "Maximum DTI for personal loans: 43%. Prime rate eligibility: 720+ credit score.",
    "risk_guidelines": "HIGH RISK (Rate: Base + 3-5%): Credit <650, DTI >40%. LOW RISK (Rate: Base + 0-1%): Credit >720, DTI <30%."
}

def explain_interest_rate(loan_data, interest_rate):
    """Generate explanation for interest rate"""
    if not ANTHROPIC_AVAILABLE:
        # Fallback explanation without Anthropic
        dti = loan_data.get('dti', 0)
        income = loan_data.get('annual_inc', 0)
        loan_amt = loan_data.get('loan_amnt', 0)
        
        # Define risk thresholds based on business rules
        high_risk_rate_threshold = 12.0  # Above 12% is high rate
        low_risk_rate_threshold = 8.0    # Below 8% is low rate
        
        if dti > 40:
            if interest_rate > high_risk_rate_threshold:
                return f"Your {interest_rate:.2f}% rate is appropriate for higher risk profile (DTI: {dti:.1f}% above 40% threshold)."
            else:
                return f"Your {interest_rate:.2f}% rate is favorable despite higher DTI of {dti:.1f}% - possibly due to other strong factors."
        elif dti < 20:
            if interest_rate < low_risk_rate_threshold:
                return f"Your excellent {interest_rate:.2f}% rate reflects low risk with DTI of {dti:.1f}% (well below 20%)."
            else:
                return f"Your {interest_rate:.2f}% rate is higher than expected for low DTI of {dti:.1f}% - other risk factors may apply."
        else:
            return f"Your {interest_rate:.2f}% rate reflects moderate risk with DTI of {dti:.1f}% (standard range)."
    
    try:
        # Try environment variable first, then Secrets Manager
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            try:
                import boto3
                secrets_client = boto3.client('secretsmanager')
                response = secrets_client.get_secret_value(SecretId='loan-evaluator/anthropic-api-key')
                api_key = response['SecretString']
            except Exception as e:
                return f"Interest rate: {interest_rate:.2f}%. Could not retrieve API key: {str(e)}"
        
        if not api_key:
            return f"Interest rate: {interest_rate:.2f}%. API key not configured for detailed explanation."
        
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""Based on loan policies, explain this {interest_rate:.2f}% interest rate.
        
        Loan: ${loan_data.get('loan_amnt', 0):,}, Income: ${loan_data.get('annual_inc', 0):,}, DTI: {loan_data.get('dti', 0):.1f}%
        
        Policies: {POLICIES['risk_guidelines']}
        
        Provide 1-2 sentences explaining the rate."""
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    except Exception as e:
        return f"Your {interest_rate:.2f}% rate reflects standard risk assessment. (Fallback: {str(e)})"

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
    """Make prediction with explanation"""
    model = model_dict["model"]
    feature_names = model_dict["feature_names"]
    
    # Store original data for explanation
    original_data = input_data.iloc[0].to_dict()
    
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
        interest_rate = float(pred_value)
        explanation = explain_interest_rate(original_data, interest_rate)
        return {
            "interest_rate": interest_rate,
            "explanation": explanation,
            "model_version": "v1.0-with-rag",
            "anthropic_available": ANTHROPIC_AVAILABLE
        }
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

print(f"📝 Inference script written to: {temp_inference_path}")
print(f"🔍 Script contains RAG functions: {'explain_interest_rate' in simple_inference_script}")
print(f"🔍 Script contains anthropic import: {'import anthropic' in simple_inference_script}")

try:
    # Create the model without dependencies - embed API key directly in script
    sklearn_model = SKLearnModel(
        model_data=f"s3://loanevaluator-raw-data/models/{training_job_name}/output/model.tar.gz",
        role=role_arn,
        entry_point=temp_inference_path,
        framework_version='1.0-1',
        py_version='py3',
        env={'ANTHROPIC_API_KEY': anthropic_api_key}
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
        # Update existing endpoint without waiting
        predictor = sklearn_model.deploy(
            initial_instance_count=1,
            instance_type='ml.m5.large',
            endpoint_name=endpoint_name,
            update_endpoint=True,
            wait=False  # Don't wait for deployment to complete
        )
    else:
        print(f"Creating new endpoint: {endpoint_name}")
        # Create new endpoint without waiting
        predictor = sklearn_model.deploy(
            initial_instance_count=1,
            instance_type='ml.m5.large',
            endpoint_name=endpoint_name,
            wait=False  # Don't wait for deployment to complete
        )
    
    print(f"Model deployment initiated!")
    print(f"Endpoint name: {endpoint_name}")
    print(f"Deployment will continue in background. Check AWS SageMaker console for status.")
    print(f"Endpoint will be ready in 5-8 minutes.")
    
except Exception as e:
    print(f"Error during deployment: {e}")
finally:
    # Clean up temp file
    if os.path.exists(temp_inference_path):
        os.unlink(temp_inference_path)