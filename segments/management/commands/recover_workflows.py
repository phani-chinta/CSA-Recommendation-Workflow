from django.core.management.base import BaseCommand, CommandError
from segments.tasks import requeue_stale_workflows

class Command(BaseCommand):
    help="Requeue stale worker jobs and fail runs that exceeded the retry limit."
    def add_arguments(self,p): p.add_argument("--older-than-minutes",type=int,default=45); p.add_argument("--max-attempts",type=int,default=3)
    def handle(self,*args,**o):
        if o["older_than_minutes"]<1 or o["max_attempts"]<1: raise CommandError("Recovery limits must be positive.")
        result=requeue_stale_workflows(o["older_than_minutes"],o["max_attempts"])
        self.stdout.write(self.style.SUCCESS(f"Requeued {result['requeued']} stale run(s); marked {result['failed']} failed."))
