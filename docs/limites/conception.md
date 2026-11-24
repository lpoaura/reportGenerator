# Limites de génération des rapports : conception

Validée le 19/11/2026. Objet : protéger la base et le serveur Docker (`generate` toutes les heures) sans
bloquer les demandes raisonnables, et garder une trace de chaque génération.

## Constat (code de `main`, 19/11/2026)

- Une génération en erreur ne remplit pas `date_reportgenerate` : la demande est relancée toutes les heures, sans fin.
- Le filtre de 1000 km² (`get_pending_areas`) porte sur la zone saisie sans tampon ni anneaux, et ignore la demande
  en silence.
- Pas de délai maximal sur la vue de synthèse, pas de verrou entre deux `generate`.

## Règles retenues (communes à tous les dossiers pour l'instant)

1. **Bilan de chaque génération**, écrit par une nouvelle fonction `src_gestion.update_reportgenerator_bilan`
   (`docs/limites/sql/`, à exécuter par dbadmin) :
   - `ref_geo.l_areas.comment` : une ligne lisible ;
   - `additional_data.reportgenerate` : le même bilan en jsonb (statut, durées, nombre de données, seuil, motif,
     dossier), pour régler les seuils sur des mesures ;
   - `date_reportgenerate` remplie pour `ok`, `refuse` et `erreur` : **dès le premier échec, la demande sort de la
     file**. Relance : effacer la date.

   | Statut | Exemple de commentaire |
   |---|---|
   | `en_cours` (sans date) | `EN COURS depuis le 19/11/2026 14:02` |
   | `ok` | `OK le 19/11/2026 14:09 : 7 min 12 s (vue 3 min 40 s), 352 410 données` |
   | `refuse` | `REFUSÉ le 19/11/2026 14:03 : trop de données, 1 532 004 > 1 000 000` |
   | `refuse` | `REFUSÉ le 19/11/2026 14:08 : comptage des données trop long (> 5 min)` |
   | `erreur` | `ÉCHEC le 19/11/2026 14:40 : temps de calcul trop long, vue arrêtée après 30 min` |
   | `erreur` | `ÉCHEC le 19/11/2026 14:05 : erreur KeyError: 'x' (brique sp_patrimoniales)` |
   | `erreur` | `ÉCHEC le 19/11/2026 15:00 : génération interrompue (processus arrêté)` |

2. **Comptage avant la vue** : dans `set_global_data`, `count(*)` avec exactement les filtres de la vue (emprise
   tampon ou anneaux compris, années, groupes, validation, rayons par taxon, géométries), avant dédoublonnage des
   sources (majorant). Au-delà du seuil (1 000 000), refus sans construire la vue. Le comptage a son propre délai
   (5 min) : le dépasser vaut refus.
3. **Délai de la vue** : `statement_timeout` de 30 min sur la construction de la vue ; au-delà, erreur « temps de
   calcul trop long ». La base annule elle-même la requête.
4. **Plus de filtre de surface** dans `get_pending_areas` : le comptage le remplace, quel que soit le dossier.
5. **Un seul `generate` à la fois** : verrou consultatif PostgreSQL (`pg_try_advisory_lock`, aucun objet créé) ; un
   second lancement s'arrête aussitôt. Le verrou tombe avec la connexion si le processus est tué.
6. **Génération interrompue** : le statut `en_cours` est écrit au démarrage ; une demande encore `en_cours` au
   `generate` suivant (verrou acquis, donc rien ne tourne) est marquée `erreur`, « génération interrompue ».
7. **Dossiers sans vue de synthèse** (indicateurs, PLSOC) : pas de comptage ni de seuil, mais le bilan (durée) est
   écrit.
8. **Lancement manuel** : `cli.py run ... --sans-limite` ignore le seuil et les délais ; le bilan est écrit.

Seuils par défaut dans le code (`core/limites.py`), surchargeables dans le `[params]` d'un dossier
(`limite_donnees`, `limite_comptage_min`, `limite_vue_min`) si un dossier doit un jour s'en écarter.

## Approches écartées

- Surface tampon compris par dossier : l'éolien (anneau de 20 km, ≈ 1 260 km² pour un site ponctuel) serait
  toujours bloqué ; le nombre de données est le vrai facteur de charge.
- Deuxième essai si la file est vide : le premier essai a déjà chargé la base ; demande un compteur d'essais.
- Bilan dans `comment` seul : les seuils se régleraient en analysant du texte ; dans `additional_data` seul : peu
  lisible. Les deux sont écrits par la même fonction.

## Compatibilité

Tant que la fonction n'existe pas en base, le code se rabat sur `update_reportgenerator_date` (date seule, bilan
dans le journal) : une erreur ne provoque plus de relance horaire, même avant le déploiement du SQL.
