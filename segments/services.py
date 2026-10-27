from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import BigIntegerField, Sum, Count, Max, Q
from django.db.models.functions import Cast, Substr
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Customer, Order, EngagementEvent, SupportCase, SupportCaseEvent, Consent, SegmentRule, SegmentMembership, ActionCatalog, ActionOutcome, ActionSequence, ActionOutcomeEvent, WorkflowLock

@transaction.atomic
def rebuild_segments(as_of=None):
    as_of=as_of or timezone.now(); WorkflowLock.objects.select_for_update().get(pk="customer_workflow"); rules=list(SegmentRule.objects.filter(active=True,effective_from__lte=as_of.date()).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=as_of.date())).order_by("priority","id")); SegmentMembership.objects.filter(is_current=True).update(is_current=False); made=0
    if not rules: raise ValidationError("No active segment rules are effective at the selected time.")
    required={"New","Dormant","High Value","Service Attention","Engaged","Active"}
    by_name={r.name:r for r in rules}
    if not required.issubset(by_name): raise ValidationError(f"Segment rules missing: {', '.join(sorted(required-set(by_name)))}")
    order_stats={x["customer_id"]:x for x in Order.objects.filter(status="completed",ordered_at__lte=as_of).values("customer_id").annotate(spend=Sum("total"),count=Count("id"),last=Max("ordered_at"))}
    engagement_counts=dict(EngagementEvent.objects.filter(occurred_at__gte=as_of-timedelta(days=30),occurred_at__lte=as_of).values("customer_id").annotate(n=Count("id")).values_list("customer_id","n"))
    high_service=set(SupportCase.objects.filter(service_cost__gte=100).values_list("customer_id",flat=True))
    batch=[]
    for c in Customer.objects.all().iterator(chunk_size=2000):
        x=order_stats.get(c.id,{}); engagement=engagement_counts.get(c.id,0)
        spend=x.get("spend") or Decimal("0"); count=x.get("count") or 0; last=x.get("last"); recency=(as_of.date()-last.date()).days if last else 9999
        if c.lifecycle=="new": name,why,score="New","Recently acquired; purchase history is not yet established",0
        elif not last or recency>180: name,why,score="Dormant",f"No completed purchase in {recency} days",0
        elif spend>=1000 and count>=3: name,why,score="High Value",f"${spend:.2f} completed spend across {count} orders",float(spend)
        elif c.id in high_service: name,why,score="Service Attention","At least one support case with service cost >= $100",100
        elif engagement>=2: name,why,score="Engaged",f"{count} completed orders; {engagement} engagement events in the last 30 days",float(spend)+engagement
        else: name,why,score="Active",f"{count} completed orders; last purchase {recency} days ago; {engagement} recent engagement events",float(spend)
        r=by_name[name]; snapshot={"id":r.id,"name":r.name,"description":r.description,"priority":r.priority,"effective_from":r.effective_from.isoformat(),"effective_to":r.effective_to.isoformat() if r.effective_to else None}; batch.append(SegmentMembership(id=f"MEM-{r.id}-{c.id}-{as_of:%Y%m%d%H%M%S%f}",segment=r,customer=c,assigned_at=as_of,reason=why,score=score,rule_snapshot=snapshot)); made+=1
        if len(batch)>=2000: SegmentMembership.objects.bulk_create(batch,batch_size=2000); batch=[]
    if batch: SegmentMembership.objects.bulk_create(batch,batch_size=2000)
    return {"memberships":made,"customers":Customer.objects.count()}

