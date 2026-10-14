"""Render the French companion report and a readable, vector Gantt PDF."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether,
)
from reportlab.pdfgen.canvas import Canvas

import build_project as b

ROOT=b.ROOT
OUT=b.OUT
FONT_DIR=Path('/usr/share/fonts/truetype/dejavu')
pdfmetrics.registerFont(TTFont('DejaVu',str(FONT_DIR/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVu-Bold',str(FONT_DIR/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVu-Bold')
NAVY=colors.HexColor('#132D46')
TEAL=colors.HexColor('#007F83')
RED=colors.HexColor('#BD3B45')
PALE=colors.HexColor('#EFF4F8')
GRAY=colors.HexColor('#546575')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleAD',fontName='DejaVu-Bold',fontSize=25,leading=31,textColor=NAVY,spaceAfter=12))
styles.add(ParagraphStyle(name='SubtitleAD',fontName='DejaVu',fontSize=11,leading=16,textColor=GRAY,spaceAfter=16))
styles.add(ParagraphStyle(name='HAD',fontName='DejaVu-Bold',fontSize=13,leading=18,textColor=TEAL,spaceBefore=12,spaceAfter=8))
styles.add(ParagraphStyle(name='BodyAD',fontName='DejaVu',fontSize=9.2,leading=14,spaceAfter=8,textColor=NAVY))
styles.add(ParagraphStyle(name='SmallAD',fontName='DejaVu',fontSize=7.5,leading=11,spaceAfter=5,textColor=GRAY))
styles.add(ParagraphStyle(name='CellAD',fontName='DejaVu',fontSize=8.1,leading=11,textColor=NAVY))
styles.add(ParagraphStyle(name='CellHeadAD',fontName='DejaVu-Bold',fontSize=8,leading=11,textColor=colors.white))


def para(s,style='BodyAD'):
    return Paragraph(s,styles[style])


def table(headers,rows,widths):
    data=[[para(escape(str(s)),'CellHeadAD') for s in headers]]
    data += [[para(escape(str(s)),'CellAD') for s in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LINEBELOW',(0,0),(-1,0),0.7,TEAL),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    return t


def footer(canvas,doc):
    canvas.setStrokeColor(TEAL);canvas.setLineWidth(.8)
    canvas.line(19*mm,17*mm,A4[0]-19*mm,17*mm)
    canvas.setFont('DejaVu',7);canvas.setFillColor(GRAY)
    canvas.drawString(19*mm,12*mm,'A&D High Tech (A) • Cas KEL156 • Planning au 26 mai 2003')
    canvas.drawRightString(A4[0]-19*mm,12*mm,str(doc.page))


def make_summary(T,R,S):
    story=[]
    def add(s,style='BodyAD'):story.append(para(s,style))
    add('A&amp;D HIGH TECH','SubtitleAD')
    add('Planning et réponses<br/>aux questions du cas','TitleAD')
    add('Boutique en ligne • Microsoft Project Professionnel<br/>Dates et montants historiques du cas, en dollars américains.','SubtitleAD')
    story.append(table(['Indicateur','Résultat de référence'],[
        ('Début du projet','26 mai 2003 à 08h00'),
        ('Mise en production — tâche 58','4 novembre 2003 à 17h00'),
        ('Clôture complète — tâche 59','18 novembre 2003 à 17h00'),
        ('Durée totale','127 jours ouvrés / 1 016 heures de durée'),
        ('Charge cumulée','8 488,8 heures de travail'),
        ('Budget total','943 480 USD'),
    ],[77*mm,95*mm]))
    add('1. Quelle est la date prévisionnelle de fin ?','HAD')
    add('Le projet se termine le <b>18 novembre 2003</b>, après 127 jours ouvrés à compter du 26 mai. '
        'La boutique est mise en production le <b>4 novembre</b>. Les dix jours ouvrés suivants correspondent à '
        'la clôture du projet ; ils ne doivent pas être confondus avec la date de lancement commercial.')
    add('Hypothèses de calcul','HAD')
    add('Calendrier lundi–vendredi, 08h–12h et 13h–17h : 8 h/jour, 40 h/semaine, <b>aucun jour férié</b>. '
        'Les estimations sont des jours-personne, divisés par la somme des unités des ressources affectées. '
        'Les retards de nivellement sont des jours <b>écoulés</b>, week-ends compris, puis le démarrage est reporté au prochain créneau ouvré. '
        'Les coûts déjà engagés par l’équipe de planification sont exclus ; les 127 jours de gestion future de Chris Johnson sont conservés.')
    add('Données : annexes 5 à 9 du cas « A&D High Tech (A): Managing Projects for Success », KEL156, et document « AD High Tech case questions » fourni. '
        'Les intitulés anglais et les ID du cas sont conservés dans le fichier Project pour permettre le rapprochement.','SmallAD')

    story.append(PageBreak())
    add('2. Quel est le coût total ?','TitleAD')
    add('Le budget prévisionnel est de <b>943 480 USD</b>, sans heures supplémentaires ni nouvelle acquisition de licences. '
        'Il s’agit du coût des travaux restant à réaliser à partir du 26 mai 2003.')
    internal=external=0
    resource_rows=[]
    for code,r in R.items():
        hours=sum(t['duration_minutes']/60*float(u) for t in T.values() if not t['summary'] for c,u in t['assign'] if c==code)
        cost=hours*r['standard_rate']
        if code.startswith('D'):external+=cost
        else:internal+=cost
        resource_rows.append((r['name'].split(' (')[0],f"{hours:,.1f}".replace(',',' '),f"{r['standard_rate']} USD/h",f"{cost:,.0f}".replace(',',' ')))
    story.append(table(['Poste','Calcul / contenu','Coût (USD)'],[
        ('Main-d’œuvre interne','8 ressources A&D, à 75 USD/h',f'{internal:,.0f}'.replace(',',' ')),
        ('Main-d’œuvre externe','3 développeurs Geneva ; 165 / 175 / 175 USD/h',f'{external:,.0f}'.replace(',',' ')),
        ('Total main-d’œuvre','8 488,8 heures', '844 980'),
        ('Postes de travail','12 × 3 000 USD','36 000'),
        ('Serveurs','5 × 12 500 USD','62 500'),
        ('Total capital / matériel','Licences déjà disponibles : 0 USD de nouvelle acquisition','98 500'),
        ('TOTAL PROJET','Main-d’œuvre + matériel','943 480'),
    ],[42*mm,99*mm,31*mm]))
    add('Contrôle des ressources','HAD')
    story.append(table(['Ressource','Travail (h)','Taux standard','Coût (USD)'],resource_rows,[73*mm,28*mm,34*mm,37*mm]))
    add('Dans Project, le matériel est saisi une seule fois comme coût fixe de 98 500 USD sur la tâche 35 '
        '(Create Development Environment). Les champs personnalisés Coût1 et Coût2 donnent respectivement la main-d’œuvre et le capital. '
        'Les lignes récapitulatives agrègent leurs sous-tâches : ne pas additionner ces lignes aux tâches détaillées.','SmallAD')

    story.append(PageBreak())
    add('3. Chemins critiques et risque','TitleAD')
    add('Le réseau comporte plusieurs branches à marge nulle. Elles se rejoignent dans les tests d’assemblage '
        '(tâche 53) et les tests système (54). Réduire la durée d’une seule branche ne garantit donc pas une fin plus tôt.')
    add('Branches critiques représentatives','HAD')
    branches=[
        ('Exigences communes','13 → 14 → 16 → 17 ; ou 13 → 14 → 16 —DD→ 19. Les tâches 17 et 19 finissent ensemble et conditionnent la conception.'),
        ('Catalogue et assemblage 1','23 → 42 → 43 → 52 → 53'),
        ('Catalogue, panier et interface ERP','23 → 24 → 29 → 48 → 53'),
        ('Paiements et commande','25 → 44 → 45 → 53 ; 43 → 45 constitue aussi une branche bloquante.'),
        ('Modèle de données','28 → 47 → 53'),
        ('Préparation des tests','31 → 32 → 33 → 54 ; cette branche rejoint le réseau après 53.'),
        ('Tronc final commun','53 → 54 → 55 → 57 → 58 → 59'),
    ]
    story.append(table(['Branche','ID des tâches du cas'],branches,[56*mm,116*mm]))
    add('Lecture : les flèches indiquent des liaisons fin-début ; DD signifie début-début (SS dans le XML). '
        'Les liens passant par les tâches récapitulatives 10, 11, 21, 40, 50, 51 et 56 restent présents dans Project. '
        'Les branches ci-dessus sont des extraits du réseau, avec les contraintes de phase héritées.','SmallAD')
    add('Gestion du projet et nivellement','HAD')
    add('La tâche 3, <i>Manage Project</i>, apparaît également critique : sa charge de 127 jours et sa liaison fin-fin '
        'depuis la tâche 59 sont imposées par le cas. Elle accompagne le projet ; ce n’est pas une activité technique '
        'supplémentaire à placer après le déploiement.')
    add('Les retards de nivellement sont conservés : tâche 13 = 5 j écoulés ; 15 = 6 ; 25 = 11 ; 31 = 23 ; 44 = 14. '
        'Ils évitent de dépasser la disponibilité des ressources. Le calcul tient compte des week-ends lors de l’analyse des marges. '
        'Les tâches 5, 6 et 8 restent proches du critique avec seulement un jour ouvré de marge dans ce modèle. '
        'Ces marges concernent le réseau avec les retards fournis ; déplacer une tâche exige de revérifier les charges des ressources.')
    add('Liste des tâches détaillées à marge nulle : '+', '.join(str(i) for i in S['critical_leaf_ids'])+'. '
        'Le fichier CSV donne la marge de chacune des 59 lignes.','SmallAD')

    story.append(PageBreak())
    add('4. Le délai paraît-il tenable ?','TitleAD')
    add('<b>Le planning de référence permet une livraison avant Noël et avant la fin novembre, mais la tenue du délai reste fragile.</b> '
        'La mise en production est prévue le 4 novembre et la clôture le 18 novembre. Le cas ne fixe pas de date précise '
        'pour le début de la saison des achats : la cible commerciale doit être confirmée avec le sponsor.')
    story.append(table(['Source de risque','Conséquence pour le délai'],[
        ('Plusieurs branches critiques simultanées','Une dérive sur l’une d’elles peut bloquer les tests puis le déploiement.'),
        ('Développeurs Geneva non encore nommés','Le modèle suppose leur disponibilité aux dates prévues et leur capacité à produire aux estimations du cas.'),
        ('ERP fortement personnalisé','L’interface et les tests d’intégration peuvent nécessiter des corrections imprévues ; la connaissance des anciens consultants manque.'),
        ('Ressources pleinement engagées','Aucune surcharge au planning de référence, mais des pointes à 100 % : les reprises et absences ne sont pas couvertes.'),
        ('Estimations ponctuelles, sans réserve explicite','Aucune distribution de durée ni provision de risque n’est fournie ; une probabilité de réussite chiffrée serait inventée.'),
        ('Soutien et disponibilité technique','Les supports des tâches 38 et 39 vont jusqu’au déploiement du 4 novembre ; leur couverture doit être prolongée si le lancement glisse.'),
    ],[58*mm,114*mm]))
    add('Exemple de sensibilité, sans valeur probabiliste','HAD')
    add('Si les tests système prennent une semaine ouvrée supplémentaire et qu’aucun rattrapage n’est réalisé, '
        'le tronc final se décale d’environ une semaine : mise en production le <b>11 novembre</b>, clôture le <b>25 novembre</b>. '
        'Il faut alors ajuster la couverture du support et recontrôler les ressources. La marge commerciale diminue avant même Noël.')
    add('Avis','HAD')
    add('L’objectif est <b>réalisable selon les données du cas</b>. Une confiance élevée n’est pas justifiée sans validation '
        'de la disponibilité Geneva, des estimations de l’interface ERP et des critères de recette. Le risque d’exécution est '
        '<b>élevé</b>, surtout à l’approche des tests intégrés ; aucun pourcentage de succès ne peut être déduit des seules annexes.')

    story.append(PageBreak())
    add('5. Recommandations au chef de projet','TitleAD')
    add('Le scénario de base n’est pas en retard par rapport à Noël. Les mesures suivantes sécurisent la livraison '
        'et préparent une réaction si la prévision se dégrade ; elles ne sont pas appliquées silencieusement au fichier de référence.')
    recommendations=[
        ('Fixer la cible commerciale','Faire approuver une date précise de disponibilité de la boutique, les critères go/no-go et une réserve avant le pic des achats. Séparer cette date de la clôture administrative.'),
        ('Sécuriser les trois développeurs','Obtenir de Geneva les noms, disponibilités, compétences et engagements ; anticiper l’accès aux environnements et la montée en compétence sur l’ERP.'),
        ('Piloter toutes les branches critiques','Revoir chaque semaine les tâches 23–24, 25–44, 28–47, 29–48, 42–43 et 31–33. Suivre leurs dates prévisionnelles, pas seulement le pourcentage réalisé.'),
        ('Tester tôt l’intégration ERP','Réaliser un test technique de bout en bout et préparer des données de recette avant les tests système. Traiter en priorité les flux de commande et de paiement.'),
        ('Préparer une accélération ciblée','Si nécessaire, étudier un chevauchement conception/développement fondé sur des exigences stables, au lieu d’attendre toute une phase. Valider les nouveaux liens et les risques de reprise avant de modifier le planning.'),
        ('Arbitrer coût, ressources et réserve','Ajouter des compétences sur les branches réellement bloquantes et recalculer le réseau complet. Les heures supplémentaires Geneva coûtent 230/250/250 USD/h ; ne pas supposer une accélération proportionnelle.'),
        ('Protéger la recette et le support','Préserver les tests système et de validation. Prolonger le support infrastructure/DBA en cas de dérive et prévoir surveillance, retour arrière et décision formelle de mise en production.'),
        ('Maîtriser le périmètre','Geler les exigences minimales validées et soumettre tout ajout à une analyse d’impact. Ne différer des fonctions qu’avec accord du sponsor, le cas imposant une expérience client cohérente entre canaux.'),
    ]
    story.append(table(['Action','Application'],recommendations,[54*mm,118*mm]))

    story.append(PageBreak())
    add('Ouvrir et exploiter le fichier','TitleAD')
    add('Fichier principal : <b>AD_High_Tech_Project.xml</b>. Il s’agit du format d’échange natif '
        '<b>Microsoft Project XML (MSPDI)</b>, compatible avec l’application de bureau Project Professionnel. '
        'Le fichier livré est un XML ; l’enregistrement en MPP se fait dans Microsoft Project.')
    for n,s in enumerate([
        'Télécharger le fichier XML. Dans Project Professionnel, choisir <b>Fichier → Ouvrir → Parcourir</b> et sélectionner le type <b>XML</b> ou <b>Tous les fichiers</b>.',
        'Sélectionner <b>AD_High_Tech_Project.xml</b>. Si l’assistant pose la question, choisir <b>Comme nouveau projet</b>.',
        'Contrôler le début au <b>26/05/2003</b>, la fin de la tâche 58 au <b>04/11/2003</b> et la fin du projet au <b>18/11/2003</b>. Ne pas remplacer les dates historiques par celles de l’année en cours.',
        'Choisir <b>Fichier → Enregistrer sous</b>, puis le format <b>Projet (*.mpp)</b>. Ne pas simplement renommer l’extension du XML.',
    ],1):add(f'<b>{n}.</b> {s}')
    add('Vues et colonnes utiles','HAD')
    add('<b>Diagramme de Gantt</b> : afficher toutes les sous-tâches et cocher « Tâches critiques ». '
        'Ajouter Durée, Travail, Prédécesseurs, Marge totale, Coût, Coûts fixes et Retard de nivellement. '
        '<b>Tableau des ressources</b> : contrôler les taux standard, taux d’heures supplémentaires et disponibilités. '
        '<b>Utilisation des ressources</b> : examiner les affectations à 10 %, 50 % et 90 %.')
    add('Champs personnalisés : <b>Coût1 = main-d’œuvre</b>, <b>Coût2 = capital</b>, '
        '<b>Texte1 = source</b>, <b>Texte2 = retard en jours écoulés</b>. '
        'La notation des liens du CSV est anglaise : FS = fin-début ; SS = début-début ; FF = fin-fin. '
        'Project peut afficher ces codes différemment selon la langue de l’application.')
    add('Vérifications réalisées','HAD')
    add('Contrôle des liens et charges, calcul des dates et marges, totalisation des coûts, vérification de la charge maximale '
        'par ressource (aucun dépassement de 100 %). Le XML est conforme au schéma MSPDI représenté par MPXJ 16.10.0 '
        'et relu avec ce lecteur indépendant : 59 lignes, 11 ressources, 103 affectations, 8 488,8 h et 943 480 USD.')
    add('Microsoft Project Professionnel n’est pas installé dans cet environnement : l’ouverture dans son interface et '
        'l’enregistrement en MPP restent à effectuer sur votre ordinateur. La compatibilité est vérifiée par le schéma et '
        'le lecteur MSPDI, sans prétendre à un essai de l’application Microsoft.','SmallAD')
    add('Fichiers complémentaires','HAD')
    add('<b>Gantt_AD_High_Tech.pdf</b> : diagramme de toutes les tâches détaillées et des phases. '
        '<b>AD_High_Tech_Taches.csv</b> : tableau de contrôle détaillé. '
        '<b>calculs.json</b> : résultats structurés. '
        'Le dossier du dépôt contient aussi les données et le script permettant de régénérer le planning.')
    doc=SimpleDocTemplate(str(OUT/'Synthese_AD_High_Tech.pdf'),pagesize=A4,
        leftMargin=19*mm,rightMargin=19*mm,topMargin=19*mm,bottomMargin=23*mm,
        title='A&D High Tech — Planning et réponses aux questions',author='Analyse du cas KEL156 fourni')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


def gantt(T):
    pagesize=landscape(A4)
    W,H=pagesize
    c=Canvas(str(OUT/'Gantt_AD_High_Tech.pdf'),pagesize=pagesize)
    c.setTitle('A&D High Tech — Diagramme de Gantt')
    rows=[i for i in T if i!=1]
    groups=[rows[:29],rows[29:]]
    x0=380; x1=W-23
    first=datetime(2003,5,26); last=datetime(2003,11,24)
    span=(last-first).total_seconds()
    def xdate(dt):return x0+(dt-first).total_seconds()/span*(x1-x0)
    for page,ids in enumerate(groups,1):
        c.setFillColor(NAVY);c.setFont('DejaVu-Bold',18)
        c.drawString(22,H-32,'A&D High Tech • Diagramme de Gantt')
        c.setFont('DejaVu',8);c.setFillColor(GRAY)
        c.drawString(22,H-50,'26 mai–18 novembre 2003 • Lundi–vendredi • 8 h/j • Aucun jour férié • Rouge : marge nulle')
        top=H-91; step=14.6;bottom=top-len(ids)*step
        c.setFillColor(PALE);c.rect(22,top+4,W-44,24,fill=1,stroke=0)
        c.setFillColor(NAVY);c.setFont('DejaVu-Bold',7)
        c.drawString(25,top+11,'ID   WBS / Tâche')
        c.drawString(328,top+11,'Durée')
        for month in range(6,12):
            d=datetime(2003,month,1);x=xdate(d)
            c.setStrokeColor(colors.HexColor('#D8E2EA'));c.setLineWidth(.5);c.line(x,bottom,x,top+6)
            c.setFont('DejaVu-Bold',7);c.setFillColor(NAVY)
            c.drawString(x+2,top+11,['','','','','','','Juin','Juil.','Août','Sept.','Oct.','Nov.'][month])
        for n,i in enumerate(ids):
            t=T[i];y=top-(n+1)*step
            if n%2==0:
                c.setFillColor(colors.HexColor('#F7F9FB'));c.rect(22,y-1,W-44,step,fill=1,stroke=0)
            for month in range(6,12):
                xm=xdate(datetime(2003,month,1));c.setStrokeColor(colors.HexColor('#D8E2EA'));c.line(xm,y-1,xm,y+step-1)
            c.setFillColor(NAVY);font='DejaVu-Bold' if t['summary'] else 'DejaVu'
            c.setFont(font,6.8)
            label=f"{i:2}   {t['wbs']}  {t['name']}"
            while pdfmetrics.stringWidth(label,font,6.8)>297:label=label[:-2]+'…'
            c.drawString(25,y+3,label)
            c.drawRightString(365,y+3,f"{t['duration_minutes']/480:g} j")
            start=b.start_date(t['start']);end=b.finish_date(t['finish'])
            a,z=xdate(start),xdate(end)
            color=NAVY if t['summary'] else RED if t['critical'] else TEAL
            c.setFillColor(color);c.setStrokeColor(color)
            if t['summary']:
                c.rect(a,y+6,max(1,z-a),2,fill=1,stroke=0)
                for xm in [a,z]:c.line(xm,y+3,xm,y+8)
            else:c.roundRect(a,y+3,max(1,z-a),6,1.4,fill=1,stroke=0)
        for task,colour in [(58,TEAL),(59,NAVY)]:
            xm=xdate(b.finish_date(T[task]['finish']))
            c.setStrokeColor(colour);c.setLineWidth(.8);c.setDash(2,2);c.line(xm,bottom,xm,top+7);c.setDash()
        c.setFillColor(GRAY);c.setFont('DejaVu',7)
        c.drawString(22,24,'Traits verticaux : production 04/11 et clôture 18/11. Les liens complets figurent dans le fichier Microsoft Project.')
        c.drawRightString(W-23,24,f'{page}/2')
        c.showPage()
    c.save()


def main():
    T,R=b.read_data();plan=b.schedule(T);S=b.analyse(T,R,plan)
    make_summary(T,R,S);gantt(T)
    print(OUT/'Synthese_AD_High_Tech.pdf')
    print(OUT/'Gantt_AD_High_Tech.pdf')


if __name__=='__main__':main()
