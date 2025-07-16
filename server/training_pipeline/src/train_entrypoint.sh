#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# 设置SageMaker环境变量（如果没有设置的话）
export SM_MODEL_DIR=${SM_MODEL_DIR:-"/opt/ml/model"}
export SM_CHANNEL_TRAINING=${SM_CHANNEL_TRAINING:-"/opt/ml/input/data/training"}
export SM_CHANNEL_VALIDATION=${SM_CHANNEL_VALIDATION:-"/opt/ml/input/data/validation"}

# 打印环境变量用于调试
echo "Environment variables:"
echo "SM_MODEL_DIR: $SM_MODEL_DIR"
echo "SM_CHANNEL_TRAINING: $SM_CHANNEL_TRAINING"
echo "SM_CHANNEL_VALIDATION: $SM_CHANNEL_VALIDATION"

# 确保目录存在
mkdir -p "$SM_MODEL_DIR"
mkdir -p "$SM_CHANNEL_TRAINING"
mkdir -p "$SM_CHANNEL_VALIDATION"

# 列出可用的文件和目录
echo "Available files and directories:"
echo "Contents of /opt/ml/input/data:"
ls -la /opt/ml/input/data/ || echo "Directory /opt/ml/input/data not found"
echo "Contents of /opt/ml/input/data/training:"
ls -la /opt/ml/input/data/training/ || echo "Directory /opt/ml/input/data/training not found"

# Shift the arguments to the left if the first argument is "train"
if [ "$1" = "train" ]; then
    shift
fi

# Execute the python training script with the remaining arguments
exec python train.py "$@"