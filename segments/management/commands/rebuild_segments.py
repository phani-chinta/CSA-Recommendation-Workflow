import json
from django.core.management.base import BaseCommand
from segments.services import rebuild_segments

class Command(BaseCommand):
    help="Run the segmentation workflow synchronously; intended for managed jobs/operations."
    def handle(self,*args,**options): self.stdout.write(json.dumps(rebuild_segments(),indent=2))
