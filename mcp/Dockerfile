FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY server.py gateway.py routing.py ./
RUN chmod -R a+rX /app && mkdir -p /data && chown 65532:65532 /data
USER 65532
EXPOSE 8000
CMD ["python", "server.py"]
