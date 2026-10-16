FROM python:3.12-slim
WORKDIR /app
COPY --chmod=644 requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY --chmod=644 server.py gateway.py routing.py ./
RUN mkdir -p /data && chown 65532:65532 /data
USER 65532
EXPOSE 8000
CMD ["python", "server.py"]
