import json
from django.core.management.base import BaseCommand
from segments.services import run_recommendations

class Command(BaseCommand):
    help="Run consent- and cooldown-gated action recommendations synchronously."
    def handle(self,*args,**options): self.stdout.write(json.dumps(run_recommendations(),indent=2))
