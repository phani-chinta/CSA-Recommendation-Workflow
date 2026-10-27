import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

class Customer(models.Model):
    id = models.CharField(primary_key=True, max_length=16)
    first_name = models.CharField(max_length=40)
    last_name = models.CharField(max_length=40)
    email = models.EmailField(unique=True)
    region = models.CharField(max_length=20)
    joined_at = models.DateField()
    lifecycle = models.CharField(max_length=16, choices=[("new","New"),("active","Active"),("dormant","Dormant")])
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.id} · {self.first_name} {self.last_name}"

class Product(models.Model):
    id = models.CharField(primary_key=True, max_length=16)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=40)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Order(models.Model):
    id = models.CharField(primary_key=True, max_length=24)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    ordered_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=[("completed","Completed"),("returned","Returned"),("cancelled","Cancelled")])
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issue_type = models.CharField(max_length=32, blank=True)
    def __str__(self): return self.id
    class Meta:
        indexes=[models.Index(fields=["customer","ordered_at"]),models.Index(fields=["status","ordered_at"])]

class OrderLine(models.Model):
    id = models.CharField(primary_key=True, max_length=28)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_lines")
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    product_snapshot=models.JSONField(default=dict)

class EngagementEvent(models.Model):
    id = models.CharField(primary_key=True, max_length=24)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="engagement_events")
    event_type = models.CharField(max_length=20)
    occurred_at = models.DateTimeField()
    channel = models.CharField(max_length=16)
    campaign = models.CharField(max_length=32, blank=True)
    class Meta:
        indexes=[models.Index(fields=["customer","occurred_at"]),models.Index(fields=["occurred_at","event_type"])]

class SupportCase(models.Model):
    id = models.CharField(primary_key=True, max_length=20)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="support_cases")
    opened_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    category = models.CharField(max_length=24,choices=[("billing","Billing"),("delivery","Delivery"),("product","Product"),("other","Other")])
    status = models.CharField(max_length=12, choices=[("open","Open"),("resolved","Resolved")])
    service_cost = models.DecimalField(max_digits=9, decimal_places=2)
    description=models.TextField(blank=True)
    class Meta:
        indexes=[models.Index(fields=["customer","opened_at"]),models.Index(fields=["status","opened_at"])]

class SupportCaseEvent(models.Model):
    case=models.ForeignKey(SupportCase,on_delete=models.PROTECT,related_name="events")
    from_status=models.CharField(max_length=12,blank=True)
    to_status=models.CharField(max_length=12)
    changed_at=models.DateTimeField(default=timezone.now)
    changed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="support_case_events")
    actor_label=models.CharField(max_length=150,blank=True)
    notes=models.TextField(blank=True)
    class Meta:
        ordering=["changed_at","id"]
        indexes=[models.Index(fields=["case","changed_at"])]

class Consent(models.Model):
    id = models.CharField(primary_key=True, max_length=40)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="consents")
    channel = models.CharField(max_length=16, choices=[("email","Email"),("sms","SMS"),("push","Push")])
    is_allowed = models.BooleanField()
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=24, default="customer_preference")
    class Meta:
        ordering=["-effective_from"]
        indexes=[models.Index(fields=["customer","channel","effective_from"])]
        constraints=[models.CheckConstraint(condition=Q(effective_to__isnull=True)|Q(effective_to__gt=models.F("effective_from")),name="consent_end_after_start")]

class SegmentRule(models.Model):
    id = models.CharField(primary_key=True, max_length=24)
    name = models.CharField(max_length=64)
    description = models.TextField()
    priority = models.PositiveSmallIntegerField(default=10)
    exclusive = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

