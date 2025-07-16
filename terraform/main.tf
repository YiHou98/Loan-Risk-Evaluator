# terraform/main.tf

# 配置AWS Provider
provider "aws" {
  region = "eu-north-1" # 您可以选择任何区域
}

# 1. 创建一个S3存储桶
# 用于存放您的数据集(loan_sample_10k.csv)和模型输出(model_pipeline.joblib)
resource "aws_s3_bucket" "mlops_bucket" {
  bucket = "loanevaluator-raw-data" # <--- 请替换成一个全球唯一的名称
}

# 2. 创建一个ECR镜像仓库
# 用于存放您打包了训练代码的Docker镜像
resource "aws_ecr_repository" "training_repo" {
  name = "loan-risk-training" # 仓库名称
}

# 3. 创建一个给SageMaker使用的IAM角色
# SageMaker需要这个角色来获得访问S3和ECR的权限
resource "aws_iam_role" "sagemaker_execution_role" {
  name = "SageMakerExecutionRoleForLoanProject"

  # 允许SageMaker服务扮演这个角色
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
    }]
  })
}

# 为角色附加AWS托管的策略，以授予权限（为简化项目，我们使用完全访问权限）
resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.sagemaker_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ecr_access" {
  role       = aws_iam_role.sagemaker_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
}