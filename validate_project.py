"""Audit the generated Project file, separately from the scheduling algorithm."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
NS={'p':'http://schemas.microsoft.com/project'}


def value(node,name):
    return node.findtext('p:'+name,namespaces=NS)


def minutes(text):
    m=re.fullmatch(r'PT(\d+)H(\d+)M(\d+)S',text)
    assert m,text
    return Decimal(m[1])*60+Decimal(m[2])+Decimal(m[3])/60


def usd(node,name='Cost'):
    return Decimal(value(node,name) or '0')/100


def main():
    project=ET.parse(ROOT/'livrables/AD_High_Tech_Project.xml').getroot()
    tasks={int(value(t,'UID')):t for t in project.findall('p:Tasks/p:Task',NS)}
    resources={int(value(r,'UID')):r for r in project.findall('p:Resources/p:Resource',NS)}
    assignments=project.findall('p:Assignments/p:Assignment',NS)
    leaves={i:t for i,t in tasks.items() if value(t,'Summary')=='0'}
    assert set(tasks)==set(range(1,60))
    assert len(resources)==11 and len(assignments)==103
    assert value(project,'StartDate')=='2003-05-26T08:00:00'
    assert value(tasks[58],'Finish')=='2003-11-04T17:00:00'
    assert value(tasks[59],'Finish')=='2003-11-18T17:00:00'
    assert value(project,'MinutesPerDay')=='480'
    assert value(project,'MinutesPerWeek')=='2400'
    assert not project.findall('.//p:Exceptions/p:Exception',NS)
    assert usd(tasks[1])==Decimal('943480')
    assert sum((usd(t,'FixedCost') for t in leaves.values()),Decimal(0))==Decimal('98500')
    assert sum((usd(t) for t in leaves.values()),Decimal(0))==usd(tasks[1])
    assert sum((minutes(value(t,'Work')) for t in leaves.values()),Decimal(0))==Decimal('8488.8')*60
    work=defaultdict(Decimal);cost=defaultdict(Decimal);events=defaultdict(lambda:defaultdict(Decimal))
    for a in assignments:
        taskid=int(value(a,'TaskUID'));rid=int(value(a,'ResourceUID'))
        assert taskid in leaves and rid in resources
        t=tasks[taskid];r=resources[rid]
        w=minutes(value(a,'Work'));units=Decimal(value(a,'Units'))
        assert w==minutes(value(t,'Duration'))*units
        rate=Decimal(value(r,'StandardRate'))
        assert usd(a)==w/60*rate
        assert value(a,'Start')==value(t,'Start')
        assert value(a,'Finish')==value(t,'Finish')
        work[taskid]+=w;cost[taskid]+=usd(a)
        events[rid][value(a,'Start')]+=units
        events[rid][value(a,'Finish')]-=units
    for i,t in leaves.items():
        assert work[i]==minutes(value(t,'Work'))
        assert cost[i]+usd(t,'FixedCost')==usd(t)
    assert sum(cost.values())==Decimal('844980')
    for rid,changes in events.items():
        load=Decimal(0)
        for dt,delta in sorted(changes.items()):
            load+=delta
            assert load<=Decimal(value(resources[rid],'MaxUnits')), (rid,dt,load)
        assert load==0
    for i,t in tasks.items():
        assert value(t,'Manual')=='0'
        start=datetime.fromisoformat(value(t,'Start'));finish=datetime.fromisoformat(value(t,'Finish'))
        assert start<=finish and start.weekday()<5 and finish.weekday()<5
        for link in t.findall('p:PredecessorLink',NS):
            p=tasks[int(value(link,'PredecessorUID'))]
            kind=value(link,'Type')
            a=datetime.fromisoformat(value(p,'Finish' if kind in ('0','1') else 'Start'))
            z=finish if kind=='0' else start
            assert a<=z, (i,kind)
        wbs=value(t,'WBS')
        if value(t,'Summary')=='1':
            children=[u for u in leaves.values() if value(u,'WBS').startswith(wbs+'.')]
            assert value(t,'Start')==min(value(u,'Start') for u in children)
            assert value(t,'Finish')==max(value(u,'Finish') for u in children)
            assert usd(t)==sum((usd(u) for u in children),Decimal(0))
    for i,days in {13:5,15:6,25:11,31:23,44:14}.items():
        assert int(value(tasks[i],'LevelingDelay'))==days*14400
        assert value(tasks[i],'LevelingDelayFormat')=='8'
    for i,pred,kind in [(3,59,'0'),(19,16,'3'),(20,11,'3')]:
        assert any(value(x,'PredecessorUID')==str(pred) and value(x,'Type')==kind for x in tasks[i].findall('p:PredecessorLink',NS))
    print(f'PASS: 59 lignes ({len(leaves)} tâches détaillées), 11 ressources, 103 affectations ; dates et liaisons cohérentes.')
    print('PASS: 8 488,8 h ; main-d’œuvre 844 980 USD ; capital 98 500 USD ; total 943 480 USD.')
    print('PASS: aucune surcharge, jours écoulés et tarifs respectés, coûts matériels comptés une seule fois.')


if __name__=='__main__':main()
