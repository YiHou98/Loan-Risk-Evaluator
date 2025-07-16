import os
import json
import joblib
import flask
import pandas as pd

# 1. Load the pipeline that was saved during training
# ----------------------------------------------------
def load_pipeline():
    """Loads the entire Scikit-learn pipeline from the model directory."""
    model_path = "/opt/ml/model"
    pipeline_file = os.path.join(model_path, "model_pipeline.joblib")
    print(f"Loading model pipeline from: {pipeline_file}")
    
    # The loaded object is the 'full_pipeline' from your train.py
    pipeline = joblib.load(pipeline_file)
    return pipeline

# 2. Set up the Flask web server
# --------------------------------
app = flask.Flask(__name__)

# Load the pipeline at server startup
pipeline = load_pipeline()
print("Model pipeline loaded successfully.")

@app.route("/ping", methods=["GET"])
def ping():
    """Health check endpoint for SageMaker."""
    # The pipeline object can be checked to see if it is loaded
    health = pipeline is not None
    status = 200 if health else 404
    return flask.Response(response="\n", status=status, mimetype="application/json")

@app.route("/invocations", methods=["POST"])
def invoke():
    """Endpoint for making predictions."""
    try:
        # Get data from the POST request
        # SageMaker sends data as application/json
        content_type = flask.request.content_type
        if content_type == 'application/json':
            data = flask.request.get_json()
            # Convert the JSON data into a Pandas DataFrame.
            # Your pipeline's first step expects a DataFrame.
            df = pd.DataFrame([data]) 
        else:
            return flask.Response(
                response=f"Unsupported content type: {content_type}",
                status=415,
                mimetype="text/plain",
            )
            
        print(f"Received data for prediction: \n{df.to_string()}")
        
        # 3. Use the loaded pipeline to make a prediction
        # -------------------------------------------------
        # The pipeline will automatically apply all the steps:
        # - apply_feature_engineering
        # - SimpleImputer and OneHotEncoder
        # - RandomForestRegressor.predict()
        prediction = pipeline.predict(df)
        
        # The prediction is a numpy array, convert it to a list for JSON serialization
        result = {"predicted_interest_rate": prediction.tolist()}
        
        print(f"Prediction result: {result}")
        
        # Return the prediction as a JSON response
        return flask.jsonify(result)

    except Exception as e:
        # If anything goes wrong, return an error message.
        print(f"Error during invocation: {e}")
        return flask.Response(
            response=str(e), status=500, mimetype="text/plain"
        )