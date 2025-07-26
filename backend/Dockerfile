FROM python:3.11-slim

WORKDIR /app

# 可选国内源
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 关键：把代码放进 /app/backend 这个包目录
COPY . /app/backend

# 若没有则创建包标识文件（保险）
RUN touch /app/backend/__init__.py

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# 以包导入，配合相对导入使用
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]