# 6b — Annex 4 dans *Live fill* : aperçu Word, saisie, export (design)

> Étape 6b de `docs/PLAN.md`. Branche `step-6b-word-live-fill`. S'appuie sur 6a (parseur, `DocxLocator` à positions de caractères, exporteur).
> Statut : validé dans la conversation (2026-11-05).

## 1. Intention

L'utilisateur ouvre l'Annex 4 dans *Live fill* et la remplit **à la main** comme l'Annex 7 : la liste des champs à gauche, le Word d'origine à droite, chaque valeur apparaissant à l'endroit où l'export l'écrira, puis il télécharge le DOCX rempli. Le remplissage automatique de l'Annex 4 vient en 6c.

## 2. Objectifs, non-objectifs

**Objectifs**
- Back : le parseur Word branché au seed (`forms_service.PARSERS`) ; l'Annex 4 parsée au démarrage, y compris sur une base existante (`parsed_at` nul).
- Back : `pages` d'un formulaire Word = taille de page de la section (`w:sectPr/w:pgSz`, twips → points) répétée `<Pages>` fois (`docProps/app.xml`, écrit par Word à la dernière sauvegarde) ; à défaut, nombre de `w:lastRenderedPageBreak` + 1. Annex 4 : 3 pages A4. Ce nombre est celui du fichier d'origine.
- *Tender* : carte Word avec ses compteurs (« 49 fields detected · 17 Yes/No declarations · 1 signature ») ; ~~`Auto-fill` désactivé pour un formulaire Word~~ → **réactivé à la fin de 6b (décision utilisateur, pour voir l'aperçu)** : *Setup* montre le Word (`WordViewer`) ; en mode `fake`, le lancement échoue jusqu'aux enregistrements de 6c. *Live fill* de l'Annex 4 s'ouvre aussi par son URL (`/forms/{id}/fill`).
- *Live fill* sur un Word : colonne de gauche inchangée ; à droite, rendu HTML du DOCX par `docx-preview` (`inWrapper: false` ; pages coupées aux sauts de page et sections du document, pas aux marques `lastRenderedPageBreak`, qui coupent un paragraphe en deux — révisé à la relecture, sans effet sur l'Annex 4) ; chaque champ surligné avec les teintes du PDF (`auto`, `toCheck`, `empty`, `entered`, `signature`, `searching`) ; la valeur (brouillon compris) affichée en direct à l'endroit de l'export ; clic sur une zone = sélection du champ ; sélection = défilement jusqu'à la zone.
- **Oui/Non** (_ajout de Claude, nécessaire pour saisir les 17 déclarations_) : un champ `yes_no` se remplit par deux boutons `Yes` / `No` (et `Clear`) au lieu d'un champ texte ; la valeur enregistrée est `yes` / `no` (comme le validateur) ; le back refuse toute autre valeur pour un champ `yes_no` (422). L'aperçu et l'export l'écrivent `Yes` / `No`.
- *Export* : « Export DOCX » / « Download DOCX » (déjà générique par format), même résumé.

**Non-objectifs (6b)**
- Remplissage automatique de l'Annex 4, sections en parallèle, enregistrements (6c). Aperçu Word dans *Company knowledge* (6d).
- Rendu fidèle au pixel : `docx-preview` approche la mise en page (polices remplacées si absentes, tableaux jamais coupés : l'Annex 4 s'affiche sur 2 pages au lieu de 3).

## 3. Aperçu Word : du localisateur au DOM

- Corps rendu : `section.docx > article > *` de toutes les pages, dans l'ordre ; les `<p>` de premier niveau = paragraphes du corps (même compte que python-docx, vérifié : 37 pour l'Annex 4), les `<table>` de premier niveau = tableaux du corps.
- Cellule : `tr` d'index `row`, puis `td` d'index `cell` parmi les cellules propres de la ligne (une cellule fusionnée horizontalement = un `td` ; une continuation de fusion verticale est rendue masquée et une place `gridBefore`/`gridAfter` est un `td` sans paragraphe : écartées, comme `distinct_cells`) ; les `<p>` ajoutés par l'aperçu ne comptent pas, puis `p` d'index `paragraph` parmi les enfants `p` du `td`.
- Positions : le texte d'un paragraphe rendu a la même longueur que celui de python-docx (une tabulation = un `<span>` d'un caractère) ; `start` / `end` s'y appliquent tels quels.
- Écriture dans l'aperçu (impérative, après chaque changement de valeur, idempotente) : `in_paragraph` → un `<span data-value-of>` inséré à `start` (ou en fin) ; `new_paragraph` → un `<p data-value-of>` inséré après le libellé ; `replace_leader` → les caractères `[start, end)` masqués et la valeur à leur place ; espace ajoutée devant comme à l'export. Valeur vide → rien d'inséré (pointillés visibles).
- Zone surlignée : le paragraphe qui reçoit la valeur (`data-field-id`, classes de teinte, `aria-label` = libellé, cliquable) ; signature : le paragraphe du libellé.
- Logique pure et testée à part : `findParagraph(root, locator)` et `writePreviewValue(paragraph, locator, value)` (module `features/document-preview`).

## 4. Composants

- `PreviewZone` devient générique : `{ id, label, value, tone, place }`, `place` = `{ format: "pdf", page, box, fontSize, placeholders }` ou `{ format: "docx", locator }`. `DocumentPreview` choisit `PdfPages` (inchangé) ou `WordDocument` selon le format du formulaire ; légende partagée.
- `WordDocument` : charge le fichier (`/forms/{id}/file`), `renderAsync` dans un conteneur, puis applique les zones à chaque rendu ; erreur de chargement = même message que pour le PDF (`documentLoadError`) ; squelette pendant le chargement.

## 5. Tests

- Back : seed (Annex 4 parsée : compteurs sur la carte, 49 champs, `pages` = 3 × A4), `pages` d'un Word synthétique sans `docProps/app.xml` (marques + 1), refus d'une valeur autre que yes/no sur un champ `yes_no` (422) ; le test « a Word form has no fields yet » est remplacé.
- Front, logique pure (vrai `docx-preview` sous jsdom, sur le vrai fichier de l'Annex 4) : `findParagraph` pour chaque mode et pour les paragraphes du corps ; `writePreviewValue` (insertion à une position au milieu d'un paragraphe, nouveau paragraphe, pointillés remplacés, idempotence, valeur vide).
- Front, écrans (skill `screen-tests`) : *Tender* (carte Word avec compteurs, `Auto-fill` désactivé et son infobulle) ; *Live fill* sur l'Annex 4 (fixture générée depuis le parseur, fichier réel servi par MSW) : saisie d'un champ → valeur dans l'aperçu à la frappe, sauvegarde ; Oui/Non par boutons → « Yes » dans l'aperçu ; clic sur une zone → champ sélectionné ; export → « Download DOCX ».
- e2e : après le scénario de l'Annex 7, ouvrir l'Annex 4 par son URL, saisir un champ et une déclaration, vérifier l'aperçu, télécharger le DOCX (nom d'origine, signature `PK`) ; carte *Tender* : `Auto-fill` désactivé.

## 6. Choix laissés au builder / faits par Claude

- Nommage des composants et des fonctions, détail des classes de teinte en HTML.
- Fixture `annex4` du front générée par un script depuis le parseur back (ou écrite une fois et vérifiée par un test back), au choix du builder.
- Mise à jour de `docs/PLAN.md` (6b détaillée), `docs/USER_FLOW.md` si besoin, `docs/ARCHITECTURE.md` (aperçu Word).
