import csv
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, StreamingHttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Customer, SegmentMembership, SegmentRule, ActionOutcome, SupportCase, WorkflowRun
from .services import rebuild_segments, run_recommendations, evaluation_metrics, transition_action_outcome, transition_support_case

@login_required
@permission_required("segments.view_segmentrule",raise_exception=True)
def dashboard(request):
    segs=SegmentRule.objects.filter(active=True).annotate(n=Count("memberships",filter=Q(memberships__is_current=True)))
    can_view_actions=request.user.has_perm("segments.view_actionoutcome")
    metrics=evaluation_metrics() if can_view_actions else {"recommendations":0,"sent":0,"conversions":0,"conversion_rate":0,"attributed_revenue":0,"suppressed":0}
    recent=ActionOutcome.objects.select_related("customer","action").order_by("-recommended_at")[:8] if can_view_actions else []
    return render(request,"segments/dashboard.html",{"customers":Customer.objects.count(),"segments":segs,"metrics":metrics,"recent":recent,"runs":WorkflowRun.objects.select_related("requested_by").all()[:8]})

@login_required
@permission_required("segments.view_customer",raise_exception=True)
def customers(request):
    q=request.GET.get("q",""); rows=Customer.objects.all().order_by("id")
    if q: rows=rows.filter(Q(id__icontains=q)|Q(email__icontains=q)|Q(last_name__icontains=q))
    page=Paginator(rows,50).get_page(request.GET.get("page"))
    return render(request,"segments/customers.html",{"page_obj":page,"rows":page.object_list,"q":q})

@login_required
@permission_required("segments.view_customer",raise_exception=True)
def customer_detail(request,customer_id):
    c=get_object_or_404(Customer.objects.prefetch_related("consents"),pk=customer_id)
    actions=c.action_outcomes.select_related("action").order_by("-recommended_at")[:10] if request.user.has_perm("segments.view_actionoutcome") else []
    return render(request,"segments/customer_detail.html",{"c":c,"orders":c.orders.order_by("-ordered_at")[:20],"cases":c.support_cases.prefetch_related("events").order_by("-opened_at")[:20],"memberships":c.segment_memberships.select_related("segment").order_by("-assigned_at")[:10],"actions":actions})

@login_required
@require_POST
def actions(request):
    operation=request.POST.get("operation")
    if operation=="segment":
        if not request.user.has_perm("segments.run_segmentation"): raise PermissionDenied
    elif operation=="recommend":
        if not request.user.has_perm("segments.run_recommendations"): raise PermissionDenied
    else: raise Http404()
    run=WorkflowRun.objects.create(operation=operation,requested_by=request.user)
    from .tasks import execute_workflow
    try:
        from django.db import transaction
        transaction.on_commit(lambda: execute_workflow.delay(str(run.id)))
        messages.success(request,f"Workflow {run.id} queued.")
    except Exception:
        run.status="failed"; run.finished_at=timezone.now(); run.error="Unable to enqueue workflow; check the task broker."; run.save(update_fields=["status","finished_at","error"])
        messages.error(request,"Workflow could not be queued. Check the worker and broker status.")
    return redirect("dashboard")

@login_required
@permission_required("segments.view_actionoutcome",raise_exception=True)
def evaluation(request):
    page=Paginator(ActionOutcome.objects.select_related("customer","action").order_by("-recommended_at"),50).get_page(request.GET.get("page"))
    return render(request,"segments/evaluation.html",{"metrics":evaluation_metrics(),"outcomes":page.object_list,"page_obj":page})

class OutcomeTransitionForm(forms.Form):
    to_status=forms.ChoiceField(choices=[("sent","Sent"),("suppressed","Suppressed"),("converted","Converted"),("not_converted","Not converted")])
    notes=forms.CharField(required=False,widget=forms.Textarea(attrs={"rows":3}))
    revenue=forms.DecimalField(required=False,min_value=0,max_digits=10,decimal_places=2)