class SegmentMembership(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    segment = models.ForeignKey(SegmentRule, on_delete=models.PROTECT, related_name="memberships")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="segment_memberships")
    assigned_at = models.DateTimeField()
    reason = models.TextField()
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_current = models.BooleanField(default=True)
    issue_type = models.CharField(max_length=32, blank=True)
    rule_snapshot=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["segment","customer","assigned_at"],name="unique_membership_event")]
        indexes=[models.Index(fields=["customer","is_current"]),models.Index(fields=["segment","is_current"])]
        permissions=[("run_segmentation","Can rebuild segment memberships")]

class ActionCatalog(models.Model):
    id = models.CharField(primary_key=True, max_length=24)
    name = models.CharField(max_length=64)
    description = models.TextField()
    channel = models.CharField(max_length=16, choices=[("email","Email"),("sms","SMS"),("push","Push")])
    segment = models.ForeignKey(SegmentRule, on_delete=models.PROTECT, related_name="actions")
    priority = models.PositiveSmallIntegerField(default=10)
    active = models.BooleanField(default=True)
    cooldown_days = models.PositiveSmallIntegerField(default=30)
    effective_from=models.DateField(default=timezone.localdate)
    effective_to=models.DateField(null=True,blank=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(effective_to__isnull=True)|Q(effective_to__gt=models.F("effective_from")),name="action_end_after_start")]
        permissions=[("run_recommendations","Can generate action recommendations")]

class ActionOutcome(models.Model):
    id = models.CharField(primary_key=True, max_length=32)
    action = models.ForeignKey(ActionCatalog, on_delete=models.PROTECT, related_name="outcomes")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="action_outcomes")
    recommended_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=[("recommended","Recommended"),("suppressed","Suppressed"),("sent","Sent"),("converted","Converted"),("not_converted","Not converted")])
    suppression_reason = models.CharField(max_length=40, blank=True)
    outcome_at = models.DateTimeField(null=True, blank=True)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    issue_type = models.CharField(max_length=32, blank=True)
    action_snapshot=models.JSONField(default=dict)
    class Meta:
        permissions=[("record_action_outcomes","Can record action outcome transitions")]
        indexes=[models.Index(fields=["customer","recommended_at"]),models.Index(fields=["action","recommended_at"]),models.Index(fields=["status","recommended_at"])]

class ActionSequence(models.Model):
    name=models.CharField(max_length=24,primary_key=True)
    next_value=models.PositiveBigIntegerField(default=1)

class WorkflowLock(models.Model):
    name=models.CharField(max_length=24,primary_key=True)
    touched_at=models.DateTimeField(default=timezone.now)

class ActionOutcomeEvent(models.Model):
    outcome=models.ForeignKey(ActionOutcome,on_delete=models.PROTECT,related_name="events")
    from_status=models.CharField(max_length=16,blank=True)
    to_status=models.CharField(max_length=16)
    changed_at=models.DateTimeField(default=timezone.now)
    changed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="action_outcome_events")
    actor_label=models.CharField(max_length=150,blank=True)
    notes=models.TextField(blank=True)
    revenue=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    provider_reference=models.CharField(max_length=128,blank=True)
    class Meta:
        ordering=["changed_at","id"]
        indexes=[models.Index(fields=["outcome","changed_at"])]

class WorkflowRun(models.Model):
    OPERATIONS=[("segment","Segment rebuild"),("recommend","Recommendation run")]
    STATES=[("queued","Queued"),("running","Running"),("succeeded","Succeeded"),("failed","Failed")]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    operation=models.CharField(max_length=16,choices=OPERATIONS)
    status=models.CharField(max_length=12,choices=STATES,default="queued")
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="workflow_runs")
    requested_at=models.DateTimeField(default=timezone.now)
    started_at=models.DateTimeField(null=True,blank=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    attempts=models.PositiveSmallIntegerField(default=0)
    result=models.JSONField(default=dict,blank=True)
    error=models.TextField(blank=True)
    class Meta:
        ordering=["-requested_at"]
        permissions=[("run_customer_workflows","Can enqueue customer segmentation and recommendation workflows")]
        indexes=[models.Index(fields=["status","requested_at"])]
