# A&D High Tech — Microsoft Project

Planning tiré des deux PDF fournis : cas KEL156 « A&D High Tech (A): Managing Projects for Success » et « AD High Tech case questions ».

**[Télécharger le ZIP complet](https://github.com/Nath-ct-deja-pris/project-management/raw/refs/heads/main/livrables/AD_High_Tech_Complet.zip)**

Le ZIP contient le fichier à ouvrir dans Microsoft Project, la synthèse répondant aux cinq questions, le Gantt PDF et le tableau des tâches. Si le dépôt est privé, se connecter à GitHub avec un compte qui y a accès avant de télécharger.

## Livrables

- `livrables/AD_High_Tech_Project.xml` : fichier Microsoft Project XML (MSPDI), ouvrable dans **Microsoft Project Professionnel pour Windows**.
- `livrables/Synthese_AD_High_Tech.pdf` : réponses en français aux cinq questions et guide d'ouverture.
- `livrables/Gantt_AD_High_Tech.pdf` : vue imprimable du planning.
- `livrables/AD_High_Tech_Taches.csv` : tableau détaillé de contrôle, séparateur point-virgule, UTF-8 avec BOM.
- `livrables/calculs.json` : résultats structurés.

Dans Project : **Fichier → Ouvrir → Parcourir**, choisir XML ou Tous les fichiers, ouvrir le XML **comme nouveau projet**, puis **Enregistrer sous → Projet (*.mpp)**. Changer seulement l'extension du fichier ne le convertit pas en MPP.

## Résultats

- Début : **26 mai 2003**.
- Mise en production (ID 58) : **4 novembre 2003**.
- Clôture (ID 59) : **18 novembre 2003**, après **127 jours ouvrés**.
- Travail : **8 488,8 heures**.
- Main-d'œuvre : **844 980 USD** ; capital : **98 500 USD** ; total : **943 480 USD**.
- 59 lignes du WBS, 11 ressources, 103 affectations ; aucune surcharge dans le planning de référence.

## Hypothèses et sources

- Dates historiques du cas, pas l'année de la page de couverture des questions.
- Début au 26/05/2003, date de référence de la WBS (cas p. 5).
- Calendrier lundi–vendredi, 08h–12h / 13h–17h, 8 h/j et 40 h/semaine ; **aucun jour férié**.
- Charges de l'annexe 6 en **jours-personne** : durée = charge / somme des unités affectées (annexe 8).
- Disponibilité standard de 100 % par personne. Affectations à 10 %, 50 % et 90 % conservées.
- Liens de l'annexe 9, y compris liens sur récapitulatifs, SS et FF. Les ID des prédécesseurs sont les **Task ID**, pas les numéros WBS.
- Retards de nivellement de l'annexe 9 en **jours écoulés** : 13=5, 15=6, 25=11, 31=23, 44=14 ; les week-ends sont comptés, puis le démarrage est arrondi au prochain créneau ouvré.
- 12 postes à 3 000 USD + 5 serveurs à 12 500 USD = 98 500 USD (cas p. 5), coût fixe affecté une seule fois à l'ID 35. Aucune nouvelle licence à acheter.
- Tarifs standard et d'heures supplémentaires de l'annexe 7 conservés ; aucune heure supplémentaire prévue.
- Coûts passés de l'équipe de planification exclus. Les 127 jours de gestion du projet à venir restent inclus, avec le lien 59FF imposé par le cas.
- Le cas ne fixe pas de date commerciale exacte pour le début des achats de fêtes. Ne pas inventer une date butoir ni une probabilité de réussite.

Dans Project, les champs personnalisés **Coût1** et **Coût2** affichent la main-d'œuvre et le capital ; **Texte1** donne la source et **Texte2** le retard de nivellement en jours écoulés. Les coûts des récapitulatifs sont des agrégats : ne pas les ajouter aux tâches détaillées.

## Reproduction

Utiliser le checkout existant `/workspace/project-management` ; chaque tâche cloud est déjà isolée, aucun worktree supplémentaire n'est nécessaire.

```bash
cd /workspace/project-management
python build_project.py
python validate_project.py
python make_report.py
```

Le planning et le CSV nécessitent seulement Python 3.10+ et sa bibliothèque standard. Le rendu des PDF utilise ReportLab et les polices DejaVu, présents dans l'environnement utilisé. Aucun service, secret ou processus à redémarrer. Les PDF source ne sont pas recopiés dans le dépôt.

Le fichier XML a été validé contre la structure MSPDI représentée par les classes de schéma de MPXJ 16.10.0, puis relu indépendamment avec le lecteur MSPDI de MPXJ. Les dates, les unités de nivellement, les taux, le travail et les coûts ont été contrôlés après relecture. Microsoft Project n'est pas installé ici : l'ouverture dans l'interface Microsoft et l'enregistrement final en MPP doivent être effectués sur l'ordinateur de l'utilisateur.
