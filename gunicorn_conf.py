import multiprocessing


def _calculate_workers() -> int:
    cpu_count = multiprocessing.cpu_count()
    return max(1, min((cpu_count * 2) + 1, 5))


bind = "0.0.0.0:8000"
workers = _calculate_workers()
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
