import json
from pathlib import Path
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Count, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from segments.models import *

class Command(BaseCommand):
    help="Validate keys, enums, dates, arithmetic, consent, lifecycle and labeled exceptions."
    def add_arguments(self,p): p.add_argument("--output",default="data/generated/validation_summary.json"); p.add_argument("--ground-truth",default="data/generated/ground_truth.json")
    def handle(self,*args,**opts):
        checks={"customers":Customer.objects.count(),"products":Product.objects.count(),"orders":Order.objects.count(),"order_lines":OrderLine.objects.count(),"engagement_events":EngagementEvent.objects.count(),"support_cases":SupportCase.objects.count(),"consents":Consent.objects.count(),"segment_rules":SegmentRule.objects.count(),"memberships":SegmentMembership.objects.count(),"action_catalog":ActionCatalog.objects.count(),"action_outcomes":ActionOutcome.objects.count(),"action_outcome_events":ActionOutcomeEvent.objects.count(),"support_case_events":SupportCaseEvent.objects.count()}
        issues=[]
        if Customer.objects.values("email").annotate(n=Count("id")).filter(n__gt=1).exists(): issues.append("duplicate customer email")
        if Customer.objects.exclude(lifecycle__in=["new","active","dormant"]).exists(): issues.append("invalid customer lifecycle enum")
        if Order.objects.exclude(status__in=["completed","returned","cancelled"]).exists(): issues.append("invalid order status enum")
        if Order.objects.filter(ordered_at__date__lt=F("customer__joined_at")).exclude(issue_type="return_not_netted").exists(): issues.append("order predates customer join date")
        if Product.objects.filter(unit_price__lt=0).exists(): issues.append("negative product price")
        if OrderLine.objects.filter(quantity__lte=0).exists(): issues.append("order line quantity must be positive")
        if OrderLine.objects.filter(product_snapshot={}).exists(): issues.append("order lines missing frozen product definition")
        bad_math=Order.objects.annotate(lines_total=Coalesce(Sum("lines__line_total"),Value(Decimal("0.00")))).exclude(total=F("lines_total")).exclude(issue_type="return_not_netted")
        if bad_math.exists(): issues.append(f"{bad_math.count()} order totals do not reconcile to lines")
        if EngagementEvent.objects.exclude(event_type__in=["email_open","email_click","web_visit","app_session","purchase_view"]).exists(): issues.append("invalid engagement event type")
        if EngagementEvent.objects.exclude(channel__in=["email","sms","push"]).exists(): issues.append("invalid engagement channel")
        if EngagementEvent.objects.filter(occurred_at__date__lt=F("customer__joined_at")).exists(): issues.append("engagement event predates customer join date")
        if SupportCase.objects.exclude(status__in=["open","resolved"]).exists(): issues.append("invalid support case status")
        if SupportCase.objects.filter(resolved_at__lt=F("opened_at")).exists(): issues.append("support case resolves before it opens")
        if SupportCase.objects.filter(opened_at__date__lt=F("customer__joined_at")).exists(): issues.append("support case predates customer join date")
        if Consent.objects.exclude(channel__in=["email","sms","push"]).exists(): issues.append("invalid consent channel")
        if Consent.objects.filter(effective_to__lte=F("effective_from")).exists(): issues.append("consent effective end must follow start")
        if SegmentRule.objects.filter(effective_to__lte=F("effective_from")).exists(): issues.append("segment effective end must follow start")
        if ActionCatalog.objects.exclude(channel__in=["email","sms","push"]).exists(): issues.append("invalid action channel")
        if ActionCatalog.objects.filter(effective_to__lte=F("effective_from")).exists(): issues.append("action effective end must follow start")
        if ActionOutcome.objects.exclude(status__in=["recommended","suppressed","sent","converted","not_converted"]).exists(): issues.append("invalid action outcome status")
        if ActionOutcome.objects.filter(revenue__lt=0).exists(): issues.append("negative action revenue")
        dup=SegmentMembership.objects.filter(is_current=True,issue_type="").values("customer_id").annotate(n=Count("id")).filter(n__gt=1)
        if dup.exists(): issues.append(f"{dup.count()} customers have multiple current memberships")
        if SegmentMembership.objects.exclude(customer_id__in=Customer.objects.values("id")).exists(): issues.append("membership foreign key integrity error")
        if SegmentMembership.objects.filter(rule_snapshot={}).exists(): issues.append("membership missing frozen rule definition")
        if ActionOutcome.objects.filter(action_snapshot={}).exists(): issues.append("action outcome missing frozen catalog definition")
        if SupportCase.objects.exclude(pk__in=SupportCaseEvent.objects.values("case_id")).exists(): issues.append("support cases missing initial lifecycle history")
        if ActionOutcome.objects.exclude(pk__in=ActionOutcomeEvent.objects.values("outcome_id")).exists(): issues.append("action outcomes missing lifecycle history")
        latest_outcome_event=ActionOutcomeEvent.objects.filter(outcome_id=OuterRef("pk")).order_by("-changed_at","-pk").values("to_status")[:1]
        if ActionOutcome.objects.annotate(last_event_status=Subquery(latest_outcome_event)).exclude(status=F("last_event_status")).exists(): issues.append("action outcome does not match its latest history event")
        latest_case_event=SupportCaseEvent.objects.filter(case_id=OuterRef("pk")).order_by("-changed_at","-pk").values("to_status")[:1]
        if SupportCase.objects.annotate(last_event_status=Subquery(latest_case_event)).exclude(status=F("last_event_status")).exists(): issues.append("support case does not match its latest history event")
        invalid_outcome_event=ActionOutcomeEvent.objects.exclude(from_status="").exclude(Q(from_status="recommended",to_status__in=["sent","suppressed","recommended"])|Q(from_status="sent",to_status__in=["converted","not_converted"]))
        if invalid_outcome_event.exists(): issues.append("invalid action outcome lifecycle transition")
        invalid_case_event=SupportCaseEvent.objects.exclude(from_status="").exclude(Q(from_status="open",to_status="resolved")|Q(from_status="resolved",to_status="open"))
        if invalid_case_event.exists(): issues.append("invalid support case lifecycle transition")
        invalid_conversions=ActionOutcome.objects.filter(status="converted").filter(Q(outcome_at__isnull=True)|Q(revenue__lt=0))
        if invalid_conversions.exists(): issues.append(f"{invalid_conversions.count()} conversions are missing time or have negative revenue")
        for row in ActionOutcome.objects.filter(status__in=["converted","not_converted"],outcome_at__lt=F("recommended_at")).values_list("id",flat=True)[:5]: issues.append(f"{row}: outcome precedes recommendation")
        gt={"segment_conflicts":SegmentMembership.objects.filter(issue_type="exclusive_segment_conflict").count(),"consent_violations":ActionOutcome.objects.filter(issue_type="action_violates_consent").count(),"return_not_netted":Order.objects.filter(issue_type="return_not_netted").count(),"wrong_action_attribution":ActionOutcome.objects.filter(issue_type="wrong_action_attribution").count()}
        conflict_customers=SegmentMembership.objects.filter(issue_type="exclusive_segment_conflict").values("customer_id").annotate(n=Count("segment_id",distinct=True)).filter(n__gte=2)
        if gt["segment_conflicts"] and not conflict_customers.exists(): issues.append("labeled segment conflict does not contain two distinct segments")
        if gt["return_not_netted"] and not Order.objects.filter(issue_type="return_not_netted",status="returned",total__gt=0).exists(): issues.append("return anomaly label does not match the source row")
        for outcome in ActionOutcome.objects.filter(issue_type="action_violates_consent").select_related("action"):
            consent=Consent.objects.filter(customer_id=outcome.customer_id,channel=outcome.action.channel,effective_from__lte=outcome.recommended_at).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=outcome.recommended_at)).order_by("-effective_from").first()
            if outcome.status!="sent" or not consent or consent.is_allowed: issues.append(f"{outcome.id}: labeled consent anomaly does not match the source consent")
        truth_path=Path(opts["ground_truth"])
        if truth_path.exists():
            truth={item["issue_type"]:item for item in json.loads(truth_path.read_text(encoding="utf-8"))}
            expected=truth.get("wrong_action_attribution")
            if expected:
                row=ActionOutcome.objects.filter(pk=expected.get("record_id")).first()
                if not row or row.action_id!=expected.get("actual_action_id") or row.action_id==expected.get("expected_action_id"): issues.append("wrong-action attribution ground truth does not match the action record")
        report={"status":"PASS" if not issues else "FAIL","counts":checks,"issues":issues,"known_anomalies":gt,"ground_truth_separate_from_features":True}
        out=Path(opts["output"]); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2),encoding="utf-8")
        self.stdout.write(json.dumps(report,indent=2))
        if issues: raise SystemExit(1)
