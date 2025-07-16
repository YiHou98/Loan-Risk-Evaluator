# training_pipeline/deploy.py

import sagemaker
import os

# --- 1. 配置信息 ---

# 您需要部署哪一个训练任务的产出？
# 请从AWS SageMaker控制台的“训练任务”页面复制一个已成功的任务名称
# 例如: 'loan-risk-training-2025-07-14-14-45-30-751'
training_job_name = 'sagemaker-scikit-learn-2025-07-15-15-51-55-008'
# 为您即将创建的API服务（Endpoint）命名
endpoint_name = 'loan-risk-predictor-endpoint'

# 为Endpoint配置服务器实例
# 对于推理任务，通常不需要很强的算力，t2.medium是一个性价比较高的选择
instance_type = 'ml.m5.large'

# --- 2. 附加到已完成的训练任务 ---
try:
    print(f"Attempting to attach to existing training job: {training_job_name}")
    
    # sagemaker.estimator.Estimator.attach() 是一个非常强大的功能
    # 它可以“连接”到一个已经完成的训练任务，并获取它的所有信息
    estimator = sagemaker.estimator.Estimator.attach(training_job_name)
    
    print("Successfully attached to the training job.")

    # --- 3. 部署模型！ ---
    # 调用.deploy()方法，SageMaker会自动完成以下所有事情：
    # 1. 创建一个“模型(Model)”资源，指向S3中的模型文件和ECR中的推理镜像
    # 2. 创建一个“Endpoint配置(Endpoint Configuration)”，定义服务器类型
    # 3. 创建“终端节点(Endpoint)”，启动服务器并部署模型服务
    print(f"\nDeploying model to a new endpoint named: {endpoint_name}")
    print(f"This will take several minutes...")
    
    predictor = estimator.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name
    )
    
    print(f"\nDeployment successful!")
    print(f"Endpoint '{endpoint_name}' is now InService.")
    print(f"Endpoint ARN: {predictor.endpoint_name}")

except Exception as e:
    print(f"\nError during deployment: {e}")