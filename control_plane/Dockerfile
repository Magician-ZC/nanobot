# 构建上下文应为 control_plane/ 的父目录
# 用法: docker build -f control_plane/Dockerfile .
# 或通过 docker-compose.yml 自动处理

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# 复制 Python 包和配套文件
COPY control_plane/ /app/control_plane/

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.20.0" \
    "python-jose[cryptography]>=3.3.0" \
    "bcrypt>=4.0.0" \
    "aiosqlite>=0.19.0" \
    "pydantic>=2.12.0,<3.0.0" \
    "loguru>=0.7.3,<1.0.0" \
    "lark-oapi>=1.5.0,<2.0.0" \
    "websockets>=16.0,<17.0"

# 构建前端
WORKDIR /app/control_plane/frontend
RUN npm install && npm run build
WORKDIR /app

RUN mkdir -p /app/data

EXPOSE 8080

ENTRYPOINT ["python", "control_plane/run.py"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
