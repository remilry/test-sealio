# 5d — Remplissage automatique dans l'UI (design)

> Étape 5d de `docs/PLAN.md`. Parcours de référence : `docs/USER_FLOW.md` §3.2–3.4. Branche `step-5d-auto-fill-ui`.
> Statut : à valider.

## 1. Intention

L'utilisateur lance le remplissage d'un formulaire et **voit le PDF et la colonne de gauche se remplir au fur et à mesure** que les réponses arrivent, avec une barre de progression qui avance toujours. Le but est de donner le sentiment de **ne pas attendre** : la première réponse doit apparaître vite, puis les autres une à une, au lieu d'un écran figé ~23 s suivi de tout d'un coup.

**Ton produit, pas gadget IA** (décision utilisateur) : l'interface ne parle jamais d'« IA ». On parle de **remplissage automatique** (*Auto-fill*, *Filled automatically*, *From your documents*). Pas d'icône ✦ « sparkles ». Le mot « AI » ne reste que dans le code et la doc technique.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- *Setup* (modale) avant le remplissage, un clic pour lancer.
- *Live fill* en flux : champs « Searching… » puis répondus, un par un, dans la liste et sur le PDF ; barre de progression dans la colonne de gauche.
- Par champ : état en mots (rempli automatiquement, introuvable, à remplir par vous, déclaration cochée) et **source** (document, page, citation) dans la carte du champ.
- Le modèle réel est **streamé** : chaque champ est validé et publié dès qu'il est complet dans la réponse.
- Le `FakeLLM` **simule la latence** du vrai modèle (rejoue le minutage enregistré) ; aucune latence dans les tests rapides ni l'e2e.
- e2e du parcours complet avec remplissage automatique.

