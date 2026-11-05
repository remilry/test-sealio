# 6c — Remplissage automatique de l'Annex 4 (design)

> Étape 6c de `docs/PLAN.md`. Branche `step-6c-annex4-auto-fill`. S'appuie sur 5c/5d (moteur, job, flux SSE, `FakeLLM`) et 6a/6b (parseur Word, *Live fill* Word).
> Statut : en attente de validation (2026-11-05).

## 1. Intention

Un clic sur `Auto-fill` de l'Annex 4 la remplit comme l'Annex 7 : les réponses arrivent champ par champ, sourcées, dans l'aperçu Word. Le remplissage dure à peu près le temps de **l'appel le plus lent**, pas la somme des 8 sections (en séquence : 2 à 3 min). Les réponses du vrai modèle sont enregistrées pour le `FakeLLM` (tests, e2e, démo sans clé).

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Appels au modèle **en parallèle** dans le job, par **groupes de champs**.
- **Contexte d'en-tête** des champs Word (décision utilisateur) : l'en-tête qui chapeaute un champ sert à la recherche et au prompt.
- **Enregistrement réel de l'Annex 4**, vérifié contre `knowledge-base/GROUND_TRUTH.md`.
- Durée annoncée dans *Setup* calculée d'après le remplissage parallèle.

**Non-objectifs (6c)**
- Cartes Conflit / Périmé, onglet *Source*, blocage de l'export par une déclaration sans réponse : étape 7. Les types `conflict`, `outdated`, `declaration`, `missing` existent déjà (5c) et s'affichent avec les statuts actuels de 5d.
- Aperçu Word dans *Company knowledge* : 6d.
- Évaluation chiffrée de la qualité, durcissement du moteur au-delà de corrections simples : étape 8.
- Ré-enregistrer l'Annex 7 (l'enregistrement versionné est gardé, voir les limites de 5d).

**Anti-objectifs**
- Aucune règle propre à l'Annex 4 ou à un champ (prompt, recherche, parseur restent génériques).
- Aucun surcoût par champ : même prompt, mêmes passages ; seule la répétition des instructions par appel s'ajoute.
- Un champ fixé par l'utilisateur n'est jamais remplacé, y compris pendant les appels parallèles (garanti par l'upsert conditionnel de 5c).

## 3. Groupes de champs (décision validée)

- Unité d'appel = **groupe** : les champs à remplir d'une section, dans l'ordre ; une section de plus de **10** champs est coupée en groupes équilibrés (`ceil(n / 10)` groupes de tailles qui diffèrent d'au plus 1). Annex 4 : Table 7 (17 Oui/Non + *Remarks* = 18 champs) → 9 + 9 ; les autres sections tiennent en un groupe (Table 3 : 9 champs). Annex 7 : 9 champs → 1 groupe, sa clé d'enregistrement ne change pas. _Limite 10 plutôt que 8 : choix de Claude, pour garder l'enregistrement de l'Annex 7._
- La coupe se fait sur **tous les champs hors signature**, puis les champs fixés par l'utilisateur sont retirés de leur groupe (un groupe vide n'est pas appelé). Ainsi la clé et le contenu d'un groupe ne dépendent pas de ce que l'utilisateur a saisi, et un enregistrement reste valable sur un formulaire commencé à la main ; la durée estimée compte les mêmes groupes. _Choix de Claude, après relecture._
- Clé stable d'un appel : `<formulaire>--<section>` pour un groupe unique (inchangé), `<formulaire>--<section>--part-<i>` (à partir de 1) quand la section est coupée. Fonction pure, testée ; utilisée par le job et par `scripts/record_llm.py`.
- Le libellé « Section » du prompt reste le nom de la section.

## 4. Appels en parallèle (job)

