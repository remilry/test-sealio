# 7 — Relecture et humain dans la boucle (design)

> Étape 7 de `docs/PLAN.md`. Branche `step-7-review`. S'appuie sur 5d (file de champs, statuts), 6b/6c (Annex 4, types `unsure` / `outdated`).
> Statut : à valider.

## 1. Intention

Après l'Auto-fill (Annex 4 : « 40 / 48 filled · 8 empty · 15 doubts »), l'utilisateur doit savoir **quoi regarder** et pouvoir **trancher vite** : d'abord les doutes, qu'il valide ou corrige, puis les champs sans valeur, qu'il remplit ou **laisse vides volontairement**. Quand il a tout tranché, l'export ne l'avertit plus de rien. Inspiré des maquettes `docs/design/Formpilot.dc.html` (*Live fill*, file groupée, cartes par type).

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- File de relecture groupée, dans cet ordre (décision utilisateur : les doutes avant les champs vides, l'inverse de la maquette) :
  1. **To check** : `conflict`, `outdated`, `unsure`, `manual` avec une valeur suggérée, non tranchés par l'utilisateur (un `manual` sans valeur suggérée va dans *No value*) ;
  2. **No value** : champs sans valeur non tranchés (`missing`, Oui/Non sans preuve, champ jamais répondu) ;
  3. **Filled automatically** : `auto` et `declaration`, repliée par défaut (« n answers sourced from your documents, already in the form · Show »).
- Une action pour trancher chaque carte :
  - conflit : candidats en boutons radio (valeur, source, page, date ; le sélectionné marqué *most recent* s'il est daté), plus « Enter another value » → `Use this one` ;
  - périmé / incertain / suggéré : valeur + note actuelle → `Keep this value` · `Enter new value` (focus sur le champ de saisie) ;
  - sans valeur (texte ou Oui/Non) : saisie (`Save`, ou Yes / No) · **`Leave empty`** (décision utilisateur : aussi pour un Oui/Non).
- Une carte tranchée montre qui l'a fait : « Kept by you · 14:32 », « Left empty by you · 14:32 », « Entered by you · 14:32 » (existant), et reste éditable (changer la valeur, ou `Leave empty` d'un champ rempli n'est pas proposé : on efface le texte).
- Titre de la file une fois le remplissage fini : « n fields need a look » (les doutes et vides non tranchés), « Everything is reviewed » à 0.
- **Pastilles-filtres** en haut de la file : `To check` (ambre) · `No value` (rose) · `Automatic` (bleu), chacune avec son nombre ; un clic ne montre que ce groupe, un second clic remet tout.
- **Clavier** : `↵` dans une carte à trancher = son action principale (`Keep this value` / `Use this one` / `Save` si du texte est saisi), puis sélection du **prochain champ encore ouvert** (dans l'ordre de la file) ; `↑↓` / `j` `k` inchangés.
- **Export jamais bloqué** (décision utilisateur, remplace la règle « bloqué par une déclaration Oui/Non sans réponse ») : la modale liste
  - « n fields still empty — they will be exported blank » : vides **non tranchés** (Oui/Non compris) ;
  - « n doubts not reviewed — the automatic answer will be used » : doutes non tranchés ;
  - chaque bandeau a `Back to review` : ferme la modale et sélectionne le premier champ concerné ;
  - rien d'ouvert → titre « {form} is ready to submit », pas de bandeau ;
  - résumé : « x of y fields filled · n automatically from your documents · n reviewed by you ».
- Statut **Ready** du formulaire (prévu depuis 4.5) : posé quand plus rien n'est ouvert, retiré dès qu'un champ se rouvre (ex. *Discard*, nouveau remplissage) ; la carte *Tender* l'affiche déjà.

**Non-objectifs**
- Onglet *Source* (passage cité ouvert à la page, citation surlignée) → **étape 7.5** (décision utilisateur).
- Validation en lot (_choix de Claude_ : le groupe *Filled automatically* n'exige déjà aucune action ; les doutes se tranchent un à un).
- `Undo` d'une décision (_choix de Claude_ : la valeur reste éditable ; la valeur suggérée d'un champ `manual` remplacée n'est pas restaurable). `Replace certificate` (→ Knowledge) : hors étape.

**Anti-objectifs**
- Une carte qui disparaît ou saute sous le curseur au moment où on la tranche.
- Un champ tranché par l'utilisateur encore compté comme doute ou vide dans l'export.
- Un mot « IA » dans l'interface.

## 3. Modèle : « tranché par l'utilisateur »

Pas de nouvelle colonne (_choix de Claude_) : une réponse est **tranchée** quand `resolved_by = user` (`needs_review = false`). C'est déjà ce que fait `PATCH /forms/{id}/fields/{fieldId}` :
- `Keep this value` / `Use this one` → PATCH avec la valeur affichée (même valeur : la réponse passe à l'utilisateur, `type` et `candidates` gardés) ;
- `Leave empty` → PATCH `value: null` ;
- un champ sans réponse (jamais rempli) n'est pas tranché.

Nouvelle colonne `answer.proposed_value` (_choix de Claude_) : la valeur que le remplissage automatique a écrite (y compris la valeur suggérée d'un `manual`), jamais modifiée par l'utilisateur, exposée dans `AnswerOut`. Statut affiché d'une réponse de l'utilisateur, dérivé côté front : valeur nulle → *Left empty by you* ; valeur égale à `proposed_value` ou à celle d'un candidat → *Kept by you* ; sinon *Entered by you* (existant). Elle rendra aussi un `Undo` possible plus tard.

Ouvert = tranché par personne et (doute `needs_review` ou sans valeur). Les signatures ne comptent jamais.

**Back**
- `FillCounts` : + `open` (doutes non tranchés + vides non tranchés) ; `doubts` reste « doutes non tranchés » ; `empty` reste « sans valeur ».
- `ExportSummary` : `empty_fields` = vides **non tranchés** ; + `left_empty` (nombre), `unreviewed_doubts: list[FieldRef]`, `automatic` (valeurs de l'IA gardées sans revue), `reviewed` (tranchés par l'utilisateur).
- Statut `ready` / `in_review` recalculé après chaque `set_answer`, à la fin d'un remplissage et après *Discard* (`not_started`).
- Types du front régénérés (`make gen-api`).

## 4. Front

- `review-queue` : fonction pure `groupFields(fields)` → groupes ordonnés + nombres + `nextOpen(fieldId)` (testée à part). Pendant le remplissage, la liste reste dans l'ordre du formulaire (comme aujourd'hui, _choix de Claude_ : les champs arrivent un à un) ; groupée dès que le run est fini, ou sans run.
- Une carte tranchée reste à sa place dans son groupe, compacte, avec ✓ et son statut (pas de saut) ; les nombres des pastilles et du titre comptent ce qui reste ouvert.
- Carte sélectionnée dépliée (sources, actions) ; les autres en une ligne (libellé, valeur, statut), comme la maquette.
- `ExportDialog` : deux bandeaux + `Back to review` (callback vers *Live fill* qui sélectionne le champ) ; titre prêt / restant.
- Textes dans `en.json` (skill `frontend-i18n`).

## 5. Tests

- Back : comptes `open` (doute, vide, tranché, gardé, laissé vide, signature), résumé d'export (vides non tranchés, laissés vides exclus, doutes non revus), statut `ready` ↔ `in_review`, PATCH même valeur sur un doute.
- Front : `groupFields` / `nextOpen` ; écran *Live fill* : ordre des groupes, filtres, `Keep this value`, conflit `Use this one` avec un autre candidat, `Leave empty` (texte et Oui/Non), `↵` passe au suivant ouvert, groupe automatique replié / déplié ; *Export* : bandeaux, `Back to review` sélectionne le champ, « ready to submit ».
- e2e (Annex 4) : après l'Auto-fill, garder un doute, laisser vide une déclaration, saisir un champ, l'export montre les nombres attendus, DOCX téléchargé.

## 6. Documents à mettre à jour

- `docs/USER_FLOW.md` §3.4 (ordre des groupes, `Leave empty`), §3.5 et §4 (export jamais bloqué).
- `CLAUDE.md` (« only an unanswered declaration blocks it » → export jamais bloqué, avertissements) : **à valider par l'utilisateur**.
- `docs/PLAN.md` : étape 7 détaillée, onglet *Source* déplacé en 7.5, journal.

## 7. Laissé au builder

Découpage des composants de carte, styles exacts (teintes déjà définies par la légende), forme de `kept` (dérivé ou colonne), messages exacts hors ceux cités.
