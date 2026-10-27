from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured
from segments.services_delivery import dispatch_email_actions

class Command(BaseCommand):
    help="Preview queued email actions; sending requires --send and ACTION_DELIVERY_ENABLED=true."
    def add_arguments(self,p):
        p.add_argument("--send",action="store_true",help="Actually submit eligible email actions to the configured SMTP provider.")
        p.add_argument("--limit",type=int,default=100)
    def handle(self,*args,**opts):
        if opts["limit"]<1: raise CommandError("--limit must be positive.")
        try: result=dispatch_email_actions(limit=opts["limit"],dry_run=not opts["send"])
        except ImproperlyConfigured as exc: raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{'Delivery' if opts['send'] else 'Dry run'} summary: {result}"))
