import json, random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from segments.models import Customer, Product, Order, OrderLine, EngagementEvent, Consent, SegmentRule, ActionCatalog, ActionOutcome, SegmentMembership, SupportCase, SupportCaseEvent, ActionOutcomeEvent, ActionSequence

class Command(BaseCommand):
    help="Generate reproducible synthetic data. Use --full for 50k customers, 200k orders and 1m events."
    def add_arguments(self,p):
        p.add_argument("--seed",type=int,default=20261022); p.add_argument("--customers",type=int,default=500); p.add_argument("--orders",type=int,default=2000); p.add_argument("--events",type=int,default=10000); p.add_argument("--full",action="store_true"); p.add_argument("--clear",action="store_true"); p.add_argument("--output",default="data/generated")
    def handle(self,*args,**o):
        rng=random.Random(o["seed"]); n,on,en=(50000,200000,1000000) if o["full"] else (o["customers"],o["orders"],o["events"])
        if n<1 or on<1 or en<0: raise CommandError("Generate at least one customer and order; event count may be zero or greater.")
        if o["clear"]:
            for m in [SupportCaseEvent,ActionOutcomeEvent,ActionOutcome,ActionSequence,ActionCatalog,SegmentMembership,SegmentRule,Consent,SupportCase,EngagementEvent,OrderLine,Order,Product,Customer]: m.objects.all().delete()
        existing=[m._meta.label for m in [Customer,Product,Order,EngagementEvent,Consent,SegmentRule,ActionOutcome,SupportCaseEvent] if m.objects.exists()]
        if existing: raise CommandError(f"Database contains existing business data ({', '.join(existing)}). Use --clear only for a disposable synthetic-data database.")
        today=date(2026,10,22); now=datetime(2026,10,22,tzinfo=timezone.utc); products=[]
        for i,(name,cat,price) in enumerate([("Everyday Tote","Accessories","24.99"),("Trail Bottle","Outdoors","34.50"),("Desk Lamp","Home","59.00"),("Travel Kit","Accessories","89.00"),("Yoga Mat","Wellness","45.00")],1): products.append(Product.objects.create(id=f"PRD-{i:04d}",name=name,category=cat,unit_price=Decimal(price)))
        customers=[]
        for i in range(1,n+1):
            joined=today-timedelta(days=rng.randint(1,1000)); life="new" if (today-joined).days<45 else rng.choices(["active","dormant"],[.8,.2])[0]
            customers.append(Customer(id=f"CUS-{i:06d}",first_name=f"Customer{i}",last_name=rng.choice(["A","B","C","D"]),email=f"customer{i}@example.test",region=rng.choice(["North","South","East","West","Central"]),joined_at=joined,lifecycle=life))
        Customer.objects.bulk_create(customers,batch_size=2000); ids=[f"CUS-{i:06d}" for i in range(1,n+1)]; joined_by_id={c.id:c.joined_at for c in customers}
        # Normalize auto_now_add after bulk insert so fixed-seed exports have stable bytes.
        Customer.objects.update(created_at=now)
        withdrawal_candidates=[c.id for i,c in enumerate(customers,1) if i%17==0 and (today-c.joined_at).days>=30]
        withdrawal_customer=withdrawal_candidates[0] if withdrawal_candidates else ids[-1]
        rules=[SegmentRule(id=f"SEG-2026-{i:06d}",name=name,description=f"Explainable purchase/engagement/service rule: {name}",priority=i,effective_from=today) for i,name in enumerate(["New","Dormant","High Value","Service Attention","Engaged","Active"],1)]; SegmentRule.objects.bulk_create(rules)
        ActionCatalog.objects.bulk_create([ActionCatalog(id=f"CAT-{i:04d}",name=f"{r.name} follow-up",description=f"Contextual contact for {r.name}",channel=["email","sms","push"][(i-1)%3],segment=r,priority=i,cooldown_days=30,effective_from=today) for i,r in enumerate(rules,1)])
        orders=[]; lines=[]
        for i in range(1,on+1):
            p=rng.choice(products); qty=rng.randint(1,4); state=rng.choices(["completed","returned","cancelled"],[.91,.05,.04])[0]
            # GT-003 deliberately leaves a returned line gross amount in source data.
            state="returned" if i==1 else state
            total=(p.unit_price*qty).quantize(Decimal(".01")) if state=="completed" or i==1 else Decimal("0.00"); oid=f"ORD-2026-{i:06d}"
            cid=rng.choice(ids); days=rng.randint(0,min(730,(today-joined_by_id[cid]).days)); orders.append(Order(id=oid,customer_id=cid,ordered_at=now-timedelta(days=days),status=state,total=total,issue_type="return_not_netted" if i==1 else "")); lines.append(OrderLine(id=f"{oid}-001",order_id=oid,product=p,quantity=qty,unit_price=p.unit_price,line_total=total,product_snapshot={"id":p.id,"name":p.name,"category":p.category,"unit_price":str(p.unit_price)}))
            if len(orders)>=5000:
                Order.objects.bulk_create(orders,batch_size=5000); OrderLine.objects.bulk_create(lines,batch_size=5000); orders=[]; lines=[]
            if i%50000==0: self.stdout.write(f"orders generated: {i:,}/{on:,}")
        if orders: Order.objects.bulk_create(orders,batch_size=5000); OrderLine.objects.bulk_create(lines,batch_size=5000)
        events=[]; channels=["email","sms","push"]
        for i in range(1,en+1):
            cid=rng.choice(ids); days=rng.randint(0,min(730,(today-joined_by_id[cid]).days)); events.append(EngagementEvent(id=f"EVT-{i:09d}",customer_id=cid,event_type=rng.choice(["email_open","email_click","web_visit","app_session","purchase_view"]),occurred_at=now-timedelta(days=days),channel=rng.choice(channels),campaign=f"CMP-{rng.randint(1,20):03d}"))
            if len(events)>=10000: EngagementEvent.objects.bulk_create(events,batch_size=10000); events=[]
            if i%100000==0: self.stdout.write(f"engagement events generated: {i:,}/{en:,}")
        if events: EngagementEvent.objects.bulk_create(events,batch_size=10000)
        cons=[]
        for i,cid in enumerate(ids,1):
            start=joined_by_id[cid]; effective=datetime(start.year,start.month,start.day,tzinfo=timezone.utc)
            for ch in channels:
                if ch=="email" and cid==withdrawal_customer:
                    days=max(1,(today-start).days); withdrawn=effective+timedelta(days=min(days,max(1,days//2)))
                    cons.append(Consent(id=f"CNS-{i:06d}-{ch}-001",customer_id=cid,channel=ch,is_allowed=True,effective_from=effective,effective_to=withdrawn,source="synthetic_signup"))
                    cons.append(Consent(id=f"CNS-{i:06d}-{ch}-002",customer_id=cid,channel=ch,is_allowed=False,effective_from=withdrawn,source="synthetic_withdrawal"))
                else: cons.append(Consent(id=f"CNS-{i:06d}-{ch}-001",customer_id=cid,channel=ch,is_allowed=True,effective_from=effective,source="synthetic_signup"))
        Consent.objects.bulk_create(cons,batch_size=5000)
        cases=[]
        for i in range(1,max(2,n//50)+1):
            cid=rng.choice(ids); opened=now-timedelta(days=rng.randint(0,min(365,(today-joined_by_id[cid]).days))); cases.append(SupportCase(id=f"CASE-{i:07d}",customer_id=cid,opened_at=opened,resolved_at=opened+timedelta(days=1),category=rng.choice(["billing","delivery","product"]),status="resolved",service_cost=Decimal("150.00") if i%4==0 else Decimal("25.00")))
        SupportCase.objects.bulk_create(cases,batch_size=3000)
        SupportCaseEvent.objects.bulk_create([SupportCaseEvent(case=case,to_status="resolved",changed_at=case.resolved_at,notes="Synthetic case resolved; generated lifecycle seed.") for case in cases],batch_size=3000)
        # GT-001: explicit current conflict for validator/demo inspection.
        for idx,r in enumerate(rules[:2]): SegmentMembership.objects.create(id=f"MEM-{r.id}-{ids[0]}-2026102200000{idx}",segment=r,customer_id=ids[0],assigned_at=now-timedelta(minutes=idx),reason="Ground-truth injected exclusive conflict",score=0,issue_type="exclusive_segment_conflict",rule_snapshot={"id":r.id,"name":r.name,"description":r.description,"priority":r.priority,"effective_from":r.effective_from.isoformat(),"effective_to":None})
        # GT-002 and GT-004 are explicit labeled records; the operational recommender itself suppresses opt-outs.
        email_action=ActionCatalog.objects.filter(channel="email").first()
        if email_action:
            violating_customer=withdrawal_customer
            bad=ActionOutcome.objects.create(id="ACTN-2026-000001",action=email_action,customer_id=violating_customer,recommended_at=now,status="sent",suppression_reason="",issue_type="action_violates_consent",action_snapshot={"id":email_action.id,"name":email_action.name,"description":email_action.description,"channel":email_action.channel,"segment_id":email_action.segment_id,"cooldown_days":email_action.cooldown_days})
            ActionOutcomeEvent.objects.create(outcome=bad,from_status="recommended",to_status="sent",changed_at=now,notes="Ground-truth injected consent violation")
        if len(rules)>1:
            wrong_action=ActionCatalog.objects.get(pk="CAT-0002"); bad=ActionOutcome.objects.create(id="ACTN-2026-000002",action=wrong_action,customer_id=ids[0],recommended_at=now,status="converted",outcome_at=now,revenue=Decimal("40.00"),issue_type="wrong_action_attribution",action_snapshot={"id":wrong_action.id,"name":wrong_action.name,"description":wrong_action.description,"channel":wrong_action.channel,"segment_id":wrong_action.segment_id,"cooldown_days":wrong_action.cooldown_days})
            ActionOutcomeEvent.objects.create(outcome=bad,from_status="sent",to_status="converted",changed_at=now,notes="Ground-truth injected attribution anomaly",revenue=Decimal("40.00"))
        out=Path(o["output"]); out.mkdir(parents=True,exist_ok=True)
        truth=[{"issue_id":"GT-001","issue_type":"exclusive_segment_conflict","customer_id":ids[0],"record_ids":[f"MEM-{rules[0].id}-{ids[0]}-20261022000000",f"MEM-{rules[1].id}-{ids[0]}-20261022000001"],"expected":"Validation must flag the two current exclusive memberships"},{"issue_id":"GT-002","issue_type":"action_violates_consent","customer_id":violating_customer if email_action else None,"record_id":"ACTN-2026-000001" if email_action else None,"expected":"Validator flags the contact; production recommender suppresses opt-outs"},{"issue_id":"GT-003","issue_type":"return_not_netted","order_id":"ORD-2026-000001","expected":"RFM uses only completed orders; validator flags returned order with positive total"},{"issue_id":"GT-004","issue_type":"wrong_action_attribution","customer_id":ids[0],"record_id":"ACTN-2026-000002","actual_action_id":"CAT-0002","expected_action_id":"CAT-0001","expected":"Outcome action/customer pair must be independently auditable"}]
        (out/"ground_truth.json").write_text(json.dumps(truth,indent=2),encoding="utf-8")
        (out/"generation_manifest.json").write_text(json.dumps({"generator":"segments.generate_demo","seed":o["seed"],"as_of":now.isoformat(),"scale":{"customers":n,"orders":on,"engagement_events":en},"source":"fully synthetic; no external data","known_anomalies":[x["issue_type"] for x in truth]},indent=2),encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Generated {n} customers, {on} orders, {en} events; seed={o['seed']}"))
