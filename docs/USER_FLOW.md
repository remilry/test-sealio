# Parcours utilisateur — Formpilot

> Livrable de l'étape 2 (`docs/PLAN.md`). Statut : **validé le 2026-11-03**.
> Maquettes de référence : `docs/design/Formpilot.dc.html` (Claude Design). Les détails visuels restants se peaufinent au développement.
> Langue de l'interface : anglais. Ce document est en français.

## 1. Intention

L'utilisateur (responsable des appels d'offres chez Alpenlogic AG) doit rendre des formulaires d'acheteur remplis. Le produit doit lui donner trois sentiments :

1. **Fluidité** : l'IA fait tout ce qu'elle peut d'un coup ; l'humain ne traite que ce qui a besoin de lui. Viser **un clic pour lancer, zéro clic pour les réponses sûres**.
2. **Contrôle** : chaque valeur est modifiable, à tout moment, y compris pendant le remplissage. Rien n'est figé avant l'export.
3. **Confiance** : chaque valeur affiche sa source (document, page, citation exacte surlignée). Les doutes sont nommés (« périmé », « 2 sources en conflit », « introuvable ») au lieu d'être cachés.

**Anti-objectifs** (échec même si « ça marche ») : une réponse sans source présentée comme sûre ; un doute ou un conflit noyé dans la masse ; un utilisateur qui doit relire 45 champs un par un ; un fichier exporté dont la mise en page diffère de l'original.

## 2. Vue d'ensemble du flux

```
Company knowledge ──(alertes)──┐
                               ▼
Tender (offre fictive) ──► Setup (modale) ──► Live fill ──► Export (modale) ──► Tender (formulaire « Ready »)
                                                 │  ▲
                                   repli technique▼  │
                                  Auto-fill (repli) ──► Review
```

- **Vocabulaire** (décision 2026-11-04) : l'interface ne dit jamais « AI » ni « IA » : « Auto-fill », « Filling the form… », « Filled automatically », « To check », pas de ✦. Ces libellés l'emportent sur ceux des maquettes `docs/design/`.
- **Écran principal** : *Live fill*. Le formulaire se remplit tout seul sous les yeux de l'utilisateur, qui peut corriger pendant le remplissage.
- **Écrans de repli** : *Auto-fill progress* (progression seule) puis *Review* (même écran que Live fill, sans animation). Utilisés uniquement si le remplissage en flux s'avère techniquement problématique (voir §5).
- **Une seule offre**, fictive, pré-chargée : *Cloud Platform Services – Canton of Zurich*, qui contient les deux formulaires réels (Annex 4 DOCX, Annex 7 PDF).
- **Même écran pour les deux formulaires** : seul l'aperçu du document change (tableaux Word vs page PDF).

## 3. Écrans

### 3.1 Company knowledge

But : savoir **sur quoi l'IA s'appuie**.

> **V1 (décision 2026-11-03)** : pas d'extraction de faits à l'ingestion (coût). L'écran liste seulement les documents enregistrés ; les doutes (périmé, conflit) sont détectés pendant le remplissage. Les faits extraits et les alertes au niveau de la base passent en *Remaining features*.

- En-tête : nom de l'entreprise, `11 documents · last sync`.
- Tableau des documents : type (PDF/DOC), nom, nombre de pages, date d'ajout, statut : `Indexed` · `Processing` (avec progression « Reading… 3/5 pages ») · `Error` (fichier illisible, avec message).
- Bouton **Add documents** : dépôt PDF/DOCX → la ligne apparaît en `Processing` puis passe à son statut final. Retour immédiat par document, pas de rechargement de page.
- Vide au départ (décision 2026-11-04) : pendant la démo, l'utilisateur ajoute les 11 documents de `knowledge-base/documents/`.

### 3.2 Tender (détail de l'offre)

But : voir ce qui est demandé et lancer le remplissage.

