import boto3
import time

# Initialize SageMaker client
sagemaker_client = boto3.client('sagemaker', region_name='eu-north-1')

# List all endpoints
try:
    response = sagemaker_client.list_endpoints()
    endpoints = response['Endpoints']
    
    for endpoint in endpoints:
        endpoint_name = endpoint['EndpointName']
        if 'loan-risk-predictor' in endpoint_name:
            print(f"Deleting endpoint: {endpoint_name}")
            try:
                sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
                print(f"Deleted endpoint: {endpoint_name}")
            except Exception as e:
                print(f"Error deleting endpoint {endpoint_name}: {e}")
    
    # List all endpoint configs
    response = sagemaker_client.list_endpoint_configs()
    configs = response['EndpointConfigs']
    
    for config in configs:
        config_name = config['EndpointConfigName']
        if 'loan-risk-predictor' in config_name:
            print(f"Deleting endpoint config: {config_name}")
            try:
                sagemaker_client.delete_endpoint_config(EndpointConfigName=config_name)
                print(f"Deleted endpoint config: {config_name}")
            except Exception as e:
                print(f"Error deleting endpoint config {config_name}: {e}")
    
    print("Cleanup completed!")
    
except Exception as e:
    print(f"Error during cleanup: {e}")