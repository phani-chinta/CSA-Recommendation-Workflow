from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from .models import (ActionCatalog, ActionOutcome, ActionOutcomeEvent, ActionSequence, Consent, Customer,
                     EngagementEvent, Order, SegmentMembership, SegmentRule, SupportCase,
                     SupportCaseEvent)
from .services import (rebuild_segments, run_recommendations, transition_action_outcome,
                       transition_support_case)
from .services_delivery import dispatch_email_actions

class CustomerWorkflowTests(TestCase):
    def setUp(self):
        now=timezone.now(); self.today=now.date(); self.customer=Customer.objects.create(id="CUS-900001",first_name="Test",last_name="Account",email="workflow@example.test",region="North",joined_at=self.today-timedelta(days=400),lifecycle="active")
        self.rules={}
        for i,name in enumerate(["New","Dormant","High Value","Service Attention","Engaged","Active"],1):
            self.rules[name]=SegmentRule.objects.create(id=f"SEG-2026-{900000+i:06d}",name=name,description=f"Rule for {name}",priority=i,effective_from=self.today-timedelta(days=10))

    def test_engagement_signal_is_explainable_and_snapshotted(self):
        now=timezone.now()
        Order.objects.create(id="ORD-2026-900001",customer=self.customer,ordered_at=now-timedelta(days=4),status="completed",total=Decimal("150.00"))
        for i in range(2): EngagementEvent.objects.create(id=f"EVT-90000000{i}",customer=self.customer,event_type="web_visit",occurred_at=now-timedelta(days=1),channel="email")
        result=rebuild_segments(as_of=now)
        membership=SegmentMembership.objects.get(customer=self.customer,is_current=True)
        self.assertEqual(result["memberships"],1); self.assertEqual(membership.segment.name,"Engaged")
        self.assertIn("2 engagement events",membership.reason); self.assertEqual(membership.rule_snapshot["id"],membership.segment_id)

    def test_recommendation_suppresses_without_consent_and_logs_decision(self):
        rule=self.rules["Active"]
        SegmentMembership.objects.create(id="MEM-SEG-TEST-CUS-TEST-0001",segment=rule,customer=self.customer,assigned_at=timezone.now(),reason="Test rule")
        action=ActionCatalog.objects.create(id="CAT-TEST",name="Email follow-up",description="Follow up",channel="email",segment=rule,priority=1,cooldown_days=30,effective_from=self.today-timedelta(days=1))
        Consent.objects.create(id="CNS-TEST",customer=self.customer,channel="email",is_allowed=False,effective_from=timezone.now()-timedelta(days=1))
        result=run_recommendations()
        outcome=ActionOutcome.objects.get(customer=self.customer,action=action)
        self.assertEqual(result["suppressed"],1); self.assertEqual(outcome.status,"suppressed")
        self.assertEqual(outcome.suppression_reason,"consent_missing_or_withdrawn"); self.assertEqual(outcome.events.count(),1)

    def test_recommendation_advances_a_stale_action_sequence(self):
        now=timezone.now(); rule=self.rules["Active"]
        SegmentMembership.objects.create(id="MEM-SEQ-CUS-TEST-0001",segment=rule,customer=self.customer,assigned_at=now,reason="Test rule")
        action=ActionCatalog.objects.create(id="CAT-SEQ",name="Email follow-up",description="Follow up",channel="email",segment=rule,effective_from=self.today-timedelta(days=1))
        Consent.objects.create(id="CNS-SEQ",customer=self.customer,channel="email",is_allowed=True,effective_from=now-timedelta(days=1))
        ActionOutcome.objects.create(id=f"ACTN-{now:%Y}-000900",action=action,customer=self.customer,recommended_at=now-timedelta(days=1),status="suppressed")
        sequence=ActionSequence.objects.get(name="action_outcome"); sequence.next_value=1; sequence.save(update_fields=["next_value"])
        run_recommendations(as_of=now)
        outcome=ActionOutcome.objects.get(customer=self.customer,action=action,status="recommended")
        self.assertEqual(outcome.id,f"ACTN-{now:%Y}-000901")

    def test_sent_transition_requires_consent_and_conversions_are_audited(self):
        action=ActionCatalog.objects.create(id="CAT-TEST",name="Test",description="Action",channel="email",segment=self.rules["Active"],effective_from=self.today-timedelta(days=1))
        outcome=ActionOutcome.objects.create(id="ACTN-2026-900001",action=action,customer=self.customer,recommended_at=timezone.now(),status="recommended")
        with self.assertRaises(ValidationError): transition_action_outcome(outcome.id,"sent")
        Consent.objects.create(id="CNS-TEST",customer=self.customer,channel="email",is_allowed=True,effective_from=timezone.now()-timedelta(days=1))
        transition_action_outcome(outcome.id,"sent",notes="Provider accepted")
        transition_action_outcome(outcome.id,"converted",revenue=Decimal("25.00"),notes="Matched order")
        outcome.refresh_from_db(); self.assertEqual(outcome.status,"converted"); self.assertEqual(outcome.events.count(),2)

    def test_support_reopen_requires_reason_and_records_history(self):
        case=SupportCase.objects.create(id="CASE-9000001",customer=self.customer,opened_at=timezone.now()-timedelta(days=2),resolved_at=timezone.now()-timedelta(days=1),category="delivery",status="resolved",service_cost=Decimal("25"))
        with self.assertRaises(ValidationError): transition_support_case(case.id,"open")
        transition_support_case(case.id,"open",notes="Customer reports the issue recurred")
        case.refresh_from_db(); self.assertEqual(case.status,"open"); self.assertIsNone(case.resolved_at); self.assertEqual(SupportCaseEvent.objects.filter(case=case).count(),1)

    def test_admin_csv_export_has_foreign_key_headers(self):
        user=get_user_model().objects.create_superuser(username="csv-admin",email="csv@example.test",password="a-strong-test-password-123")
        action=ActionCatalog.objects.create(id="CAT-TEST",name="Test",description="Action",channel="email",segment=self.rules["Active"],effective_from=self.today-timedelta(days=1))
        ActionOutcome.objects.create(id="ACTN-2026-900001",action=action,customer=self.customer,recommended_at=timezone.now(),status="recommended")
        self.client.force_login(user); response=self.client.get("/exports/actions/")
        payload=b"".join(response.streaming_content).decode("utf-8")
        self.assertEqual(response.status_code,200); self.assertIn("action_id",payload.splitlines()[0]); self.assertIn("customer_id",payload.splitlines()[0])

    def test_private_dashboard_redirects_anonymous_user_to_login(self):
        response=self.client.get("/")
        self.assertEqual(response.status_code,302); self.assertIn("/accounts/login/",response.url)

    def test_role_setup_keeps_analysts_read_only(self):
        call_command("setup_roles",verbosity=0)
        user=get_user_model().objects.create_user(username="analyst",password="a-strong-test-password-123")
        user.groups.add(Group.objects.get(name="Analysts"))
        self.assertTrue(user.has_perm("segments.view_actionoutcome")); self.assertFalse(user.has_perm("segments.run_recommendations")); self.assertFalse(user.has_perm("segments.record_action_outcomes"))

    def test_email_dispatch_preview_never_changes_state(self):
        action=ActionCatalog.objects.create(id="CAT-TEST",name="Preview",description="Preview only",channel="email",segment=self.rules["Active"],effective_from=self.today-timedelta(days=1))
        Consent.objects.create(id="CNS-TEST",customer=self.customer,channel="email",is_allowed=True,effective_from=timezone.now()-timedelta(days=1))
        outcome=ActionOutcome.objects.create(id="ACTN-2026-900002",action=action,customer=self.customer,recommended_at=timezone.now(),status="recommended")
        result=dispatch_email_actions(dry_run=True)
        outcome.refresh_from_db(); self.assertEqual(result["eligible"],1); self.assertEqual(outcome.status,"recommended"); self.assertEqual(outcome.events.count(),0)

    def test_workflow_task_records_run_state(self):
        from .models import WorkflowRun
        from .tasks import execute_workflow
        run=WorkflowRun.objects.create(operation="segment")
        result=execute_workflow(str(run.id)); run.refresh_from_db()
        self.assertEqual(result["status"],"succeeded"); self.assertEqual(run.status,"succeeded"); self.assertEqual(run.attempts,1)

    def test_support_agent_can_open_and_audit_case(self):
        call_command("setup_roles",verbosity=0)
        user=get_user_model().objects.create_user(username="support",password="a-strong-test-password-123")
        user.groups.add(Group.objects.get(name="Support Agents")); self.client.force_login(user)
        response=self.client.post(f"/customers/{self.customer.id}/cases/new/",{"category":"delivery","description":"Package arrived damaged","service_cost":"20.00"})
        self.assertEqual(response.status_code,302)
        case=SupportCase.objects.get(customer=self.customer); event=SupportCaseEvent.objects.get(case=case)
        self.assertEqual(case.status,"open"); self.assertEqual(event.to_status,"open"); self.assertEqual(event.actor_label,"support")