- Barre latérale : logo, entreprise, navigation *Tenders* / *Company knowledge*, utilisateur (Marc Keller).
- En-tête de l'offre : procédure, référence, autorité, **échéance** (date + jours restants).
- **Formulaires à compléter** (2) — une carte par formulaire :
  - format (DOCX/PDF), titre, méta : `N fields detected · N Yes/No declarations · 1 signature` ;
  - statut : `Not started` · `In review · x/y` · `✓ Ready` ;
  - actions : `Auto-fill` (non commencé) · `Continue review` + menu `Discard answers` (commencé ; pas de relance directe, voir ci-dessous) · `⤓ DOCX` / `⤓ PDF` (prêt, format d'origine uniquement).
- Carte **Company knowledge** résumée : nombre de documents, lien *Manage*.

### 3.3 Setup (modale avant remplissage)

But : un dernier coup d'œil, un clic pour lancer.

- Fichier détecté : nom, `N fields detected · N Yes/No declarations · 1 signature`.
- Source utilisée : *Company knowledge* (`11 documents`) + *Tender details*. Base de connaissances vide : avertissement « Your company knowledge is empty: only the tender details can be used. » + lien *Add documents* (le lancement reste possible) ; tant que le nombre de documents est inconnu (chargement, échec), ni le nombre ni l'avertissement ne sont affichés. Les doutes (conflits, sources périmées) sont détectés pendant le remplissage.
- Durée estimée (« Takes about 15 seconds », calculée d'après le nombre de sections), boutons `Cancel` / `Start`.
- Un formulaire déjà commencé ne peut pas être relancé : il faut d'abord `Discard answers` (confirmation « Discard all answers to … ? », supprime **toutes** les réponses, celles de l'utilisateur aussi, même pendant un remplissage en cours), puis `Auto-fill` à nouveau. Un nouveau remplissage qui garde les valeurs de l'utilisateur viendra en V2.

### 3.4 Live fill (écran principal)

Écran plein, sans barre latérale. Deux colonnes.

**Barre du haut** : retour, fil d'Ariane `Cloud Platform Services / Annex 4 · Bidder questionnaire`, `✓ Saved`, compteur `x / y filled · n empty · n doubts`, bouton `⤓ Export DOCX` (désactivé, libellé « Filling… », tant que le remplissage dure) et menu `Discard answers`.

**Colonne gauche — la file de relecture**

- Titre : pendant le remplissage « Filling the form… » + phase en cours + barre de progression (qui ne s'arrête ni ne recule jamais) + `n / total` ; ensuite « n fields need a look ».
- Rappel : « Confident answers are already in the form. Only doubts and empty fields are flagged. »
- **3 pastilles-filtres** cliquables : `To check` (ambre) · `No value` (rose) · `Automatic` (bleu), avec leur nombre (champs encore ouverts) ; un second clic remet tout.
- Liste groupée une fois le remplissage fini (dans l'ordre du formulaire pendant le remplissage), dans cet ordre (décision 2026-11-05 : les doutes d'abord) :
  1. **To check** : conflits, valeurs d'un document périmé ou ancien, trouvées par une seule des deux recherches, valeurs suggérées (lieu, date) ;
  2. **No value** : introuvables, champs manuels sans suggestion, déclarations sans preuve ; chacun peut être rempli ou **laissé vide volontairement** (`Leave empty`, Oui/Non compris) ;
  3. **Filled automatically** : replié par défaut (« 19 answers sourced from your documents, already in the form · Show »).
- Un champ tranché par l'utilisateur (gardé, choisi, saisi, laissé vide) reste à sa place, n'est plus compté comme ouvert ni signalé à l'export.
- **Carte du champ sélectionné** (dépliée) selon le type :

| Type | Ce que voit l'utilisateur | Action principale |
|---|---|---|
| Auto (sûr) | valeur + source + citation surlignée, « Filled automatically » | `Change` (édition) |
| Introuvable | note « Not found in the passages searched in your 11 documents » (formulation honnête : la recherche RAG peut rater), champ de saisie | `Save` · `Leave empty` |
| Manuel (lieu/date…) | « Only you can fill this », valeur pré-écrite si possible (date du jour) | `Save` |
| Périmé | valeur + note « The certificate expired on … » | `Keep this value` · `Enter new value` · `Replace certificate` (→ Knowledge) |
| Conflit | 2 options radio, chacune avec source, page, date, citation ; la plus récente pré-sélectionnée et marquée *most recent* ; option « Enter another value » | `Use this one` |
| Déclaration avec preuve | **cochée automatiquement**, preuve + citation, « You declare this on behalf of Alpenlogic AG » | `Change` |
| Déclaration sans preuve | « No evidence. Your tax attestation covers direct taxes only, not VAT. » + boutons Yes / No | cocher (enregistré aussitôt) · `Leave empty` |

- Chaque valeur résolue affiche qui l'a fixée : `Filled automatically` · `Entered by you · 14:32` · `Kept by you · 14:32` · `Left empty by you · 14:32`, et reste modifiable (`Undo` : plus tard).
- **Clavier** : `↑↓` (ou `j`/`k`) pour se déplacer, `↵` pour confirmer et passer au **prochain champ ouvert**.

**Colonne droite — le document**

- Onglets `Form` / `Source` (*Source* : étape 7.5).
- **Form** : aperçu fidèle du formulaire d'origine, mis à jour en direct. Légende : *Filled automatically* (bleu) · *To check* (ambre) · *Empty* (hachuré rose) · *Entered by you* (vert) · *Sign by hand*. Les Oui/Non montrent ☐/☒ et « awaiting you » si non tranchés. Zones signature / cachet visibles, jamais remplies.
- **Source** : le passage du document cité, ouvert à la page, citation surlignée, « Used for: <champ> ». Si aucune source : « No source for this field — nothing relevant found in the passages searched ».
- **Synchronisation** : cliquer un champ à gauche cadre et surligne sa zone à droite (défilement automatique), et inversement.

**Déroulé du remplissage en direct** (phases affichées) :

1. *Reading the form* — format, pages, sections.
2. *Detecting fields* — nombre de champs, déclarations, signature.
3. *Searching your documents* — les champs se remplissent **un par un, au fil de l'écriture du modèle** (chaque champ est validé puis publié dès qu'il est complet) dans le document (« Searching your documents… » sur le champ en cours) et apparaissent dans la file à gauche.
4. *Checking sources* — conflits (valeurs candidates divergentes) et sources périmées (date de validité renvoyée par le LLM avec citation vérifiée, comparée à la date du jour) détectés.
5. *Preparing your review* — tri ; fin : « 20 of 23 fields filled in 14 seconds », sélection automatique du premier champ ouvert.

L'utilisateur peut corriger un champ signalé **pendant** le remplissage.

### 3.5 Export

Modale ouverte par `⤓ Export …` au-dessus de *Live fill* (pas de page séparée, pour alléger le flux ; une page pourra revenir si nécessaire). *Back to review* la ferme.

- Titre : « Annex 4 is ready to submit » ou « Annex 4 — n fields still empty ».
- Résumé : `x of y fields filled · n automatically from your documents · n reviewed by you`.
- Bandeau si des champs restent ouverts (ni revus ni laissés vides volontairement) : « n fields still empty — they will be exported blank » / « n doubts not reviewed — the automatic answer will be used », chacun avec sa liste et un bouton (*Review empty fields* / *Review doubts*) qui ferme la modale sur le premier champ concerné. L'export n'est jamais bloqué.
- `⤓ Download DOCX` (Annex 4) ou `⤓ Download PDF` (Annex 7) : **format d'origine uniquement**. Mention « Buyer's original layout preserved · answers written into the existing fields ».
- **Before you submit** : « Sign and stamp page n by hand — Signatory: … » ; si des valeurs d'un document périmé ont été gardées : « You kept n values from an expired certificate — attach a valid one » + *Upload new*.

### 3.6 Écrans de repli : Auto-fill progress + Review

- **Auto-fill progress** : les 5 phases avec coches, un flux « Answers found x / y » (libellé, valeur, source, drapeau *Conflict*/*Outdated*), puis un résumé (`17 filled automatically · 3 with a doubt · 3 without a value`) et `Open the form →`.
- **Review** : identique à Live fill une fois terminé.
- Ne sont construits que si Live fill pose un problème technique.

## 4. Règles métier du parcours

**Aucune règle propre à un formulaire ou à un champ.** D'autres formulaires et documents arriveront : c'est l'IA qui juge, pour chaque champ, si les documents contiennent l'information. Le code n'applique que des critères génériques :
- une preuve existe-t-elle (citation trouvée et vérifiée mécaniquement dans un document) ?
- plusieurs sources donnent-elles des valeurs différentes ?
- le document source est-il périmé (date de validité dépassée) ?
- le champ est-il, par nature, réservé à l'utilisateur (signature, cachet, lieu et date) ?

Les exemples de ce document (assurance, AVS, TVA…) illustrent ces critères ; ce ne sont pas des cas codés en dur.

| Règle | Décision |
|---|---|
| Réponse sûre, sourcée, citation vérifiée | Écrite directement dans le formulaire, aucune action requise |
| Déclaration Oui/Non **avec** preuve | **Cochée automatiquement**, preuve visible, modifiable : même règle que pour tout autre champ, y compris les déclarations légales (décision 2026-11-03, remplace le principe « toujours validée par un humain ») |
| Déclaration Oui/Non **sans** preuve | Jamais cochée par l'IA ; reste dans *No value* (l'utilisateur répond ou la laisse vide volontairement) |
| Introuvable | Champ vide, jamais de valeur inventée ; l'utilisateur saisit ou laisse vide |
| Conflit | Valeur la plus récente / la plus officielle pré-sélectionnée, les deux sources montrées, dans *To check* |
| Source périmée | Valeur proposée, signalée *Outdated*, dans *To check* |
| Signature, cachet | Jamais remplis ; rappel à l'export |
| Export | **Toujours autorisé** (décision 2026-11-05, remplace le blocage par une déclaration non tranchée), avec un bandeau listant les champs vides et les doutes que personne n'a tranchés ; un champ laissé vide volontairement (Oui/Non compris) n'est plus signalé |
| Format d'export | Format d'origine uniquement (DOCX → DOCX, PDF → PDF) |
| Sauvegarde | Automatique à chaque modification (`✓ Saved`) ; reprise possible via *Continue review* |

## 5. Contraintes techniques que ce parcours impose (pour l'étape 3)

- **Résultats en flux** : le back doit pousser les réponses champ par champ (SSE ou WebSocket) avec la phase en cours. C'est le risque principal ; s'il bloque, on bascule sur les écrans de repli (même modèle de données, résultat d'un seul coup).
- **Aperçu fidèle du document** : rendu du DOCX et du PDF d'origine avec positions de chaque champ pour surligner, défiler et refléter les valeurs en direct. La méthode (rendu HTML des tableaux, conversion en image, PDF.js…) se tranche à l'étape 3.
- **Vue Source** : afficher la page du document de la base citée, avec la citation surlignée → l'ingestion doit garder document, page et position du passage.
- **États par champ** (lien avec `PLAN.md` §6) : `pending → searching → filled | flagged → resolved(by: ai | you | kept)`, plus le type (`auto`, `missing`, `manual`, `outdated`, `conflict`, `declaration`).
- **Persistance** de l'état de relecture par formulaire (reprise après rechargement).

## 6. Hors périmètre MVP

**Retiré** : export dans un autre format (pas de PDF pour l'Annex 4).

**→ « Remaining features » du README** :
- *Remember new answers* : réinjecter les réponses saisies dans la base pour les formulaires suivants.
- *Declarations audit trail* joint à l'export.
- Extraction de faits à l'ingestion : « N facts extracted », alertes *périmé* / *conflit* et statuts `Outdated` / `Conflict` dans *Company knowledge*, avertissement dans *Setup* (retiré de la V1 le 2026-11-03 pour réduire les coûts).
- Résoudre un conflit une fois pour tous les formulaires depuis *Company knowledge* (probablement fait après coup si le temps le permet).
- Source *Previous submissions* (formulaires déjà remplis).
- Plusieurs offres, *Forms library*, *Settings*, recherche ⌘K, onglets *Overview / Tender documents / Proposal*, *Submission package*, notifications « on vous prévient quand c'est prêt ».

## 7. Choix faits par Claude (à vérifier)

1. **Éléments de maquette hors périmètre masqués**, pas affichés en lien mort : la barre latérale ne montre qu'une offre et *Company knowledge* ; pas d'Annex 2, pas d'onglets d'offre, pas de *Submission package*.
2. **Données de la maquette illustratives** : les valeurs, le nombre de champs (23 dans la maquette, ~45 réels pour l'Annex 4) et les documents viennent en réalité du parseur et de `knowledge-base/` (`GROUND_TRUTH.md` fait foi, ex. adresse Pfingstweidstrasse 31, signataire Marc Keller).
3. **Les informations de l'offre** (titre, référence, autorité adjudicatrice, échéance) sont une **source comme une autre** pour l'IA, affichée « Tender details ». Par exemple, elles permettent de remplir le projet et l'autorité dans l'Annex 7, sans règle spécifique.
4. **Upload de documents** dans *Company knowledge* gardé dans le MVP (c'était dans ton parcours initial), avec retour par document et statut `Error` pour un fichier illisible.
5. **Lieu et date** : pré-écrits avec la ville du siège et la date du jour, type *Manual*, à confirmer par l'utilisateur.
