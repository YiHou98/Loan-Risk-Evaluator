#!/usr/bin/env python3
"""
Debug script to test the deployed endpoint and see what it's returning
"""

import boto3
import json
from sagemaker.predictor import Predictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer

def test_endpoint():
    """Test the deployed endpoint"""
    endpoint_name = 'loan-risk-predictor-simple'
    
    print("🧪 Testing SageMaker Endpoint")
    print("=" * 40)
    print(f"📡 Endpoint: {endpoint_name}")
    
    # Create predictor
    predictor = Predictor(
        endpoint_name=endpoint_name,
        serializer=JSONSerializer(),
        deserializer=JSONDeserializer()
    )
    
    # Test data
    test_data = {
        "loan_amnt": 25000,
        "annual_inc": 65000,
        "dti": 18.5,
        "emp_length": "5 years",
        "home_ownership": "MORTGAGE",
        "installment": 750.50,
        "funded_amnt": 25000,
        "open_acc": 8,
        "pub_rec": 0,
        "revol_bal": 12000,
        "revol_util": 45.2,
        "total_acc": 15,
        "delinq_2yrs": 0,
        "inq_last_6mths": 1
    }
    
    print("📋 Input Data:")
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    
    print("\n📤 Sending request...")
    
    try:
        result = predictor.predict(test_data)
        
        print("📥 Response received:")
        print(f"🔍 Raw result: {result}")
        print(f"📊 Result type: {type(result)}")
        
        # Check if it's the new format with explanations
        if isinstance(result, dict):
            if 'interest_rate' in result and 'explanation' in result:
                print("\n✅ NEW FORMAT DETECTED:")
                print(f"🎯 Interest Rate: {result['interest_rate']:.2f}%")
                print(f"💡 Explanation: {result['explanation']}")
                print(f"🔧 Model Version: {result.get('model_version', 'unknown')}")
            elif 'prediction' in result:
                print("\n⚠️  OLD FORMAT DETECTED:")
                print(f"🎯 Prediction: {result['prediction']}")
                print("❌ No explanation found")
            else:
                print(f"\n❓ UNKNOWN FORMAT:")
                print(f"📋 Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        else:
            print(f"\n❓ UNEXPECTED RESULT TYPE: {type(result)}")
            print(f"📋 Content: {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"🔍 Error type: {type(e)}")
        return None

def check_endpoint_config():
    """Check endpoint configuration"""
    print("\n🔧 Checking Endpoint Configuration")
    print("=" * 40)
    
    try:
        sagemaker_client = boto3.client('sagemaker')
        endpoint_name = 'loan-risk-predictor-simple'
        
        # Get endpoint info
        endpoint = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        config_name = endpoint['EndpointConfigName']
        
        print(f"📋 Endpoint Status: {endpoint['EndpointStatus']}")
        print(f"📋 Config Name: {config_name}")
        
        # Get endpoint config
        config = sagemaker_client.describe_endpoint_config(EndpointConfigName=config_name)
        production_variants = config['ProductionVariants']
        
        for variant in production_variants:
            print(f"📋 Model Name: {variant['ModelName']}")
            print(f"📋 Instance Type: {variant['InstanceType']}")
        
        # Get model info
        model_name = production_variants[0]['ModelName']
        model = sagemaker_client.describe_model(ModelName=model_name)
        
        print(f"📋 Model Data: {model['PrimaryContainer'].get('ModelDataUrl', 'N/A')}")
        print(f"📋 Environment Variables: {model['PrimaryContainer'].get('Environment', {})}")
        
    except Exception as e:
        print(f"❌ Error checking config: {e}")

if __name__ == "__main__":
    print("🚀 SageMaker Endpoint Debug Tool")
    print("=" * 50)
    
    # Test the endpoint
    result = test_endpoint()
    
    # Check configuration
    check_endpoint_config()
    
    print("\n📝 Summary:")
    if result and isinstance(result, dict) and 'explanation' in result:
        print("✅ RAG explanations are working!")
    else:
        print("❌ RAG explanations are NOT working")
        print("🔧 Possible issues:")
        print("  - API key not configured in Secrets Manager")
        print("  - SageMaker role lacks Secrets Manager permissions")
        print("  - Model using old inference script")
        print("  - anthropic library not installed")