@transaction.atomic
def run_recommendations(as_of=None):
    as_of=as_of or timezone.now(); WorkflowLock.objects.select_for_update().get(pk="customer_workflow"); result={"recommended":0,"suppressed":0}
    memberships=dict(SegmentMembership.objects.filter(is_current=True).values_list("customer_id","segment_id"))
    action_map={}
    for action in ActionCatalog.objects.filter(active=True,effective_from__lte=as_of.date()).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=as_of.date())).order_by("priority"): action_map.setdefault(action.segment_id,[]).append(action)
    consents={}
    qs=Consent.objects.filter(effective_from__lte=as_of).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=as_of)).order_by("customer_id","channel","-effective_from")
    for cns in qs.iterator(chunk_size=5000): consents.setdefault((cns.customer_id,cns.channel),cns.is_allowed)
    max_cooldown=max((a.cooldown_days for group in action_map.values() for a in group),default=0)
    cooldowns={(cid,aid):when for cid,aid,when in ActionOutcome.objects.filter(status__in=["recommended","sending","sent","converted","not_converted"],recommended_at__gte=as_of-timedelta(days=max_cooldown)).order_by("recommended_at").values_list("customer_id","action_id","recommended_at")}
    sequence=ActionSequence.objects.select_for_update().filter(name="action_outcome").first()
    max_seq=ActionOutcome.objects.filter(id__startswith=f"ACTN-{as_of:%Y}-").annotate(sequence_number=Cast(Substr("id",11),BigIntegerField())).aggregate(max_seq=Max("sequence_number"))["max_seq"] or 0
    if sequence is None:
        sequence=ActionSequence.objects.create(name="action_outcome",next_value=max_seq+1)
    else:
        sequence.next_value=max(sequence.next_value,max_seq+1)
    seq=sequence.next_value
    batch=[]
    event_batch=[]
    for customer_id,segment_id in memberships.items():
        for action in action_map.get(segment_id,[]):
            reason="" if consents.get((customer_id,action.channel),False) else "consent_missing_or_withdrawn"
            recent_at=cooldowns.get((customer_id,action.id))
            if recent_at and recent_at>=as_of-timedelta(days=action.cooldown_days): reason=(reason+";cooldown").strip(";")
            status="suppressed" if reason else "recommended"; snapshot={"id":action.id,"name":action.name,"description":action.description,"channel":action.channel,"segment_id":action.segment_id,"cooldown_days":action.cooldown_days}; outcome=ActionOutcome(id=f"ACTN-{as_of:%Y}-{seq:06d}",action=action,customer_id=customer_id,recommended_at=as_of,status=status,suppression_reason=reason,action_snapshot=snapshot); batch.append(outcome); event_batch.append(ActionOutcomeEvent(outcome=outcome,to_status=status,changed_at=as_of,notes="Recommendation suppressed by eligibility rules" if reason else "Recommendation created by segment rules")); seq+=1; result["suppressed" if reason else "recommended"]+=1
            if len(batch)>=2000:
                ActionOutcome.objects.bulk_create(batch,batch_size=2000); ActionOutcomeEvent.objects.bulk_create(event_batch,batch_size=2000); batch=[]; event_batch=[]
    if batch: ActionOutcome.objects.bulk_create(batch,batch_size=2000); ActionOutcomeEvent.objects.bulk_create(event_batch,batch_size=2000)
    sequence.next_value=seq; sequence.save(update_fields=["next_value"])
    return result

@transaction.atomic
def transition_action_outcome(outcome_id,to_status,actor=None,notes="",revenue=None,provider_reference="",at=None):
    at=at or timezone.now(); outcome=ActionOutcome.objects.select_for_update().select_related("customer","action").get(pk=outcome_id); old=outcome.status
    allowed={"recommended":{"sent","suppressed"},"sent":{"converted","not_converted"}}
    if to_status not in allowed.get(old,set()): raise ValidationError(f"Cannot transition action from {old} to {to_status}.")
    if to_status=="sent":
        consent=Consent.objects.filter(customer=outcome.customer,channel=outcome.action.channel,effective_from__lte=at).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=at)).order_by("-effective_from").first()
        if not consent or not consent.is_allowed: raise ValidationError("A current channel consent is required before marking the action sent.")
    if to_status=="converted":
        if revenue is None or Decimal(revenue)<0: raise ValidationError("A conversion requires a nonnegative revenue amount.")
        outcome.revenue=Decimal(revenue); outcome.outcome_at=at
    elif to_status=="not_converted": outcome.revenue=Decimal("0"); outcome.outcome_at=at
    elif to_status=="suppressed": outcome.suppression_reason=notes[:40] or "operator_suppressed"
    outcome.status=to_status; outcome.save(update_fields=["status","suppression_reason","outcome_at","revenue"])
    ActionOutcomeEvent.objects.create(outcome=outcome,from_status=old,to_status=to_status,changed_at=at,changed_by=actor,actor_label=actor.get_username() if actor else "system",notes=notes,revenue=outcome.revenue if to_status=="converted" else None,provider_reference=provider_reference)
    return outcome

@transaction.atomic
def transition_support_case(case_id,to_status,actor=None,notes="",at=None):
    at=at or timezone.now(); case=SupportCase.objects.select_for_update().get(pk=case_id); old=case.status
    if to_status not in {"open","resolved"} or to_status==old: raise ValidationError(f"Invalid support case transition from {old} to {to_status}.")
    if old=="resolved" and to_status=="open" and not notes.strip(): raise ValidationError("A reopen reason is required.")
    case.status=to_status; case.resolved_at=at if to_status=="resolved" else None; case.save(update_fields=["status","resolved_at"])
    SupportCaseEvent.objects.create(case=case,from_status=old,to_status=to_status,changed_at=at,changed_by=actor,actor_label=actor.get_username() if actor else "system",notes=notes)
    return case

def evaluation_metrics():
    baseline=ActionOutcome.objects.filter(issue_type="")
    sent=baseline.filter(status__in=["sent","converted","not_converted"]).count(); converted=baseline.filter(status="converted").count()
    return {"recommendations":baseline.count(),"sent":sent,"conversions":converted,"conversion_rate":round(converted/sent*100,2) if sent else 0,"attributed_revenue":baseline.filter(status="converted").aggregate(v=Sum("revenue"))["v"] or Decimal("0"),"suppressed":baseline.filter(status="suppressed").count(),"known_anomalies_excluded":ActionOutcome.objects.exclude(issue_type="").count()}