- Pool borné (`ThreadPoolExecutor`), taille réglable `FORMPILOT_FILL_MAX_PARALLEL_CALLS`, **10** par défaut (Annex 4 : 9 groupes, tous lancés ensemble). Les appels du modèle et la recherche sont bloquants (SDK synchrone, psycopg) : des threads suffisent.
- **Une session de base par groupe** (recherche, écriture des réponses, événements), ouverte et fermée dans son thread ; la session principale garde les phases et la fin du run.
- Au début de la phase `searching`, un événement `field` `searching` pour **chaque** champ à répondre (tous les groupes partent ensemble). Puis chaque champ est publié (`answered`, réponse + compteurs) dès que son groupe l'a validé, comme en 5d ; les événements de groupes différents s'entrelacent. Les compteurs de chaque événement sont relus après le commit du champ (l'état peut contenir des champs d'autres groupes : c'est voulu).
- **Échec d'un groupe** (erreur du modèle ou panne) : les autres groupes ne publient plus rien (drapeau d'arrêt partagé, vérifié avant chaque publication ; un appel déjà en cours n'est pas interrompu, son résultat est ignoré), le run se termine par `error` avec le même message qu'aujourd'hui (`MODEL_ERROR` ou `UNEXPECTED_ERROR`). Les champs déjà publiés restent (comme en 5d quand une section échoue après une autre).
- **Discard pendant le remplissage** : chaque groupe vérifie que le run existe encore avant de publier (comme `check_not_discarded` aujourd'hui) ; le job s'arrête en silence.
- Phases `cross_checking`, `preparing_review` et `done` émises quand tous les groupes ont fini ; les compteurs des types (`conflict`, `outdated`) agrégés sur tous les groupes.
- Journal : temps, passages et consommation par groupe, puis total (somme des coûts, durée réelle du run).

## 5. Contexte d'en-tête (décision utilisateur)

- Nouveau champ `context: str | None` de `ParsedField` et colonne `field.context` (texte, nullable, migration Alembic) ; pas exposé par l'API ni affiché (_choix de Claude_).
- Règles du parseur Word, génériques :
  - une **ligne de titre** d'un tableau (une seule cellule, déjà écartée comme champ) devient le contexte des champs des lignes suivantes du même tableau, jusqu'à la prochaine ligne de titre ;
  - un **libellé qui chapeaute plusieurs libellés à sa droite** (déjà écarté comme champ) devient le contexte des champs de la cellule de droite ;
  - les deux s'enchaînent (titre de tableau, puis libellé chapeau) séparés par « › » ; texte nettoyé par `clean_label` (tabulations, `:` final).
  - Annex 4 : Table 4 → « Number of employees in the area essential to performing the tendered contract » ; Table 5 *Personal injury* / *Property damage* / *Financial loss* → « Available amounts per claim ». Les autres champs n'en ont pas. Le parseur PDF n'en produit pas (Annex 7 inchangée).
- Usage : la requête de recherche d'un champ = `contexte + " " + libellé` ; la ligne du champ dans le prompt ajoute `· context: …`. Sans contexte, recherche et prompt identiques à aujourd'hui (l'Annex 7 et son enregistrement ne bougent pas).
- **Base existante** : l'Annex 4 y est déjà parsée (6b), avec peut-être des réponses. Le seed complète `context` des champs existants depuis le parseur, en les retrouvant par clé, sans supprimer de champ ni de réponse (_choix de Claude_ ; le builder peut préférer une migration de données équivalente).

## 6. Durée annoncée dans *Setup*

- `estimated_fill_seconds` = `ceil(groupes / max_parallel_calls) × fill_seconds_per_call` (renommage de `fill_seconds_per_section`, 25 s par défaut). Annex 4 : 9 groupes, 10 en parallèle → 25 s ; Annex 7 : 25 s (inchangé). Le nombre de groupes est calculé avec la même fonction que le job (sur tous les champs hors signature). Le réglage est ajusté après la mesure réelle de l'Annex 4.
- Front : aucun changement attendu (le texte « Takes about N seconds » lit déjà cette valeur ; la barre `fillProgress` repose sur les phases, les réponses reçues et le temps). Si la mesure montre un défaut visible avec les événements entrelacés, le corriger ici.

## 7. Enregistrement de l'Annex 4

- `scripts/record_llm.py` passe par les mêmes groupes et clés que le job, et lance les groupes **en parallèle** (même pool), pour mesurer la vraie durée. Il affiche par groupe et au total : durée, premier champ, coût. Une option pour n'enregistrer qu'un formulaire (`--form annex-4`, au choix du builder) évite de payer l'Annex 7 à chaque essai.
- Lancé par Claude avec la clé de l'utilisateur ; **après chaque essai, Claude rapporte le coût et les écarts, et attend l'accord de l'utilisateur avant le suivant** (décision utilisateur). C'est l'utilisateur qui décide quand on arrête et que les écarts restants partent dans les limites connues.
- Critère de réussite (relecture contre `GROUND_TRUTH.md`, « aujourd'hui » = date de l'enregistrement, après le 31 octobre 2026) :
  - conflits : effectif total s'il est demandé, adresse de la caisse AVS (Hardturmstrasse 120 proposée) ;
  - périmés : les trois montants par sinistre (attestation 03 expirée le 2026-10-31) ;
  - introuvables : personnel auxiliaire, apprentis, TVA, LAA (UVG), questions « services à l'étranger », champs des soumissionnaires étrangers ;
  - Oui/Non prouvés avec la citation attendue, et aucune déclaration inventée ;
  - champs factuels conformes (nom, adresse, UID, forme juridique, capital, assureur, offices…).
- Écart : correction générique et simple du prompt ou de la recherche, puis nouvel essai ; sinon l'écart est consigné dans les limites connues pour l'étape 8. Un enregistrement qui invente une valeur ou coche une déclaration sans preuve vérifiée n'est pas versionné tel quel (le validateur doit déjà l'empêcher ; sinon c'est un bug à corriger).
- Fichiers versionnés : un JSON par groupe dans `backend/llm_recordings/`, avec leur bloc `timing` (la latence simulée du `FakeLLM` les rejoue en parallèle comme en vrai).

## 8. Tests

- **Parseur** : contexte d'une ligne de titre (et sa fin à la ligne de titre suivante), d'un libellé chapeau, des deux enchaînés, sur des Word synthétiques ; schéma attendu de l'Annex 4 complété avec les contextes de Table 4 et Table 5.
- **Groupes** (pur) : pas de coupe à 10, coupe équilibrée à 11 et à 18, clés `--part-i`, champs exclus.
- **Moteur** : requête de recherche avec contexte, ligne du prompt avec contexte, sans contexte inchangées.
- **Job** (FakeLLM scripté) : groupes en parallèle (tous les champs publiés, une seule fin `done`, compteurs finaux justes), échec d'un groupe → `error` et plus aucune publication des autres, discard pendant le remplissage, valeur de l'utilisateur gardée ; preuve du parallélisme : avec une latence simulée, la durée totale reste proche d'un appel, pas de la somme.
- **Seed** : base où l'Annex 4 a été parsée sans contexte → contexte complété, champs et réponses gardés.
- **Durée estimée** : Annex 4 et Annex 7.
- **Rejeu** : l'enregistrement de l'Annex 4 rejoué dans tout le remplissage donne les types attendus aux champs pièges (conflit AVS, montants périmés, TVA introuvable, déclarations prouvées).
- **e2e** : après l'Annex 7, `Auto-fill` de l'Annex 4 depuis *Tender* (*Setup* puis `Start`), compteurs finaux, une déclaration cochée visible dans l'aperçu, export DOCX. Le passage manuel actuel de l'Annex 4 (ouverture par URL, un champ et une déclaration saisis) est remplacé ou ajusté au choix du builder.

## 9. Choix laissés au builder / faits par Claude

- Choix de Claude : limite de 10 champs par groupe ; pool de 10 ; `context` non exposé par l'API ; seed qui complète le contexte des champs existants ; renommage `fill_seconds_per_call`.
- Au builder : nommage, structure interne du job parallèle (fonction par groupe, drapeau d'arrêt), forme de l'option du script d'enregistrement, ajustement de `fill_seconds_per_call` après mesure.
- Documentation : `docs/PLAN.md` (6c détaillée, journal), `docs/ARCHITECTURE.md` (job parallèle, groupes, contexte), `docs/DB_SCHEMA.md` (`make db-schema`), `backend/CLAUDE.md` (mesure de l'Annex 4, réglage du pool). `CLAUDE.md` racine : proposer la mise à jour à l'utilisateur.
