rom celery import Celery
from app.config import settings

celery_app = Celery(
    "voxflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,

    # Task tracking supaya status "STARTED" (bukan cuma PENDING/SUCCESS/FAILURE)
    # ikut terekam -- berguna untuk debugging lewat Flower/monitoring.
    task_track_started=True,

    # Satu task berat (render FFmpeg / TTS batch) per worker dalam satu waktu.
    # Default Celery prefetch beberapa task sekaligus ke tiap worker, yang
    # bisa bikin satu worker kebanjiran beberapa job render video sekaligus
    # dan gampang OOM. Prefetch=1 memastikan worker ambil task baru HANYA
    # setelah task sebelumnya benar-benar selesai.
    worker_prefetch_multiplier=1,

    # Task baru dianggap "acknowledged" (dihapus dari antrean) HANYA setelah
    # benar-benar selesai dieksekusi -- bukan begitu diterima worker. Kalau
    # worker crash di tengah proses (OOM saat render), task otomatis
    # dikembalikan ke antrean untuk dicoba worker lain, tidak hilang begitu
    # saja.
    task_acks_late=True,

    # Retry otomatis kalau koneksi ke Redis broker belum siap saat startup

    broker_connection_retry_on_startup=True,

    # Batas waktu keras per task -- mencegah task yang macet total
    # (misal FFmpeg hang) memblokir worker selamanya.
    task_time_limit=900,
    task_soft_time_limit=780,
)