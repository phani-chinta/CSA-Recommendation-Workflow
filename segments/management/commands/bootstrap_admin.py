import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help="Create or update the first operator from DJANGO_SUPERUSER_* environment variables."
    def handle(self,*args,**opts):
        username=os.environ.get("DJANGO_SUPERUSER_USERNAME"); email=os.environ.get("DJANGO_SUPERUSER_EMAIL",username or ""); password=os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not username or not email or not password: raise CommandError("Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD in the environment.")
        if len(password)<12: raise CommandError("Bootstrap password must be at least 12 characters.")
        User=get_user_model(); user,created=User.objects.get_or_create(username=username,defaults={"email":email})
        try: validate_password(password,user)
        except ValidationError as exc: raise CommandError("Bootstrap password rejected: "+"; ".join(exc.messages)) from exc
        user.email=email; user.is_active=True; user.is_staff=True; user.is_superuser=True; user.set_password(password); user.save()
        self.stdout.write(self.style.SUCCESS("Bootstrap administrator created." if created else "Bootstrap administrator credentials rotated."))
