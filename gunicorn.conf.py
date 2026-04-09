"""Gunicorn configuration for the health analytic service."""

bind = "0.0.0.0:8000"
workers = 3          # 2 * CPU + 1 as baseline
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"
