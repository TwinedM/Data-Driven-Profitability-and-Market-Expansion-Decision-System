FROM python:3.11-slim
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY app/data/amazon_sales.csv ./amazon_sales.csv
RUN mkdir -p /app/outputs
ENV PORT=5000
EXPOSE 5000
CMD ["python", "app/dashboard.py"]
