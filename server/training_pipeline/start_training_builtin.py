# Alternative training using SageMaker's built-in scikit-learn container
import sagemaker
import boto3
import os
from sagemaker.sklearn.estimator import SKLearn

# Configuration
aws_account_id = os.environ.get("AWS_ACCOUNT_ID", "291688974126")
aws_region = os.environ.get("AWS_REGION", "eu-north-1")
sagemaker_role_name = "SageMakerExecutionRoleForLoanProject"
s3_bucket_name = "loanevaluator-raw-data"

# Get SageMaker session and IAM role
sagemaker_session = sagemaker.Session()
iam_client = boto3.client('iam')
role_arn = iam_client.get_role(RoleName=sagemaker_role_name)['Role']['Arn']

# Define S3 paths
s3_input_path = f's3://{s3_bucket_name}/'
s3_output_path = f's3://{s3_bucket_name}/models/'

# Create SKLearn estimator using SageMaker's built-in container
sklearn_estimator = SKLearn(
    entry_point='train.py',
    source_dir=os.path.join(os.path.dirname(__file__), 'src'),
    framework_version='0.23-1',
    py_version='py3',
    role=role_arn,
    instance_type='ml.m5.xlarge',
    instance_count=1,
    output_path=s3_output_path,
    sagemaker_session=sagemaker_session,
    hyperparameters={
        'n-estimators': 150,
        'data-file': 'loan_sample_10k.csv'
    }
)

# Start training
try:
    print("Starting SageMaker training job using built-in scikit-learn container...")
    print(f"Data source: {s3_input_path}")
    print(f"Model output path: {s3_output_path}")
    
    sklearn_estimator.fit({'training': s3_input_path}, wait=False)
    
    print("\nTraining job started successfully!")
    print(f"Job name: {sklearn_estimator.latest_training_job.name}")
    print(f"Monitor progress in AWS SageMaker console for region '{aws_region}'")
    
except Exception as e:
    print(f"Error starting training job: {e}")