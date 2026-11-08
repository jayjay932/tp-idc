FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY datapipeline/ datapipeline/
COPY examples/ examples/
COPY tests/ tests/
RUN useradd --create-home --uid 10001 pipeline && mkdir /app/data && chown pipeline:pipeline /app/data
USER pipeline
ENTRYPOINT ["python", "-m", "datapipeline"]
CMD ["demo", "--source", "s3"]