**Non-objectifs (étapes suivantes)**
- Onglet *Source* (page citée surlignée à droite) → étape 6.
- Filtres *No value / Doubt / Automatic*, regroupement et tri de la file, validation en lot → étape 6.
- Cartes Conflit / Périmé (options radio, « Keep this value ») → étapes 6–7. En 5d, un champ `conflict` ou `outdated` s'affiche avec sa valeur sélectionnée, sa source et un libellé de doute simple (« 2 sources disagree », « Source expired on … »), sans action dédiée.
- Sections en parallèle → étape 7 (l'Annex 7 n'a qu'une section).
- Règle de blocage de l'export par une déclaration sans réponse → étape 6.

**Anti-objectifs**
- Une barre de progression qui reste immobile (sentiment d'attente) ou qui ment (100 % avant la fin).
- Tout qui apparaît d'un coup à la fin.
- Un vocabulaire « AI is filling… », « Fill with AI », ✦.
- Une valeur saisie par l'utilisateur pendant le remplissage écrasée par le remplissage.
- Des tests lents parce que le `FakeLLM` attend.

## 3. Parcours et écrans

### 3.1 Tender — carte du formulaire
- `not_started` : bouton **Auto-fill** (icône sobre, pas de ✦) → ouvre *Setup*.
- Commencé ou en cours (`in_review`, `ready`, run en cours) : `Continue review` (lien vers *Live fill*) + menu « ⋯ » avec **Discard answers** (§3.5). **Pas de relance** du remplissage automatique sur un formulaire commencé (décision utilisateur) : pour refaire un *Auto-fill*, on abandonne d'abord le remplissage. Une relance qui garde les valeurs de l'utilisateur viendra dans une V2.
- Format non lu (Annex 4) : *Auto-fill* désactivé, comme aujourd'hui.

### 3.2 Setup (modale, sur l'écran *Tender*)
- Titre « Auto-fill {formTitle} ».
- Fichier : nom du fichier, `N fields detected · N Yes/No declarations · 1 signature`.
- Sources : *Company knowledge* · `N documents` (documents indexés) + *Tender details*.
  - 0 document indexé : avertissement « Your company knowledge is empty: only the tender details can be used » + lien *Add documents* ; le lancement reste possible.
- Durée estimée : « Takes about {n} seconds » (voir §4.4).
- Boutons `Cancel` / `Start`. `Start` → `POST /forms/{id}/fill` puis navigation vers *Live fill*. Erreurs : 503 (« Auto-fill is not available right now », message du back), 409 (déjà en cours → on navigue quand même vers *Live fill*), autre → bandeau dans la modale.

### 3.3 Live fill pendant le remplissage
**En-tête de la colonne de gauche** (remplace « n fields to fill » pendant le run) :
- « Filling the form… » + libellé de la phase en cours + `n / total` champs répondus.
- **Barre de progression** (`role="progressbar"`, `aria-valuenow`) — calcul en §4.4.
- Phases affichées (libellés produit) : *Reading the form* · *Detecting fields* · *Searching your documents* · *Checking sources* · *Preparing your review*.
- À la fin : « {filled} of {fillable} fields filled in {seconds} seconds », puis l'en-tête normal (« n fields to fill » / « All fields are filled ») ; le premier champ ouvert est sélectionné automatiquement (sauf si l'utilisateur a déjà choisi un champ).
- Erreur du run : bandeau « Auto-fill stopped: {message} » ; les réponses déjà publiées restent, l'utilisateur complète à la main ou abandonne le remplissage (§3.5) pour relancer. _Choix de Claude_ : pas de bouton *Try again* (pas de relance en V1).

**Liste des champs** : chaque champ passe par `pending` (rien) → `searching` (« Searching your documents… », discret, animé) → `answered` (carte §3.4). Les champs déjà fixés par l'utilisateur ne passent pas par `searching`.

**PDF** : la valeur apparaît dans sa zone dès que le champ est répondu ; une zone en `searching` est signalée (pulsation légère). Nouvelles teintes de légende :
- *Filled automatically* (bleu) — `auto`, `declaration`.
- *To check* (ambre) — `conflict`, `outdated`, et `manual` avec valeur suggérée. _Choix de Claude_ : le compteur `doubts` du back reste « conflits + périmés » (inchangé) ; la teinte ambre couvre en plus les valeurs suggérées à confirmer, d'où le libellé de légende *To check* plutôt que *Doubt*.
- *Empty* (hachuré rose) — sans valeur.
- *Entered by you* (vert) — `resolved_by = user`.
- *Sign by hand* — signature.

**Barre du haut** : compteur `{filled} / {fillable} filled · {empty} empty · {doubts} doubts` mis à jour à chaque événement ; `Export PDF` désactivé avec le libellé « Filling… » pendant le run.

**Édition pendant le run** : l'utilisateur peut saisir dans n'importe quel champ ; sa valeur est gardée (le back ne la remplace pas). Un événement `answered` arrivant pour un champ en cours de frappe ne doit pas effacer ce qui est tapé (l'input non sauvegardé garde la main).

### 3.4 Carte d'un champ (après réponse)
Selon `answer.type` et `resolved_by` :

| Cas | Statut affiché | Contenu |
|---|---|---|
| `auto` | *Filled automatically* | valeur éditable + source |
| `declaration` | *Filled automatically · you declare this on behalf of {company}* | Oui/Non (affiché comme valeur éditable en 5d, l'Annex 7 n'a pas de case) + preuve |
| `missing` | *Not found in your documents* (« … in the passages searched in your {n} documents ») | champ vide à saisir |
| `manual` | *Only you can fill this* + raison (`user_only_reason`) | valeur suggérée pré-écrite, à confirmer |
| `conflict` | *2 sources disagree* | valeur sélectionnée + sources (toutes) |
| `outdated` | *Source expired on {date}* | valeur + source |
| `resolved_by = user` | *Entered by you · 14:32* (existant) | la source IA reste visible si elle existe |

### 3.5 Abandonner le remplissage (décision utilisateur, V1)
- Accès : menu « ⋯ » de la carte du formulaire sur *Tender* (**Discard answers**) et barre du haut de *Live fill*.
- Confirmation : « Discard all answers to {formTitle}? Every value is deleted, including the ones you entered. This can't be undone. » · `Cancel` / `Discard`.
- Effet : toutes les réponses supprimées (celles de l'utilisateur comprises), événements et run effacés, formulaire de nouveau *Not started* ; depuis *Live fill*, retour à *Tender*.
- Possible **pendant** un remplissage : le run s'arrête (le job vérifie entre deux champs que le remplissage existe toujours / n'a pas été abandonné et s'arrête sans rien écrire), puis tout est supprimé de la même façon. Le flux SSE ouvert se termine.
- Back : `DELETE /forms/{id}/fill` (204 ; 404 formulaire inconnu) — _forme exacte au builder_ (supprimer le `form_fill` ou le remettre à zéro).
- Une V2 fera mieux (relance qui garde les valeurs de l'utilisateur, etc.).

### 3.6 Source dans la carte
**Source** (bloc repliable sous la valeur, ouvert pour le champ sélectionné) : nom du document, `page n`, citation entre guillemets. Plusieurs citations → toutes listées. *Tender details* (document_id nul) affiché « Tender details ».

## 4. Back

### 4.1 Façade LLM : streaming
- La façade ajoute un rappel de progression optionnel sur la sortie partielle, par exemple `generate_structured(request, on_partial: Callable[[dict], None] | None = None)` (_signature exacte au builder_). Le résultat final et l'usage restent inchangés.
- **OpenAI** : `client.responses.stream(..., text_format=schema)` ; à chaque `response.output_text.delta`, le texte cumulé est parsé en JSON partiel (`pydantic_core.from_json(..., allow_partial=True)`) et passé à `on_partial`. La réponse finale (`get_final_response()`) donne la sortie validée et l'usage.
- **FakeLLM** : rejoue le minutage enregistré (§4.3) en appelant `on_partial` avec la sortie tronquée aux `i` premiers champs, après le délai enregistré pour chacun. Latence contrôlée par un réglage `FORMPILOT_FAKE_LLM_LATENCY` : `recorded` (défaut, démo) ou `none` (tests pytest et e2e).

### 4.2 Moteur et job : publier champ par champ
- `answer_section` accepte un rappel `on_field(field_id, ValidatedField)`. Il détecte qu'un champ de la sortie partielle est **complet** quand un champ suivant a commencé dans la liste `fields` (ou à la fin de la réponse) ; il le valide alors (même validateur, mêmes passages) et appelle `on_field` une seule fois par champ. Les champs non renvoyés reçoivent `not_found` à la fin, comme aujourd'hui.
- Le job, dans `on_field`, applique `decide`, enregistre la réponse, commite et émet l'événement `field` `answered` (contenu inchangé). Événements `searching` : émis pour tous les champs de la section au début de la section (inchangé).
- La logique de correspondance clé/libellé reste celle de 5c ; un champ dont la clé partielle n'est pas encore complète n'est pas publié.

### 4.3 Enregistrements avec minutage
- `RecordingLLM` enregistre en plus, dans le même JSON, un bloc `timing` : `first_field_seconds` (du lancement à la fin du premier champ) et `field_seconds` (délai cumulé à la fin de chaque champ), plus `total_seconds`. Les fichiers sans `timing` restent rejouables (sans latence).
- Réenregistrer l'Annex 7 avec le vrai modèle en streaming (`scripts/record_llm.py`, ~0,5 centime, clé de l'utilisateur dans `backend/.env`, lue par les réglages de l'app, jamais par Claude). _Choix de Claude_ : Claude lance le script pendant l'étape ; la nouvelle réponse est relue contre `GROUND_TRUTH.md` (le test de rejeu existant porte sur le nouvel enregistrement). Si l'appel échoue, un bloc `timing` écrit à la main (~23 s, réparti sur les champs) sert de repli, signalé à l'utilisateur.

### 4.4 Durée estimée et progression
- Le back expose une **durée estimée** du remplissage d'un formulaire (par exemple `estimated_fill_seconds` sur `FormDetail` / `FormSummary`) = nombre de sections × durée par section (réglage, défaut 25 s ; séquentiel jusqu'à l'étape 7). _Emplacement exact au builder._
- **Progression (front, pure et testée)**, de 0 à 1, jamais en recul :
  - phases avant la recherche : 0 → 5 % ;
  - pendant la recherche : 5 % + 90 % × (champs répondus / champs à répondre), **plus** une avance au temps entre deux réponses qui tend vers le palier suivant sans l'atteindre (attente de la première réponse : le modèle réfléchit plusieurs secondes) — basée sur la durée estimée ;
  - *Checking sources* / *Preparing your review* : 95 → 99 % ; `done` : 100 %.

### 4.5 Petites retouches API
- `Tender`/`FormSummary` : exposer ce qu'il faut pour *Setup* et la carte (statut du run en cours, nombre de documents indexés — déjà sur la carte *Company knowledge*).
- Régénérer les types front (`make gen-api`).

## 5. Front

- Nouveau feature `auto-fill` (ou dans `fill-session`, _au builder_ selon les règles de modules) : `startFill` (mutation), `useFillEvents(formId)` (abonnement SSE via `EventSource` sur `/forms/{id}/fill/events`, ouvert si `ai_run.status = running` ou juste après le lancement ; applique chaque événement `field answered` au cache `fillKeys.answers` (réponse + compteurs) ; tient la phase, les champs en `searching`, le nombre répondu, le résumé `done`/`error` ; se ferme à `done`/`error` puis invalide l'état du formulaire et de l'offre).
- Rechargement de la page pendant un run : le flux rejoue depuis le début (comportement du back), l'écran reprend où il en était.
- `SetupDialog` sur l'écran *Tender* ; `FormAction` adapté (§3.1).
- `FieldList` : statut, source, état `searching` par champ ; `QueueField` étendu (type, candidats, raison, `resolved_by`).
- `DocumentPreview` : nouvelles teintes (§3.3), zone en `searching`.
- Textes dans `en.json` (skill `frontend-i18n`), sans « AI ». Renommer les clés et textes existants (`fillWithAi` → `autoFill`, etc.).

## 6. Tests

- **Back (pytest)** : extraction des champs complets d'une sortie partielle (pur : JSON coupé au milieu d'une valeur, d'une clé, entre deux champs, champ vide, fin de réponse) ; `FakeLLM` rejoue les partiels dans l'ordre, sans délai en `none`, avec délais en `recorded` (horloge/sommeil injectable, pas d'attente réelle) ; job : les événements `answered` sont émis un par un pendant l'appel (avant la fin de la section) ; enregistrement avec `timing` ; abandon (réponses utilisateur comprises supprimées, statut *Not started*, nouveau lancement possible, abandon pendant un run : le job s'arrête sans écrire, 404) ; réponse enregistrée de l'Annex 7 toujours conforme à `GROUND_TRUTH.md`.
- **Front (Vitest, skill `screen-tests`)** : calcul de progression (pur) ; écran *Tender* : *Auto-fill* ouvre *Setup*, `Start` lance et navigue, 503 affiché, abandon depuis le menu (confirmer, annuler, échec) ; *Live fill* : abandon (retour à *Tender*), y compris pendant le run ; écran *Live fill* : flux SSE simulé (phases → champs en `searching` → réponses une à une sur la liste et le PDF, barre qui avance, compteur, Export désactivé puis actif, résumé de fin, sélection du premier champ ouvert), carte de chaque type avec sa source, saisie pendant le run conservée, erreur du run.
- **e2e (Playwright)** : dépôt des documents → *Tender* → *Auto-fill* → *Setup* → *Start* → champs remplis avec source visible → correction d'un champ → export du PDF. `FakeLLM` sans latence.

## 7. Documentation
- `USER_FLOW.md` : vocabulaire produit (règle « pas d'IA dans l'interface »), libellés renommés.
- `PLAN.md` : 5d détaillée + journal (streaming, latence simulée, vocabulaire, Source tab en étape 6).
- `CLAUDE.md` : décisions (avec validation de l'utilisateur).
- `ARCHITECTURE.md` : streaming dans la façade, minutage des enregistrements.

## 8. Laissé au builder (marqué « _au builder_ »)
Signature exacte du rappel de streaming, emplacement de la durée estimée dans l'API, nom/emplacement du feature front, détail visuel des teintes et de l'animation `searching`.
