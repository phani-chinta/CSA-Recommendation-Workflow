import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from celery import shared_task
from django.db.models import F
from .models import WorkflowRun

logger=logging.getLogger(__name__)

@shared_task(name="segments.execute_workflow")
def execute_workflow(run_id):
    now=timezone.now()
    claimed=WorkflowRun.objects.filter(pk=run_id,status="queued").update(status="running",started_at=now,attempts=F("attempts")+1)
    if not claimed: return {"status":"already_claimed"}
    run=WorkflowRun.objects.get(pk=run_id)
    try:
        from .services import rebuild_segments,run_recommendations
        result=rebuild_segments() if run.operation=="segment" else run_recommendations()
        WorkflowRun.objects.filter(pk=run_id).update(status="succeeded",result=result,finished_at=timezone.now())
        return {"status":"succeeded","result":result}
    except Exception as exc:
        logger.exception("Workflow %s failed",run_id)
        WorkflowRun.objects.filter(pk=run_id).update(status="failed",error=f"{type(exc).__name__}; inspect worker logs for run {run_id}."[:4000],finished_at=timezone.now())
        return {"status":"failed"}

def requeue_stale_workflows(older_than_minutes=45,max_attempts=3):
    now=timezone.now(); stale=WorkflowRun.objects.filter(status="running",started_at__lt=now-timedelta(minutes=older_than_minutes))
    failed=stale.filter(attempts__gte=max_attempts).update(status="failed",finished_at=now,error="Worker lease expired after retry limit.")
    ids=list(stale.filter(attempts__lt=max_attempts).values_list("id",flat=True))
    with transaction.atomic():
        WorkflowRun.objects.filter(id__in=ids,status="running").update(status="queued",started_at=None,error="Recovered stale worker lease; requeued.")
        for stale_id in ids: transaction.on_commit(lambda run_id=stale_id: execute_workflow.delay(str(run_id)))
    return {"requeued":len(ids),"failed":failed}

@shared_task(name="segments.recover_stale_workflows")
def recover_stale_workflows(): return requeue_stale_workflows()
