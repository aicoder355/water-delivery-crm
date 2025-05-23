import multiprocessing
import os

# Базовые настройки
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"  # Используем Uvicorn для лучшей производительности
worker_connections = 1000
timeout = 120  # Увеличиваем таймаут для длительных операций
keepalive = 5

# Настройки для работы с SQLite
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 30
forwarded_allow_ips = "*"

# Логирование
accesslog = "./logs/gunicorn-access.log"
errorlog = "./logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Рабочие настройки
preload_app = True
reload = False
worker_tmp_dir = "/dev/shm"  # Используем tmpfs для временных файлов
threads = 4  # Включаем многопоточность

# Очистка и безопасность
daemon = False
pidfile = "./gunicorn.pid"
umask = 0o007
user = None
group = None

def on_starting(server):
    """Создаем директорию для логов при запуске"""
    if not os.path.exists("logs"):
        os.makedirs("logs")
