FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制bilibili目录(包括所有子目录)
COPY bilibili/ ./bilibili/

# 复制core模块
COPY core/ ./core/

# 复制应用代码
COPY app.py .

# 创建必要的目录
RUN mkdir -p /app/tasks /app/logs /app/data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]