from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import ActionOutcome, ActionOutcomeEvent, Consent, Customer
from .services import transition_action_outcome

def dispatch_email_actions(limit=100,dry_run=True):
    """Dry-run by default. Sending requires an explicit CLI flag and configured SMTP."""
    if not dry_run:
        if not settings.ACTION_DELIVERY_ENABLED: raise ImproperlyConfigured("Set ACTION_DELIVERY_ENABLED=true only after approving and configuring email delivery.")
        if not settings.EMAIL_HOST or "smtp" not in settings.EMAIL_BACKEND.lower(): raise ImproperlyConfigured("An SMTP email backend and EMAIL_HOST are required for delivery.")
    result={"eligible":0,"sent":0,"suppressed":0,"failed":0,"skipped_non_email":0}
    ids=list(ActionOutcome.objects.filter(status="recommended").order_by("recommended_at","id").values_list("id",flat=True)[:limit])
    for outcome_id in ids:
        with transaction.atomic():
            outcome=ActionOutcome.objects.select_for_update().select_related("customer","action").get(pk=outcome_id)
            if outcome.status!="recommended": continue
            if outcome.action.channel!="email": result["skipped_non_email"]+=1; continue
            Customer.objects.select_for_update().get(pk=outcome.customer_id)
            now=timezone.now()
            consent=Consent.objects.filter(customer=outcome.customer,channel="email",effective_from__lte=now).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=now)).order_by("-effective_from").first()
            if not consent or not consent.is_allowed:
                if not dry_run: transition_action_outcome(outcome.id,"suppressed",notes="consent_missing_or_withdrawn")
                result["suppressed"]+=1; continue
            result["eligible"]+=1
            if dry_run: continue
            message=EmailMultiAlternatives(subject=outcome.action.name,body=outcome.action.description,from_email=settings.DEFAULT_FROM_EMAIL,to=[outcome.customer.email],headers={"X-Customer-Signals-Action":outcome.id})
            try:
                sent=message.send(fail_silently=False)
                if sent!=1: raise RuntimeError("Email backend did not confirm a send.")
                transition_action_outcome(outcome.id,"sent",notes="Email provider accepted message",provider_reference=outcome.id)
                result["sent"]+=1
            except Exception as exc:
                ActionOutcomeEvent.objects.create(outcome=outcome,from_status="recommended",to_status="recommended",notes=f"Delivery attempt failed ({type(exc).__name__}); retry after checking provider logs.")
                result["failed"]+=1
    return result
