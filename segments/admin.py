from django.contrib import admin
from .models import (ActionCatalog, ActionOutcome, ActionOutcomeEvent, Consent, Customer,
                     EngagementEvent, Order, OrderLine, Product, SegmentMembership,
                     SegmentRule, SupportCase, SupportCaseEvent, WorkflowRun)

class ImmutableHistoryAdmin(admin.ModelAdmin):
    def has_delete_permission(self,request,obj=None): return False

@admin.register(ActionOutcomeEvent)
class ActionOutcomeEventAdmin(ImmutableHistoryAdmin):
    list_display=("outcome","from_status","to_status","changed_at","changed_by")
    readonly_fields=tuple(f.name for f in ActionOutcomeEvent._meta.fields)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

class OutcomeEventInline(admin.TabularInline):
    model=ActionOutcomeEvent; extra=0; can_delete=False
    fields=("from_status","to_status","changed_at","changed_by","notes","revenue","provider_reference")
    readonly_fields=fields
    def has_add_permission(self,request,obj=None): return False

class ImmutableRecordAdmin(admin.ModelAdmin):
    readonly_fields=()
    def get_readonly_fields(self,request,obj=None): return tuple(f.name for f in self.model._meta.fields)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

@admin.register(ActionOutcome)
class ActionOutcomeAdmin(ImmutableHistoryAdmin):
    list_display=("id","customer","action","status","recommended_at","outcome_at","revenue")
    list_filter=("status","action__channel")
    search_fields=("id","customer__id","customer__email")
    readonly_fields=tuple(f.name for f in ActionOutcome._meta.fields)
    inlines=(OutcomeEventInline,)
    def has_add_permission(self,request): return False

@admin.register(SupportCaseEvent)
class SupportCaseEventAdmin(ImmutableHistoryAdmin):
    list_display=("case","from_status","to_status","changed_at","changed_by")
    readonly_fields=tuple(f.name for f in SupportCaseEvent._meta.fields)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

@admin.register(SupportCase)
class SupportCaseAdmin(admin.ModelAdmin):
    list_display=("id","customer","category","status","opened_at","resolved_at","service_cost")
    list_filter=("status","category")
    search_fields=("id","customer__id","customer__email")
    readonly_fields=("id","customer","opened_at","resolved_at","category","status","service_cost","description")
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False

@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display=("id","operation","status","requested_by","requested_at","started_at","finished_at")
    list_filter=("operation","status")
    readonly_fields=tuple(f.name for f in WorkflowRun._meta.fields)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

@admin.register(Consent)
class ConsentAdmin(ImmutableHistoryAdmin):
    list_display=("customer","channel","is_allowed","effective_from","effective_to","source")
    list_filter=("channel","is_allowed")
    search_fields=("customer__id","customer__email")
    def has_change_permission(self,request,obj=None): return False

@admin.register(SegmentMembership)
class SegmentMembershipAdmin(ImmutableRecordAdmin):
    list_display=("id","customer","segment","assigned_at","is_current","score")
    list_filter=("segment","is_current")
    search_fields=("id","customer__id")
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

@admin.register(Order)
class OrderAdmin(ImmutableRecordAdmin):
    list_display=("id","customer","ordered_at","status","total")
    list_filter=("status",)
    search_fields=("id","customer__id")
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False

for model in [ActionCatalog,Product,SegmentRule]:
    admin.site.register(model)

for model in [EngagementEvent,OrderLine]: admin.site.register(model,ImmutableRecordAdmin)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display=("id","email","region","lifecycle","joined_at")
    list_filter=("region","lifecycle")
    search_fields=("id","email","last_name")
    readonly_fields=("id","joined_at","lifecycle","created_at")
    def has_delete_permission(self,request,obj=None): return False
