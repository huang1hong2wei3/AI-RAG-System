# --- 第一阶段：构建环境（负责安装依赖） ---
FROM python:3.10 as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# --- 第二阶段：运行环境（只拷贝必要文件，瘦身） ---
FROM python:3.10-slim

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
