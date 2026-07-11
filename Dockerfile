FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 环境变量配置 (运行时传入)
# RESEND_API_KEY, RESEND_FROM_EMAIL
# GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_CSE_ID
# MAX_LOOPS, COST_BUDGET

CMD ["python", "server.py"]
