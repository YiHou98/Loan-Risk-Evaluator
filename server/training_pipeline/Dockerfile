FROM python:3.11-slim-bullseye

# 设置工作目录
WORKDIR /opt/ml/code

# 复制requirements.txt
COPY requirements.txt .

# 安装依赖 - 使用pip cache and parallel installs for speed
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# 复制源代码
COPY src/ .

# 设置SageMaker环境变量
ENV PYTHONPATH="/opt/ml/code"
ENV SM_MODEL_DIR="/opt/ml/model"
ENV SM_CHANNEL_TRAINING="/opt/ml/input/data/training"
ENV SM_CHANNEL_VALIDATION="/opt/ml/input/data/validation"

# 创建必要的目录
RUN mkdir -p /opt/ml/input/data/training \
    && mkdir -p /opt/ml/input/data/validation \
    && mkdir -p /opt/ml/model \
    && mkdir -p /opt/ml/output

# 确保脚本可执行并修复行结束符
RUN chmod +x train_entrypoint.sh && \
    sed -i 's/\r$//' train_entrypoint.sh

# 使用正确的入口点
ENTRYPOINT ["./train_entrypoint.sh"]