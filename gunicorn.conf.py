import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = max(1, min(4, int(os.environ.get("WEB_CONCURRENCY", "1"))))
threads = max(1, min(16, int(os.environ.get("GUNICORN_THREADS", "8"))))
timeout = max(30, int(os.environ.get("GUNICORN_TIMEOUT", "180")))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
if os.path.isdir("/dev/shm"):
    worker_tmp_dir = "/dev/shm"
