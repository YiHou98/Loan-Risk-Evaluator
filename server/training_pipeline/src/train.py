import os
import sys
import argparse

# Install required packages if not available
try:
    import pandas as pd
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import LabelEncoder
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Installing packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "numpy", "scikit-learn", "joblib"])
    
    # Try importing again
    import pandas as pd
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import LabelEncoder

import utils

def main():
    parser = argparse.ArgumentParser()
    
    # SageMaker specific arguments - 这些会被忽略，我们强制使用SageMaker路径
    parser.add_argument('--model-dir', type=str, default='/opt/ml/model')
    parser.add_argument('--train', type=str, default='/opt/ml/input/data/training')
    parser.add_argument('--validation', type=str, default='/opt/ml/input/data/validation')
    
    # Model hyperparameters
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--data-file', type=str, default='loan_sample_10k.csv')
    
    # 解析参数但强制覆盖路径
    args, unknown_args = parser.parse_known_args()
    
    # 强制使用SageMaker路径，完全忽略命令行传入的路径
    args.model_dir = '/opt/ml/model'
    args.train = '/opt/ml/input/data/training'
    args.validation = '/opt/ml/input/data/validation'
    
    # 打印调试信息
    print(f"Training arguments: {args}")
    if unknown_args:
        print(f"Warning: Unknown arguments ignored: {unknown_args}")
    print(f"Environment variables:")
    print(f"  SM_MODEL_DIR: {os.environ.get('SM_MODEL_DIR', 'Not set')}")
    print(f"  SM_CHANNEL_TRAINING: {os.environ.get('SM_CHANNEL_TRAINING', 'Not set')}")
    print(f"  SM_CHANNEL_VALIDATION: {os.environ.get('SM_CHANNEL_VALIDATION', 'Not set')}")
    
    print("Starting training job...")
    
    print(f"Model directory: {args.model_dir}")
    print(f"Training directory: {args.train}")
    
    # 检查目录是否存在
    if not os.path.exists(args.train):
        print(f"Error: Training directory {args.train} does not exist")
        print("Available directories in /opt/ml:")
        for root, dirs, files in os.walk('/opt/ml'):
            level = root.replace('/opt/ml', '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            sub_indent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{sub_indent}{file}")
        sys.exit(1)
    
    # 尝试找到数据文件
    data_file_path = os.path.join(args.train, args.data_file)
    
    if not os.path.exists(data_file_path):
        print(f"Error: Data file not found at {data_file_path}")
        print(f"Available files in {args.train}:")
        try:
            files = os.listdir(args.train)
            if not files:
                print("  No files found in training directory")
            else:
                for file in files:
                    file_path = os.path.join(args.train, file)
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        print(f"  - {file} ({size} bytes)")
                    else:
                        print(f"  - {file}/ (directory)")
                        # If it's a directory, list its contents too
                        try:
                            subfiles = os.listdir(file_path)
                            for subfile in subfiles:
                                subfile_path = os.path.join(file_path, subfile)
                                if os.path.isfile(subfile_path):
                                    subsize = os.path.getsize(subfile_path)
                                    print(f"    - {subfile} ({subsize} bytes)")
                                else:
                                    print(f"    - {subfile}/ (subdirectory)")
                        except Exception as se:
                            print(f"    Error listing subdirectory: {se}")
        except Exception as e:
            print(f"  Error listing files: {e}")
        
        # Also check if the file exists with a different name
        print(f"\nLooking for files containing 'loan' in the name:")
        try:
            for root, dirs, files in os.walk(args.train):
                for file in files:
                    if 'loan' in file.lower():
                        full_path = os.path.join(root, file)
                        size = os.path.getsize(full_path)
                        rel_path = os.path.relpath(full_path, args.train)
                        print(f"  Found: {rel_path} ({size} bytes)")
        except Exception as e:
            print(f"  Error searching for loan files: {e}")
        
        sys.exit(1)
    
    print(f"Loading data from: {data_file_path}")
    
    try:
        # Load the data
        df = pd.read_csv(data_file_path)
        print(f"Data loaded successfully. Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        
        # Basic data preprocessing
        # Predicting 'int_rate' (interest rate) using other features
        if 'int_rate' not in df.columns:
            print("Error: 'int_rate' column not found in the data")
            print(f"Available columns: {df.columns.tolist()}")
            sys.exit(1)
        
        # Use utils.py preprocessing pipeline
        df, feature_columns, label_encoders = utils.preprocess_training_data(df)
        
        # Final data preparation and validation
        X = df[feature_columns]
        y = df['int_rate']
        
        # Check for any remaining issues
        if X.shape[0] == 0:
            print("Error: No data rows found")
            sys.exit(1)
        
        if X.shape[1] == 0:
            print("Error: No feature columns found")
            sys.exit(1)
        
        print(f"Final training data shape: {X.shape}")
        print(f"Target variable (int_rate) stats: mean={y.mean():.2f}, std={y.std():.2f}, range=[{y.min():.2f}, {y.max():.2f}]")
        
        # Check for any NaN or infinite values in final data
        nan_count = X.isnull().sum().sum()
        inf_count = np.isinf(X.select_dtypes(include=[np.number])).sum().sum()
        if nan_count > 0 or inf_count > 0:
            print(f"Warning: Found {nan_count} NaN and {inf_count} infinite values in final features")
            # Final cleanup
            X = X.fillna(X.median())
            X = X.replace([np.inf, -np.inf], X.median())
        
        # Split the data after all preprocessing (no stratify for regression)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        print(f"Training set size: {X_train.shape[0]}")
        print(f"Test set size: {X_test.shape[0]}")
        
        # Train the model with better hyperparameters
        print(f"Training Random Forest Regressor with {args.n_estimators} estimators...")
        model = RandomForestRegressor(
            n_estimators=max(args.n_estimators, 200),  # Minimum 200 estimators
            max_depth=15,                              # Limit depth to prevent overfitting
            min_samples_split=5,                       # Require at least 5 samples to split
            min_samples_leaf=2,                        # Minimum 2 samples per leaf
            random_state=42,
            n_jobs=-1  # Use all available CPUs
        )
        
        model.fit(X_train, y_train)
        
        # Evaluate the model
        y_pred = model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"Model training completed!")
        print(f"Test MSE: {mse:.4f}")
        print(f"Test MAE: {mae:.4f}")
        print(f"Test R² Score: {r2:.4f}")
        print(f"Mean interest rate: {y.mean():.4f}")
        print(f"Std interest rate: {y.std():.4f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        print("\nTop 10 Most Important Features:")
        print(feature_importance.head(10))
        
        # Create model directory if it doesn't exist
        os.makedirs(args.model_dir, exist_ok=True)
        
        # Save the model to the SageMaker model directory
        model_path = os.path.join(args.model_dir, 'model.joblib')
        joblib.dump(model, model_path)
        
        # Save feature names for inference
        feature_names_path = os.path.join(args.model_dir, 'feature_names.joblib')
        joblib.dump(feature_columns, feature_names_path)
        
        # Save feature importance
        feature_importance_path = os.path.join(args.model_dir, 'feature_importance.joblib')
        joblib.dump(feature_importance, feature_importance_path)
        
        # Save label encoders for categorical features
        if label_encoders:
            encoders_path = os.path.join(args.model_dir, 'label_encoders.joblib')
            joblib.dump(label_encoders, encoders_path)
            print(f"Label encoders saved: {list(label_encoders.keys())}")
        
        # Save model metadata
        metadata = {
            'n_estimators': max(args.n_estimators, 200),
            'mse': mse,
            'mae': mae,
            'r2_score': r2,
            'feature_columns': feature_columns,
            'categorical_features': list(label_encoders.keys()),
            'model_type': 'RandomForestRegressor',
            'data_shape': df.shape,
            'target_mean': y.mean(),
            'target_std': y.std(),
            'target_range': [y.min(), y.max()],
            'model_params': {
                'max_depth': 15,
                'min_samples_split': 5,
                'min_samples_leaf': 2
            }
        }
        metadata_path = os.path.join(args.model_dir, 'metadata.joblib')
        joblib.dump(metadata, metadata_path)
        
        print(f"\nModel artifacts saved:")
        print(f"  - Model: {model_path}")
        print(f"  - Feature names: {feature_names_path}")
        print(f"  - Feature importance: {feature_importance_path}")
        print(f"  - Metadata: {metadata_path}")
        
        # List contents of model directory for debugging
        print(f"\nContents of {args.model_dir}:")
        for item in os.listdir(args.model_dir):
            item_path = os.path.join(args.model_dir, item)
            if os.path.isfile(item_path):
                size = os.path.getsize(item_path)
                print(f"  - {item} ({size} bytes)")
            else:
                print(f"  - {item}/ (directory)")
        
        print(f"\nTraining completed successfully!")
        
        # Write success indicator
        success_file = os.path.join(args.model_dir, 'SUCCESS')
        with open(success_file, 'w') as f:
            f.write('Training completed successfully')
        
    except Exception as e:
        print(f"Error during training: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        # Write failure indicator with detailed error
        try:
            os.makedirs(args.model_dir, exist_ok=True)
            failure_file = os.path.join(args.model_dir, 'FAILURE')
            with open(failure_file, 'w') as f:
                f.write(f'Training failed: {str(e)}\n')
                f.write(f'Error type: {type(e).__name__}\n')
                f.write('Full traceback:\n')
                traceback.print_exc(file=f)
        except Exception as write_error:
            print(f"Could not write failure file: {write_error}")
        
        sys.exit(1)

if __name__ == '__main__':
    main()
    