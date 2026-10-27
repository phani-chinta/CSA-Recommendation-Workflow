import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE","customer360.settings")
app=Celery("customer360")
app.config_from_object("django.conf:settings",namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule={"recover-stale-customer-workflows":{"task":"segments.recover_stale_workflows","schedule":600.0}}
