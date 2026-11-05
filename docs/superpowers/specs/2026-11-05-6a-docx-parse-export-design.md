# 6a — Parseur et export DOCX (design)

> Étape 6a de `docs/PLAN.md` (Annex 4 de bout en bout, découpée en 6a–6d). Branche `step-6a-docx-parse-export`.
> Statut : validé dans la conversation (2026-11-05).

## 1. Intention

Donner à l'Annex 4 (Word) les deux briques critiques que l'Annex 7 (PDF) a déjà : un **parseur** qui en sort la liste des champs dans la représentation commune (`FormSchema`), et un **exporteur** qui écrit les réponses dans le fichier Word d'origine sans toucher à sa mise en page. Back seulement, pur et testé ; l'UI vient en 6b, le remplissage automatique en 6c.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- `forms/parsing/docx_parser.py` : `parse_docx(bytes) -> FormSchema`, pur, générique.
- `export/docx_exporter.py` : `export_docx(bytes, [(DocxLocator, valeur)]) -> bytes`, pur.
- `DocxLocator` dans `parsing/schema.py` ; `ParsedField.locator` et `FieldOut.locator` deviennent une union discriminée par `format` (`pdf` | `docx`).
- `export/service.py` choisit l'exporteur selon le format (l'erreur « Export of Word forms is not available yet » disparaît).

**Non-objectifs (6a)**
- Le parseur n'est **pas encore branché** dans `forms_service.PARSERS` : l'Annex 4 reste « non lisible » dans l'app (carte sans compteurs, *Auto-fill* désactivé) tant que l'UI ne sait pas l'afficher. Branchement en 6b (le formulaire déjà importé est parsé au démarrage suivant, `parsed_at` étant nul).
- Pas d'aperçu, pas de remplissage automatique, pas de sections en parallèle (6b, 6c).
- Pas de comparaison visuelle par rendu (LibreOffice) : vérification structurelle seulement (_choix de Claude, accepté_ ; tranche la question ouverte du §5 du plan).

**Anti-objectifs**
- Aucune règle propre à l'Annex 4 (pas de libellé, d'index de tableau ni de clé codés en dur) : uniquement des règles de structure Word.
- Ne jamais modifier autre chose que les paragraphes des champs remplis (styles, bordures, tabulations du reste, en-têtes, pieds de page intacts).

## 3. Règles du parseur (génériques)

Ordre de lecture du corps du document (paragraphes et tableaux mêlés, cellules fusionnées vues une seule fois). Un champ = un endroit où écrire une réponse, avec son libellé.

