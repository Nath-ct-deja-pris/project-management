"""Build an auditable Microsoft Project MSPDI file from the supplied A&D case.

The generator uses Python's standard library. Report rendering is optional.
All work estimates are PERSON-days; leveling delays are ELAPSED calendar days.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, time
from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "livrables"
BASE = datetime(2003, 5, 26, 8)
DAY = 480
NS = "http://schemas.microsoft.com/project"
ET.register_namespace("", NS)


def start_date(minutes: int) -> datetime:
    """Working-minute boundary -> next work instant, including lunch/weekends."""
    days, rem = divmod(minutes, DAY)
    weeks, weekday = divmod(days, 5)
    result = BASE + timedelta(days=7 * weeks + weekday, minutes=rem)
    if rem >= 240:
        result += timedelta(hours=1)
    return result


def finish_date(minutes: int) -> datetime:
    if minutes == 0:
        return BASE
    if minutes % DAY == 0:
        return start_date(minutes - 1) + timedelta(minutes=1)
    if minutes % DAY == 240:
        return start_date(minutes) - timedelta(hours=1)
    return start_date(minutes)


def work_index(date: datetime) -> int:
    """Round a calendar date FORWARD onto the working calendar."""
    if date.weekday() >= 5:
        date = datetime.combine(date.date() + timedelta(days=7-date.weekday()), time(8))
    if date.time() < time(8):
        date = datetime.combine(date.date(), time(8))
    elif time(12) <= date.time() < time(13):
        date = datetime.combine(date.date(), time(13))
    elif date.time() >= time(17):
        return work_index(datetime.combine(date.date() + timedelta(days=1), time(8)))
    delta_days = (date.date() - BASE.date()).days
    weeks, rem = divmod(delta_days, 7)
    mins = date.hour * 60 + date.minute - 8*60
    if date.hour >= 13:
        mins -= 60
    return (weeks*5 + rem)*DAY + mins


def delayed(start: int, edays: int) -> int:
    return work_index(start_date(start) + timedelta(days=edays)) if edays else start


def inverse_delay(latest: int, edays: int) -> int:
    if not edays:
        return latest
    lo, hi = latest - (edays+8)*DAY, latest
    while lo < hi:
        mid = (lo+hi+1)//2
        if delayed(mid, edays) <= latest:
            lo = mid
        else:
            hi = mid-1
    return lo


def read_data():
    resources = json.loads((ROOT / "data/resources.json").read_text())
    resources = {r["code"]: dict(r, uid=i+1) for i,r in enumerate(resources)}
    with (ROOT / "data/case_tasks.tsv").open() as f:
        tasks = {int(t["id"]): t for t in csv.DictReader(f, delimiter="\t")}
    for i,t in tasks.items():
        t["id"] = i
        t["outline_level"] = len(t["wbs"].split("."))
        t["parent"] = next((j for j,u in tasks.items() if u["wbs"] == t["wbs"].rsplit(".",1)[0] and j != i), None)
        t["children"] = [j for j,u in tasks.items() if u["wbs"].startswith(t["wbs"]+".") and u["work_days"]]
        t["summary"] = not bool(t["work_days"])
        t["delay_edays"] = int(t["delay_edays"])
        t["assign"] = []
        for item in t["resources"].split(","):
            if not item:
                continue
            code,_,units = item.partition(":")
            t["assign"].append((code, Decimal(units or "1")))
        t["work_minutes"] = int(Decimal(t["work_days"] or "0")*DAY)
        total_units = sum((u for _,u in t["assign"]), Decimal(0))
        t["duration_minutes"] = int(t["work_minutes"]/total_units) if total_units else 0
        if total_units:
            assert Decimal(t["duration_minutes"])*total_units == t["work_minutes"]
        t["labour_cost"] = sum((Decimal(t["duration_minutes"])/60 * u * resources[r]["standard_rate"] for r,u in t["assign"]), Decimal(0))
        # Existing licenses: no acquisition cost. Hardware is attached once to task 35.
        t["fixed_cost"] = Decimal(98500 if i == 35 else 0)
        t["predecessor_links"] = []
        for item in t["predecessors"].split(","):
            if item:
                kind = item[-2:] if item[-2:] in ("SS","FF","SF") else "FS"
                t["predecessor_links"].append((int(item[:-2] if kind != "FS" else item),kind))
    return tasks,resources


def expand_links(tasks, starts=None):
    """Resolve summary links for computation, preserve original links in the XML."""
    edges = set()
    for i,t in tasks.items():
        successors = t["children"] if t["summary"] else [i]
        for p,kind in t["predecessor_links"]:
            source = tasks[p]
            if source["summary"]:
                predecessors = source["children"]
                if kind in ("SS","SF"):
                    # An SS link from a summary refers to its earliest child start.
                    predecessors = [min(predecessors,key=lambda j:(starts[j] if starts else 0,j))]
            else:
                predecessors = [p]
            for a in predecessors:
                for b in successors:
                    edges.add((a,b,kind))
    return sorted(edges)


def schedule(tasks, durations=None, delay_override=None):
    leaves = [i for i,t in tasks.items() if not t["summary"]]
    durations = durations or {i:tasks[i]["duration_minutes"] for i in leaves}
    delays = {i:(delay_override.get(i,tasks[i]["delay_edays"]) if delay_override else tasks[i]["delay_edays"]) for i in leaves}
    edges = expand_links(tasks)
    # Dependency-only topological pass. Project management has a genuine FF link.
    incoming,outgoing = defaultdict(list),defaultdict(list)
    for a,b,k in edges:
        incoming[b].append((a,k));outgoing[a].append((b,k))
    todo,order = set(leaves),[]
    while todo:
        ready = sorted(i for i in todo if all(p not in todo for p,_ in incoming[i]))
        if not ready:
            raise ValueError("Cyclic dependency")
        order.extend(ready);todo.difference_update(ready)
    starts,finishes = {},{}
    for i in order:
        bounds = [0]
        for p,kind in incoming[i]:
            if kind == "FS": bounds.append(finishes[p])
            elif kind == "SS": bounds.append(starts[p])
            elif kind == "FF": bounds.append(finishes[p]-durations[i])
            else: raise ValueError(kind)
        starts[i] = delayed(max(bounds),delays[i])
        finishes[i] = starts[i]+durations[i]
    # SS summary selection must match the calculated earliest subtask.
    assert expand_links(tasks,starts) == edges
    project_finish = max(finishes.values())
    latest = {i:project_finish-durations[i] for i in leaves}
    for i in reversed(order):
        for j,kind in outgoing[i]:
            bound = inverse_delay(latest[j],delays[j])
            if kind == "FS": bound -= durations[i]
            elif kind == "FF": bound += durations[j]-durations[i]
            latest[i] = min(latest[i],bound)
    for i,t in tasks.items():
        if t["summary"]:
            starts[i] = min(starts[c] for c in t["children"])
            finishes[i] = max(finishes[c] for c in t["children"])
            latest[i] = starts[i]+min(latest[c]-starts[c] for c in t["children"])
    return dict(starts=starts,finishes=finishes,latest=latest,edges=edges,finish=project_finish)


def analyse(tasks, resources, plan):
    S,F,L = plan["starts"],plan["finishes"],plan["latest"]
    for i,t in tasks.items():
        if t["summary"]:
            t["work_minutes"] = sum(tasks[j]["work_minutes"] for j in t["children"])
            t["duration_minutes"] = F[i]-S[i]
            t["labour_cost"] = sum(tasks[j]["labour_cost"] for j in t["children"])
            t["fixed_cost"] = sum(tasks[j]["fixed_cost"] for j in t["children"])
        t["start"] = S[i];t["finish"] = F[i]
        t["late_start"] = L[i];t["late_finish"] = L[i]+t["duration_minutes"]
        t["slack_minutes"] = L[i]-S[i]
        t["critical"] = t["slack_minutes"] <= 0
    # A minute-accurate resource audit, not just a count of overlapping tasks.
    allocation = {r:defaultdict(Decimal) for r in resources}
    for i,t in tasks.items():
        if not t["summary"]:
            for r,u in t["assign"]:
                allocation[r][S[i]] += u;allocation[r][F[i]] -= u
    peaks = {}
    for r,events in allocation.items():
        units,peak = Decimal(0),Decimal(0)
        for _,change in sorted(events.items()):
            units += change;peak=max(peak,units)
        peaks[r] = float(peak)
    assert all(p <= 1 for p in peaks.values()), peaks
    critical_edges = []
    for a,b,k in plan["edges"]:
        if not (tasks[a]["critical"] and tasks[b]["critical"]): continue
        raw = F[a] if k=="FS" else (S[a] if k=="SS" else F[a]-tasks[b]["duration_minutes"])
        if delayed(max(0,raw),tasks[b]["delay_edays"]) == S[b]:
            critical_edges.append((a,b,k))
    # One extra working week of system testing, as discussed in the report.
    stressed_durations={i:t["duration_minutes"]+(5*DAY if i==54 else 0) for i,t in tasks.items() if not t["summary"]}
    stress=schedule(tasks,stressed_durations)
    return dict(
        start=BASE.isoformat(),finish=finish_date(F[1]).isoformat(),
        deployment=finish_date(F[58]).isoformat(),duration_days=F[1]/DAY,
        work_hours=tasks[1]["work_minutes"]/60,
        labour_cost=float(tasks[1]["labour_cost"]),capital_cost=float(tasks[1]["fixed_cost"]),
        total_cost=float(tasks[1]["labour_cost"]+tasks[1]["fixed_cost"]),
        critical_leaf_ids=[i for i,t in tasks.items() if t["critical"] and not t["summary"]],
        critical_edges=critical_edges,resource_peak_units=peaks,
        sensitivity_system_test_plus_5_days=dict(deployment=finish_date(stress["finishes"][58]).isoformat(),finish=finish_date(stress["finish"]).isoformat(),note="Sensibilité du réseau, non probabiliste ; couverture du support à adapter et ressources à recontrôler."),
    )


def elem(parent,tag,value=None):
    e=ET.SubElement(parent,f"{{{NS}}}{tag}")
    if value is not None: e.text=str(value)
    return e


def duration(minutes):
    return f"PT{int(minutes)//60}H{int(minutes)%60}M0S"


def iso_date(minutes,finish=False):
    return (finish_date(minutes) if finish else start_date(minutes)).isoformat(timespec="seconds")


def create_xml(tasks,resources,summary):
    p=ET.Element(f"{{{NS}}}Project")
    settings=[
        ("SaveVersion",14),("Name","A&D High Tech — Online Store"),
        ("Title","A&D High Tech (A) — Planning de référence"),
        ("Subject","Cas KEL156 — réponses aux cinq questions de gestion de projet"),
        ("Category","Étude de cas"),("Company","A&D High Tech"),("Manager","Chris Johnson"),
        ("Author","Planning établi à partir des annexes 5 à 9 du cas fourni"),
        ("ScheduleFromStart",1),("StartDate",BASE.isoformat()),("FinishDate",summary["finish"]),
        ("FYStartDate",1),("CriticalSlackLimit",0),("CurrencyDigits",2),("CurrencySymbol","$"),
        ("CurrencyCode","USD"),("CurrencySymbolPosition",0),("CalendarUID",1),
        ("DefaultStartTime","08:00:00"),("DefaultFinishTime","17:00:00"),
        ("MinutesPerDay",480),("MinutesPerWeek",2400),("DaysPerMonth",20),
        ("DefaultTaskType",2),("DefaultFixedCostAccrual",3),("DefaultStandardRate",75),
        ("DefaultOvertimeRate",75),("DurationFormat",7),("WorkFormat",2),
        ("EditableActualCosts",0),("HonorConstraints",1),("InsertedProjectsLikeSummary",1),
        ("MultipleCriticalPaths",0),("NewTasksEffortDriven",0),("NewTasksEstimated",0),
        ("NewTasksAreManual",0),("SpreadActualCost",0),("SpreadPercentComplete",0),
        ("TaskUpdatesResource",1),("WeekStartDay",1),
    ]
    for k,v in settings: elem(p,k,v)
    attrs=elem(p,"ExtendedAttributes")
    custom=[("188743731","Text1","Source / hypothèses"),("188743732","Text2","Retard de nivellement (jours écoulés)"),("188743786","Cost1","Coût main-d’œuvre (USD)"),("188743787","Cost2","Coût capital (USD)")]
    for fid,name,alias in custom:
        a=elem(attrs,"ExtendedAttribute");elem(a,"FieldID",fid);elem(a,"FieldName",name);elem(a,"Alias",alias)
    calendars=elem(p,"Calendars");c=elem(calendars,"Calendar")
    for k,v in [("UID",1),("Name","Standard — 8h/j — sans jours fériés"),("IsBaseCalendar",1),("BaseCalendarUID",-1)]:elem(c,k,v)
    weekdays=elem(c,"WeekDays")
    for day in range(1,8):
        w=elem(weekdays,"WeekDay");elem(w,"DayType",day);elem(w,"DayWorking",int(2<=day<=6))
        if 2<=day<=6:
            periods=elem(w,"WorkingTimes")
            for a,b in [("08:00:00","12:00:00"),("13:00:00","17:00:00")]:
                period=elem(periods,"WorkingTime");elem(period,"FromTime",a);elem(period,"ToTime",b)
    tx=elem(p,"Tasks")
    for i,t in tasks.items():
        x=elem(tx,"Task")
        note=(f"Source : cas KEL156, annexes 5/6/8/9, Task ID {i}, WBS {t['wbs']}. "
              f"Charge totale : {t['work_minutes']/DAY:g} jours-personne. "
              f"Durée : {t['duration_minutes']/DAY:g} jours ouvrés. "
              f"Retard de nivellement : {t['delay_edays']} jours ÉCOULÉS. "
              "Calendrier lundi-vendredi, 08h-12h / 13h-17h, sans jours fériés. "
              "Aucune heure supplémentaire planifiée. Coûts antérieurs de l'équipe de planification exclus.")
        if i==1:
            note += (f" RÉSULTATS : mise en production {summary['deployment'][:10]}, clôture {summary['finish'][:10]}; "
                     f"main-d'œuvre {summary['labour_cost']:,.2f} USD; capital {summary['capital_cost']:,.2f} USD; "
                     f"total {summary['total_cost']:,.2f} USD. Voir Synthese_AD_High_Tech.pdf pour les cinq réponses.")
        if i==3:note += " Charge de gestion conservée à 127 j, liaison 59FF selon le cas; n'inclut pas la planification passée."
        if i==35:note += " Coût fixe unique : 12 postes × 3 000 USD + 5 serveurs × 12 500 USD = 98 500 USD; licences déjà détenues."
        if i==58:note += " Livraison opérationnelle; la clôture administrative est la tâche 59."
        values=[
            ("UID",i),("ID",i),("Name",t["name"]),("Type",2),("IsNull",0),
            ("WBS",t["wbs"]),("OutlineNumber",t["wbs"]),("OutlineLevel",t["outline_level"]),
            ("Priority",500),("Start",iso_date(t["start"])),("Finish",iso_date(t["finish"],True)),
            ("Duration",duration(t["duration_minutes"])),("DurationFormat",7),
            ("Work",duration(t["work_minutes"])),("Stop",iso_date(t["start"])),("Resume",iso_date(t["start"])),
            ("EffortDriven",0),("Estimated",0),("Milestone",0),("Summary",int(t["summary"])),
            ("Critical",int(t["critical"])),("IsSubproject",0),("IsSubprojectReadOnly",0),
            ("ExternalTask",0),("EarlyStart",iso_date(t["start"])),("EarlyFinish",iso_date(t["finish"],True)),
            ("LateStart",iso_date(t["late_start"])),("LateFinish",iso_date(t["late_finish"],True)),
            ("StartSlack",t["slack_minutes"]*10),("FinishSlack",t["slack_minutes"]*10),
            ("TotalSlack",t["slack_minutes"]*10),
            ("FixedCost",f"{t['fixed_cost']:.2f}" if not t["summary"] else "0.00"),("FixedCostAccrual",3),
            ("PercentComplete",0),("PercentWorkComplete",0),
            ("Cost",f"{t['labour_cost']+t['fixed_cost']:.2f}"),("OvertimeCost","0.00"),
            ("OvertimeWork",duration(0)),("ActualDuration",duration(0)),("ActualCost","0.00"),
            ("ActualWork",duration(0)),("RemainingDuration",duration(t["duration_minutes"])),
            ("RemainingCost",f"{t['labour_cost']+t['fixed_cost']:.2f}"),("RemainingWork",duration(t["work_minutes"])),
            ("ConstraintType",0),("CalendarUID",-1),("LevelAssignments",0),("LevelingCanSplit",0),
            # MSPDI encodes task leveling delay in tenths of ELAPSED minutes.
            ("LevelingDelay",t["delay_edays"]*24*60*10),("LevelingDelayFormat",8),
            ("IgnoreResourceCalendar",0),("Notes",note),
        ]
        for k,v in values:elem(x,k,v)
        for pred,kind in t["predecessor_links"]:
            link=elem(x,"PredecessorLink")
            for k,v in [("PredecessorUID",pred),("Type",{"FF":0,"FS":1,"SF":2,"SS":3}[kind]),("CrossProject",0),("LinkLag",0),("LagFormat",7)]:elem(link,k,v)
        for fid,value in [("188743731",f"Cas KEL156 — annexes 5 à 9; ID {i}"),("188743732",str(t["delay_edays"])),("188743786",f"{t['labour_cost']:.2f}"),("188743787",f"{t['fixed_cost']:.2f}")]:
            a=elem(x,"ExtendedAttribute");elem(a,"FieldID",fid);elem(a,"Value",value)
        elem(x,"Active",1);elem(x,"Manual",0)
    rx=elem(p,"Resources")
    for code,r in resources.items():
        x=elem(rx,"Resource")
        hours=sum(t["duration_minutes"]/60*float(u) for t in tasks.values() if not t["summary"] for c,u in t["assign"] if c==code)
        cost=hours*r["standard_rate"]
        for k,v in [("UID",r["uid"]),("ID",r["uid"]),("Name",r["name"]),("Type",1),("IsNull",0),
                    ("Initials",code),("Group","Geneva — externe" if code.startswith("D") else "A&D — interne"),
                    ("MaxUnits",1),("PeakUnits",summary["resource_peak_units"][code]),("OverAllocated",0),
                    ("AccrueAt",3),("Work",duration(round(hours*60))),("RegularWork",duration(round(hours*60))),
                    ("OvertimeWork",duration(0)),("RemainingWork",duration(round(hours*60))),
                    ("StandardRate",r["standard_rate"]),("StandardRateFormat",2),("Cost",f"{cost:.2f}"),
                    ("OvertimeRate",r["overtime_rate"]),("OvertimeRateFormat",2),("OvertimeCost","0.00"),
                    ("CostPerUse",0),("ActualCost",0),("ActualWork",duration(0)),("RemainingCost",f"{cost:.2f}"),
                    ("CalendarUID",1)]:elem(x,k,v)
    ax=elem(p,"Assignments");aid=0
    for i,t in tasks.items():
        if t["summary"]:continue
        for code,units in t["assign"]:
            aid+=1;r=resources[code];w=int(t["duration_minutes"]*units);cost=Decimal(w)/60*r["standard_rate"]
            x=elem(ax,"Assignment")
            for k,v in [("UID",aid),("TaskUID",i),("ResourceUID",r["uid"]),("PercentWorkComplete",0),
                        ("ActualCost",0),("ActualOvertimeCost",0),("ActualOvertimeWork",duration(0)),
                        ("ActualWork",duration(0)),("Cost",f"{cost:.2f}"),("Finish",iso_date(t["finish"],True)),
                        ("RegularWork",duration(w)),("RemainingCost",f"{cost:.2f}"),("RemainingWork",duration(w)),
                        ("Start",iso_date(t["start"])),("Units",units),("Work",duration(w)),
                        ("WorkContour",0),("CostRateTable",0)]:elem(x,k,v)
    # MSPDI currency amounts are stored in cents; hourly rates remain USD/hour.
    currency_tags={"Cost","FixedCost","ActualCost","RemainingCost","OvertimeCost","ActualOvertimeCost","CostPerUse"}
    for node in p.iter():
        tag=node.tag.rsplit("}",1)[-1]
        if tag in currency_tags and node.text:
            node.text=f"{Decimal(node.text)*100:.2f}"
        if tag=="ExtendedAttribute":
            fid=node.find(f"{{{NS}}}FieldID")
            value=node.find(f"{{{NS}}}Value")
            if fid is not None and fid.text in ("188743786","188743787") and value is not None:
                value.text=f"{Decimal(value.text)*100:.2f}"
    # MSPDI is an ordered schema: emit elements in the prescribed sequence.
    orders=json.loads((ROOT/"data/mspdi_element_order.json").read_text())
    for node in p.iter():
        tag=node.tag.rsplit("}",1)[-1]
        if tag in orders:
            ranks={name:rank for rank,name in enumerate(orders[tag])}
            node[:]=sorted(node,key=lambda child:ranks[child.tag.rsplit("}",1)[-1]])
    ET.indent(p)
    file=OUT/"AD_High_Tech_Project.xml"
    ET.ElementTree(p).write(file,encoding="utf-8",xml_declaration=True)
    return file


def write_tables(tasks,resources):
    fields=["ID","WBS","Tâche","Durée (j ouvrés)","Travail (h)","Début","Fin","Prédécesseurs (notation EN)","Nivellement (j écoulés)","Marge totale (j)","Critique","Coût travail (USD)","Capital (USD)","Coût total (USD)","Ressources"]
    rows=[]
    for i,t in tasks.items():
        rows.append([i,t["wbs"],t["name"],t["duration_minutes"]/DAY,t["work_minutes"]/60,
                     iso_date(t["start"]),iso_date(t["finish"],True),t["predecessors"],t["delay_edays"],
                     t["slack_minutes"]/DAY,"Oui" if t["critical"] else "Non",float(t["labour_cost"]),float(t["fixed_cost"]),
                     float(t["labour_cost"]+t["fixed_cost"]),", ".join(f"{resources[r]['name']} [{u*100:g}%]" for r,u in t["assign"])])
    with (OUT/"AD_High_Tech_Taches.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f,delimiter=";");writer.writerow(fields);writer.writerows(rows)
    return fields,rows


def main():
    OUT.mkdir(exist_ok=True)
    tasks,resources=read_data();plan=schedule(tasks);summary=analyse(tasks,resources,plan)
    file=create_xml(tasks,resources,summary);write_tables(tasks,resources)
    (OUT/"calculs.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print(file)


if __name__ == "__main__":main()
