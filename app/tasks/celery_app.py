try:
    from celery import Celery
except ImportError:
    Celery = None  # type: ignore

from app.core.config import settings

if Celery is not None:
    celery_app = Celery(
        "autoincc_tasks",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=["app.tasks.etl_tasks"],
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="America/Sao_Paulo",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=1800,  # 30 minutes hard timeout
        task_soft_time_limit=1500,  # 25 minutes soft timeout
        worker_prefetch_multiplier=1,  # Fair task distribution
    )
else:
    class DummyCelery:
        """Dummy Celery mock when celery package is not installed on host."""
        conf = {}
        def task(self, *args, **kwargs):
            def decorator(func):
                func.delay = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Celery is not installed."))
                return func
            return decorator

    celery_app = DummyCelery()
