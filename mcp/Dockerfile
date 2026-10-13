FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
RUN mkdir -p /data && chown -R 65532:65532 /data
USER 65532
EXPOSE 8000
CMD ["python", "server.py"]
