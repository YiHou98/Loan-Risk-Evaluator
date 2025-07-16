import os
import sys
import argparse
import pandas as pd
import numpy as np
import joblib
import tarfile
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# Handle missing utils.py gracefully
try:
    import utils
    print("utils.py imported successfully")
except ImportError:
    print("Warning: utils.py not found. Using placeholder functions.")
    # Create a placeholder utils module
    class Utils:
        @staticmethod
        def placeholder_function():
            return None
    utils = Utils()

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
        
        # Select features to predict interest rate (excluding int_rate as it's our target)
        essential_features = [
            'loan_amnt',          # Loan amount
            'funded_amnt',        # Amount funded
            'installment',        # Monthly installment
            'annual_inc',         # Annual income
            'dti',                # Debt-to-income ratio
            'open_acc',           # Number of open accounts
            'pub_rec',            # Number of public records
            'revol_bal',          # Revolving credit balance
            'revol_util',         # Revolving utilization rate
            'total_acc',          # Total number of accounts
            'delinq_2yrs',        # Delinquencies in past 2 years
            'inq_last_6mths'      # Credit inquiries in last 6 months
        ]
        
        # Check which features are available in the dataset
        available_features = [col for col in essential_features if col in df.columns]
        feature_columns = available_features
        
        print(f"Essential features requested: {len(essential_features)}")
        print(f"Available features in dataset: {len(feature_columns)}")
        print(f"Selected features: {feature_columns}")
        
        # Handle missing values and infinite values
        print(f"Checking for missing values...")
        missing_counts = df[feature_columns].isnull().sum()
        columns_with_missing = missing_counts[missing_counts > 0]
        if len(columns_with_missing) > 0:
            print(f"Found missing values in {len(columns_with_missing)} columns:")
            for col, count in columns_with_missing.items():
                print(f"  - {col}: {count} missing values")
            
            # Fill missing values with median for numeric columns
            df[feature_columns] = df[feature_columns].fillna(df[feature_columns].median())
            print("Missing values filled with median values")
        
        # Handle infinite values
        print("Checking for infinite values...")
        for col in feature_columns:
            inf_count = np.isinf(df[col]).sum()
            if inf_count > 0:
                print(f"Found {inf_count} infinite values in {col}")
                # Replace infinite values with median
                median_val = df[col].replace([np.inf, -np.inf], np.nan).median()
                df[col] = df[col].replace([np.inf, -np.inf], median_val)
        
        # Final check for any remaining NaN or infinite values
        print("Final data validation...")
        for col in feature_columns:
            nan_count = df[col].isnull().sum()
            inf_count = np.isinf(df[col]).sum()
            if nan_count > 0 or inf_count > 0:
                print(f"Warning: {col} still has {nan_count} NaN and {inf_count} infinite values")
                # Force fill any remaining issues
                df[col] = df[col].fillna(df[col].median())
                df[col] = df[col].replace([np.inf, -np.inf], df[col].median())
        
        X = df[feature_columns]
        y = df['int_rate']
        
        print(f"Features selected: {len(feature_columns)}")
        print(f"Feature columns: {feature_columns[:10]}...")  # Show first 10 features
        print(f"Target variable distribution:")
        print(y.value_counts())
        
        # Check for any remaining issues
        if X.shape[0] == 0:
            print("Error: No data rows found")
            sys.exit(1)
        
        if X.shape[1] == 0:
            print("Error: No feature columns found")
            sys.exit(1)
        
        # Split the data (no stratify for regression)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        print(f"Training set size: {X_train.shape[0]}")
        print(f"Test set size: {X_test.shape[0]}")
        
        # Train the model
        print(f"Training Random Forest Regressor with {args.n_estimators} estimators...")
        model = RandomForestRegressor(
            n_estimators=args.n_estimators,
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
        
        # Save model metadata
        metadata = {
            'n_estimators': args.n_estimators,
            'mse': mse,
            'mae': mae,
            'r2_score': r2,
            'feature_columns': feature_columns,
            'model_type': 'RandomForestRegressor',
            'data_shape': df.shape,
            'target_mean': y.mean(),
            'target_std': y.std(),
            'target_range': [y.min(), y.max()]
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
        import traceback
        traceback.print_exc()
        
        # Write failure indicator
        failure_file = os.path.join(args.model_dir, 'FAILURE')
        with open(failure_file, 'w') as f:
            f.write(f'Training failed: {str(e)}')
        
        sys.exit(1)

if __name__ == '__main__':
    main()