import boto3
import json

# Test the endpoint
runtime = boto3.client('sagemaker-runtime', region_name='eu-north-1')
endpoint_name = 'loan-risk-predictor-simple'

# Simple test data
test_data = {
    "loan_amnt": 10000,
    "funded_amnt": 10000,
    "int_rate": 10.5,
    "installment": 300,
    "annual_inc": 50000
}

try:
    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=json.dumps(test_data)
    )
    
    result = json.loads(response['Body'].read().decode())
    print(f"Prediction result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    print("Check the CloudWatch logs for more details:")
    print(f"https://eu-north-1.console.aws.amazon.com/cloudwatch/home?region=eu-north-1#logEventViewer:group=/aws/sagemaker/Endpoints/{endpoint_name}")