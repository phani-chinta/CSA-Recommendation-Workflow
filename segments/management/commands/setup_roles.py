from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from segments.models import (ActionCatalog, ActionOutcome, Consent, Customer, EngagementEvent,
                             Order, OrderLine, Product, SegmentMembership, SegmentRule, SupportCase)

class Command(BaseCommand):
    help="Create the supported operator groups and assign least-privilege permissions."
    def handle(self,*args,**opts):
        models=[ActionCatalog,ActionOutcome,Consent,Customer,EngagementEvent,Order,OrderLine,Product,SegmentMembership,SegmentRule,SupportCase]
        all_permissions=Permission.objects.all()
        admin_group,_=Group.objects.get_or_create(name="System Administrators"); admin_group.permissions.set(all_permissions)
        marketing,_=Group.objects.get_or_create(name="Marketing Operations")
        marketing_codes={"view","add","change"}
        marketing_perms=Permission.objects.filter(content_type__app_label="segments",codename__in=[f"{verb}_{model._meta.model_name}" for model in [ActionCatalog,Consent,Customer,Order,OrderLine,Product,SegmentMembership,SegmentRule] for verb in marketing_codes]+["view_actionoutcome"])
        marketing_perms|=Permission.objects.filter(content_type__app_label="segments",codename__in=["run_segmentation","run_recommendations","record_action_outcomes","view_workflowrun"])
        marketing.permissions.set(marketing_perms.distinct())
        support,_=Group.objects.get_or_create(name="Support Agents")
        support.permissions.set(Permission.objects.filter(content_type__app_label="segments",codename__in=["view_customer","view_order","view_orderline","view_supportcase","view_supportcaseevent","add_supportcase","change_supportcase","view_consent","view_segmentrule","view_workflowrun"]))
        analyst,_=Group.objects.get_or_create(name="Analysts")
        analyst.permissions.set(Permission.objects.filter(content_type__app_label="segments",codename__startswith="view_"))
        self.stdout.write(self.style.SUCCESS("Created/updated groups: System Administrators, Marketing Operations, Support Agents, Analysts"))