@login_required
@permission_required("segments.record_action_outcomes",raise_exception=True)
def outcome_transition(request,outcome_id):
    outcome=get_object_or_404(ActionOutcome.objects.select_related("customer","action"),pk=outcome_id)
    form=OutcomeTransitionForm(request.POST or None)
    form.fields["to_status"].choices=[("sent","Sent"),("suppressed","Suppressed")] if outcome.status=="recommended" else ([ ("converted","Converted"),("not_converted","Not converted") ] if outcome.status=="sent" else [])
    if request.method=="POST" and form.is_valid():
        try:
            transition_action_outcome(outcome.id,form.cleaned_data["to_status"],actor=request.user,notes=form.cleaned_data["notes"],revenue=form.cleaned_data["revenue"])
            messages.success(request,"Action outcome history updated."); return redirect("evaluation")
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,"segments/outcome_transition.html",{"outcome":outcome,"form":form})

class SupportTransitionForm(forms.Form):
    to_status=forms.ChoiceField(choices=[("open","Open"),("resolved","Resolved")])
    notes=forms.CharField(required=False,widget=forms.Textarea(attrs={"rows":3}))

class SupportCaseCreateForm(forms.Form):
    category=forms.ChoiceField(choices=[("billing","Billing"),("delivery","Delivery"),("product","Product"),("other","Other")])
    description=forms.CharField(widget=forms.Textarea(attrs={"rows":4}))
    service_cost=forms.DecimalField(required=False,initial=0,min_value=0,max_digits=9,decimal_places=2)

@login_required
@permission_required("segments.add_supportcase",raise_exception=True)
def support_case_create(request,customer_id):
    customer=get_object_or_404(Customer,pk=customer_id); form=SupportCaseCreateForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        from uuid import uuid4
        from django.db import transaction
        with transaction.atomic():
            case=SupportCase.objects.create(id=f"CASE-{uuid4().hex[:12].upper()}",customer=customer,opened_at=timezone.now(),category=form.cleaned_data["category"],status="open",service_cost=form.cleaned_data["service_cost"] or 0,description=form.cleaned_data["description"])
            from .models import SupportCaseEvent
            SupportCaseEvent.objects.create(case=case,to_status="open",changed_by=request.user,actor_label=request.user.get_username(),notes="Case opened: "+case.description)
        messages.success(request,f"Support case {case.id} created."); return redirect("customer_detail",customer_id=customer.id)
    return render(request,"segments/support_case_create.html",{"customer":customer,"form":form})

@login_required
@permission_required("segments.change_supportcase",raise_exception=True)
def support_case_transition(request,case_id):
    case=get_object_or_404(SupportCase.objects.select_related("customer"),pk=case_id); form=SupportTransitionForm(request.POST or None)
    form.fields["to_status"].choices=[(s,s.title()) for s in (["resolved"] if case.status=="open" else ["open"])]
    if request.method=="POST" and form.is_valid():
        try:
            transition_support_case(case.id,form.cleaned_data["to_status"],actor=request.user,notes=form.cleaned_data["notes"])
            messages.success(request,"Support case history updated."); return redirect("customer_detail",customer_id=case.customer_id)
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,"segments/support_case_transition.html",{"case":case,"form":form})

class Echo:
    def write(self,value): return value

def safe_csv_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@","\t","\r")): return "'"+value
    return value

@login_required
def export_data(request,kind):
    configs={"customers":(Customer,"view_customer"),"memberships":(SegmentMembership,"view_segmentmembership"),"actions":(ActionOutcome,"view_actionoutcome")}
    if kind not in configs: raise Http404()
    model,permission=configs[kind]
    if not request.user.has_perm(f"segments.{permission}"): raise PermissionDenied
    fields=[f.attname for f in model._meta.fields]; writer=csv.writer(Echo())
    def rows():
        yield writer.writerow(fields)
        for row in model.objects.all().order_by(model._meta.pk.name).values(*fields).iterator(chunk_size=2000):
            yield writer.writerow([safe_csv_cell(None if field=="changed_by_id" else row[field]) for field in fields])
    response=StreamingHttpResponse(rows(),content_type="text/csv; charset=utf-8"); response["Content-Disposition"]=f'attachment; filename="{kind}.csv"'; response["X-Content-Type-Options"]="nosniff"; return response

def health_live(request): return JsonResponse({"status":"ok"})

def health_ready(request):
    from django.db import connection
    try:
        with connection.cursor() as cursor: cursor.execute("SELECT 1"); cursor.fetchone()
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            from customer360.celery import app
            app.connection_for_read().ensure_connection(max_retries=0)
        return JsonResponse({"status":"ready"})
    except Exception:
        return JsonResponse({"status":"unavailable"},status=503)
