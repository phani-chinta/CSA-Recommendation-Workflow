FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt
COPY . .
RUN chmod +x /app/docker/entrypoint.sh && mkdir -p /app/staticfiles && chown -R 10001:10001 /app
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn","customer360.wsgi:application","--bind","0.0.0.0:8000","--workers","3","--timeout","180","--access-logfile","-","--error-logfile","-"]
