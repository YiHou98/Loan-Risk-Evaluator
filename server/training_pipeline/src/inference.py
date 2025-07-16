import os
import joblib
import pandas as pd
import numpy as np

def model_fn(model_dir):
    """Load the model from the model directory."""
    try:
        model_path = os.path.join(model_dir, 'model.joblib')
        feature_names_path = os.path.join(model_dir, 'feature_names.joblib')
        
        model = joblib.load(model_path)
        feature_names = joblib.load(feature_names_path)
        
        return {'model': model, 'feature_names': feature_names}
    except Exception as e:
        raise Exception(f"Error loading model: {str(e)}")

def input_fn(request_body, request_content_type='application/json'):
    """Parse input data for prediction."""
    try:
        if request_content_type == 'application/json':
            import json
            input_data = json.loads(request_body)
            
            # Convert to DataFrame
            if isinstance(input_data, dict):
                # Single prediction
                df = pd.DataFrame([input_data])
            else:
                # Multiple predictions
                df = pd.DataFrame(input_data)
            
            return df
        else:
            raise ValueError(f"Unsupported content type: {request_content_type}")
    except Exception as e:
        raise Exception(f"Error parsing input: {str(e)}")

def predict_fn(input_data, model):
    """Make predictions on the input data."""
    try:
        clf = model['model']
        feature_names = model['feature_names']
        
        # Ensure we have the right features
        missing_features = set(feature_names) - set(input_data.columns)
        if missing_features:
            # Fill missing features with median or 0
            for feature in missing_features:
                input_data[feature] = 0
        
        # Select and reorder features to match training
        input_data = input_data[feature_names]
        
        # Handle any remaining NaN or infinite values
        input_data = input_data.fillna(0)
        input_data = input_data.replace([np.inf, -np.inf], 0)
        
        # Make prediction
        predictions = clf.predict(input_data)
        probabilities = clf.predict_proba(input_data)
        
        return {
            'predictions': predictions.tolist(),
            'probabilities': probabilities.tolist()
        }
    except Exception as e:
        raise Exception(f"Error making prediction: {str(e)}")

def output_fn(prediction, accept='application/json'):
    """Format the prediction output."""
    try:
        if accept == 'application/json':
            import json
            return json.dumps(prediction)
        else:
            raise ValueError(f"Unsupported accept type: {accept}")
    except Exception as e:
        raise Exception(f"Error formatting output: {str(e)}")