1. **Ligne « libellé | cellule vide »** : la réponse va dans le premier paragraphe de la cellule vide.
2. **Libellé suivi d'un paragraphe vide dans la même cellule** : la réponse va dans ce paragraphe vide (sous le libellé).
3. **Libellé terminé par `:`** (éventuellement suivi d'espaces / tabulations) **sans paragraphe vide après** : la réponse s'écrit à la suite du libellé, dans le même paragraphe. Plusieurs libellés empilés dans une cellule (« Business purpose: / Main activity: / Secondary activities: », les montants d'assurance) = un champ chacun.
4. **Libellé court seul dans sa cellule, sans `:` ni paragraphe vide** (en-têtes de colonnes de l'effectif) : la réponse va dans un **nouveau paragraphe** inséré sous le libellé, même format.
5. **Tableau Oui/Non** : un tableau dont la ligne d'en-tête mentionne « Yes/No » ; chaque ligne suivante dont la cellule de droite est vide = un champ `yes_no` (libellé = texte de la cellule de gauche, paragraphes joints), réponse dans la cellule de droite. Une ligne dont toutes les cellules portent le même libellé terminé par `:` (fusion, « Remarks: ») suit les règles 2/3 (champ texte).
6. **Pointillés** (`…` / `.`, même seuil que le parseur PDF) dans un paragraphe : la réponse remplace les pointillés ; libellé = texte du paragraphe, pointillés remplacés par `…`.
7. **Hors tableau** : un paragraphe qui commence par un libellé terminé par `:` suivi de tabulations (« Place and date: ») = un champ (règle 3) ; un libellé qui mentionne signature ou cachet (`signature|stamp`, comme en PDF) = champ `signature`, jamais rempli.
8. **Pas un champ** : texte long (phrases d'explication, avertissements), cellule d'en-tête sans espace de réponse (« Number of employees in the area… », titre du questionnaire hors pointillés), ligne d'en-tête du tableau Oui/Non.
9. **Type** : `yes_no` (règle 5), `signature` (règle 7), sinon `text`.
10. **Section** : une par tableau, `Table {n}` (n à partir de 1, comme `Page {n}` en PDF), plus `Text` pour les champs hors tableau. **Clé** : libellé normalisé comme en PDF, suffixée `_2`, `_3`… en cas de doublon (deux « For foreign bidders, details of the pension scheme (exact address) »).

Les seuils (longueur maximale d'un libellé, etc.) sont au choix du builder, ajustés pour que le schéma attendu de l'Annex 4 sorte et que les cas synthétiques passent.

**Schéma attendu de l'Annex 4** (à figer dans le test, à quelques ajustements près constatés par le builder) : ~49 champs — pointillé de l'en-tête (1), identité (5), forme juridique / siège / depuis / actionnariat / capital / but / activité principale / activités secondaires / certificats (9), effectif (4), assurance : détails, compagnie, 3 montants (5), offices : impôts, AVS, étrangers, LPP, étrangers (5), 17 Oui/Non, Remarks (1), Place and date (1), signature (1).

## 4. `DocxLocator`

```
format: "docx"
table: int | None      # index du tableau dans le corps ; None = paragraphe hors tableau
row: int | None
cell: int | None       # index de la cellule distincte dans la ligne (fusions dédoublonnées)
paragraph: int         # index du paragraphe dans la cellule, ou dans le corps si hors tableau
mode: "in_paragraph" | "new_paragraph" | "replace_leader"
after_run: int | None  # in_paragraph : écrire après ce run (None = fin du paragraphe / paragraphe vide)
```

Il sert à l'exporteur et, en 6b, à retrouver la zone dans l'aperçu HTML (`docx-preview`) pour la surligner. Forme exacte au builder si un champ manque.

## 5. Exporteur

- La valeur (sur une ligne, espaces normalisés) est écrite dans un **nouveau run** qui copie la mise en forme (`rPr`) du run du libellé, ou de la marque de paragraphe pour un paragraphe vide.
- `in_paragraph` après un libellé : un espace est ajouté si le libellé ne finit pas par un espace ou une tabulation. Si des tabulations suivent le libellé avant un autre texte (« Place and date: ⇥⇥⇥⇥⇥ Company stamp… »), on en retire autant que la valeur en occupe (largeur estimée / tabulation par défaut du document), en en gardant au moins une, pour que le texte qui suit ne soit pas repoussé.
- `new_paragraph` : paragraphe inséré juste après le libellé, propriétés de paragraphe copiées.
- `replace_leader` : les pointillés sont remplacés par la valeur dans leur run.
- Oui/Non écrit en toutes lettres, `Yes` / `No`. Valeur vide ou signature : rien n'est écrit.

## 6. Tests

- **Parseur** : schéma attendu de l'Annex 4 (clés, libellés, types, sections, mode) ; un document Word synthétique par règle (construit avec `python-docx` dans le test).
- **Exporteur** : sur l'Annex 4, rouvrir le DOCX exporté → chaque valeur dans le bon paragraphe, avec la police du libellé ; signature jamais écrite ; tabulations absorbées ; **reste identique** : le XML du corps hors paragraphes des champs remplis est inchangé, ainsi que les autres parties du paquet (styles, en-têtes, numérotation) ; exporter sans valeur = document identique.
- **API / service** : `export_file` d'un formulaire Word (formulaire parsé dans le test) renvoie un DOCX avec le nom de fichier d'origine.

## 7. Choix laissés au builder / faits par Claude

- Seuils de détection, forme exacte du localisateur, nom des clés : au builder, guidés par le schéma attendu.
- Front : `make gen-api` après l'union ; l'écran *Live fill* ne traite que les localisateurs PDF (rétrécissement de type), sans changement visible.
- Mise à jour de `docs/PLAN.md` (6a détaillée) et `docs/ARCHITECTURE.md` si le modèle de données change (le JSONB `locator` ne change pas de colonne).
