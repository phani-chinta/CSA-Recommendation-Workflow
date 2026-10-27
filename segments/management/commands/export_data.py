import csv
import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from segments.models import (ActionCatalog, ActionOutcome, ActionOutcomeEvent, Consent, Customer,
    EngagementEvent, Order, OrderLine, Product, SegmentMembership, SegmentRule, SupportCase,
    SupportCaseEvent)

class Command(BaseCommand):
    help="Stream domain entities to reproducible CSV/JSON/SQL seeds and write a source manifest."
    def add_arguments(self,p): p.add_argument("--output",default="data/generated"); p.add_argument("--generation-manifest",default=None)
    @staticmethod
    def sql_literal(value):
        if value is None: return "NULL"
        if isinstance(value,bool): return "TRUE" if value else "FALSE"
        if isinstance(value,(int,float,Decimal)): return str(value)
        if isinstance(value,(dict,list)): value=json.dumps(value,separators=(",",":"))
        return "'"+str(value).replace("'","''")+"'"
    @staticmethod
    def safe_csv_cell(value):
        if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@","\t","\r")): return "'"+value
        return value
    def handle(self,*args,**o):
        out=Path(o["output"]); out.mkdir(parents=True,exist_ok=True)
        models=[Customer,Product,Order,OrderLine,EngagementEvent,SupportCase,SupportCaseEvent,Consent,SegmentRule,SegmentMembership,ActionCatalog,ActionOutcome,ActionOutcomeEvent]
        manifest=[]; encoder=DjangoJSONEncoder(separators=(",",":")); sql_path=out/"seed.sql"
        with sql_path.open("w",encoding="utf-8",newline="") as sql:
            sql.write("-- Data only; apply migrations before loading. Security users and credentials are intentionally excluded.\n")
            for model in models:
                qs=model.objects.all().order_by(model._meta.pk.name); concrete=model._meta.concrete_fields; fields=[f.attname for f in concrete]; json_name=f"{model.__name__}.json"; csv_path=out/f"{model.__name__}.csv"
                with csv_path.open("w",newline="",encoding="utf-8") as stream:
                    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="raise"); writer.writeheader()
                    for row in qs.values(*fields).iterator(chunk_size=5000):
                        if "changed_by_id" in row: row["changed_by_id"]=None
                        writer.writerow({key:self.safe_csv_cell(value) for key,value in row.items()})
                json_path=out/json_name
                with json_path.open("w",encoding="utf-8",newline="") as stream:
                    stream.write("["); first=True
                    for obj in qs.iterator(chunk_size=2000):
                        if not first: stream.write(",")
                        first=False
                        record={"model":model._meta.label_lower,"pk":getattr(obj,model._meta.pk.attname),"fields":{f.name:(None if f.name=="changed_by" else getattr(obj,f.attname)) for f in concrete if not f.primary_key}}
                        for chunk in encoder.iterencode(record): stream.write(chunk)
                quoted_table=connection.ops.quote_name(model._meta.db_table); quoted_columns=", ".join(connection.ops.quote_name(f.column) for f in concrete); values_batch=[]
                for obj in qs.iterator(chunk_size=2000):
                    values=[]
                    for field in concrete:
                        value=getattr(obj,field.attname)
                        # Security user rows are intentionally omitted; retain their audit username separately.
                        if field.name=="changed_by": value=None
                        values.append(self.sql_literal(value))
                    values_batch.append("("+", ".join(values)+")")
                    if len(values_batch)>=500:
                        sql.write(f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES "+",\n".join(values_batch)+";\n"); values_batch=[]
                if values_batch: sql.write(f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES "+",\n".join(values_batch)+";\n")
                with csv_path.open("rb") as stream: checksum=hashlib.file_digest(stream,"sha256").hexdigest()
                manifest.append({"entity":model.__name__,"rows":qs.count(),"csv":csv_path.name,"json":json_name,"sha256":checksum})
            if connection.vendor=="postgresql":
                for model in models:
                    if model._meta.pk.get_internal_type() in {"BigAutoField","AutoField"}:
                        table=connection.ops.quote_name(model._meta.db_table); pk=connection.ops.quote_name(model._meta.pk.column)
                        sql.write(f"SELECT setval(pg_get_serial_sequence('{model._meta.db_table}','{model._meta.pk.column}'), COALESCE(MAX({pk}),1), MAX({pk}) IS NOT NULL) FROM {table};\n")
            max_sequence=0
            for outcome_id in ActionOutcome.objects.values_list("id",flat=True).iterator(chunk_size=5000):
                try: max_sequence=max(max_sequence,int(outcome_id.rsplit("-",1)[1]))
                except (ValueError,IndexError): continue
            sequence_table=connection.ops.quote_name("segments_actionsequence"); sequence_name=connection.ops.quote_name("name"); next_value=connection.ops.quote_name("next_value")
            sql.write(f"UPDATE {sequence_table} SET {next_value}={max_sequence+1} WHERE {sequence_name}='action_outcome';\n")
        generation_path=Path(o["generation_manifest"]) if o["generation_manifest"] else out/"generation_manifest.json"
        generation=json.loads(generation_path.read_text(encoding="utf-8")) if generation_path.exists() else None
        if generation_path.exists() and generation_path.resolve()!= (out/"generation_manifest.json").resolve(): shutil.copyfile(generation_path,out/"generation_manifest.json")
        truth_source=generation_path.parent/"ground_truth.json" if generation_path.exists() else None
        if truth_source and truth_source.exists() and truth_source.resolve()!=(out/"ground_truth.json").resolve(): shutil.copyfile(truth_source,out/"ground_truth.json")
        (out/"source_manifest.json").write_text(json.dumps({"format_version":1,"entities":manifest,"sql_seed":"seed.sql","ground_truth":"ground_truth.json" if truth_source and truth_source.exists() else None,"security_users_included":False,"generation":generation},indent=2),encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Stream-exported {len(models)} domain entities to {out}"))
