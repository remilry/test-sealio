# 8 — Durcissement : gestion d'erreur, réessais, évaluation (design)

> Étape 8 de `docs/PLAN.md`. Branche `step-8-hardening`. S'appuie sur 5b (indexation), 5c/5d (façade LLM, job, flux SSE), 6c (groupes en parallèle, deux exécutions), 7/7.5 (Live fill).
> Statut : en attente de validation (2026-11-05).

## 1. Intention

L'utilisateur veut une **gestion d'erreur solide à tous les niveaux**, avec des **réessais automatiques** dès qu'un appel (OpenAI, API du back, réseau) échoue pour une raison passagère, au lieu d'une erreur au premier raté. Si OpenAI est vraiment injoignable, « tant pis, ça ne fonctionnera pas » : l'app le dit clairement, sans chercher à faire mieux.

Le cas qui compte : sur l'Annex 4 (9 appels en parallèle), **un seul appel raté fait aujourd'hui échouer tout le remplissage**, et la seule issue est *Discard answers*, qui efface aussi les valeurs de l'utilisateur. Une section ratée ne doit plus coûter les autres : on garde ce qui a marché et on **réessaie uniquement la section manquante**.

Deuxième volet : **évaluer la qualité des réponses** sur la vérité terrain des deux annexes, avec un rapport chiffré montrable.

## 2. Constat (recon du 2026-11-05)

- `OpenAILLM` : SDK avec `max_retries=2`, `timeout=120` ; ne réessaie qu'avant le début du flux. Coupure en plein flux, `output_parsed is None`, sortie invalide : aucun réessai, `LLMError` aussitôt.
- `run_groups` : la première exception arrête tous les groupes (`stop`) et le run finit `failed` (« Answers could not be found right now… »). Relancer exige `DELETE /fill` (`POST /fill` → 409 sur un formulaire commencé).
- Le message d'un remplissage échoué n'est plus affiché après un rechargement (limite connue de 5d).
- `index_documents` : toute exception inattendue → `error` définitif, il faut redéposer le fichier.
- Front : pas de `error.tsx` / `global-error.tsx` ; `QueryClient` avec le réessai par défaut de TanStack (3 fois, y compris sur 404/422 → « introuvable » après ~7 s) ; mutations jamais réessayées (sauvegarde ratée → « Not saved — press Enter to try again »). Le flux SSE se reconnecte déjà avec un délai croissant (gardé).
- Back : pas de gestionnaire général des exceptions inattendues.
- `scripts/ground_truth.py` ne couvre que l'Annex 4 (44 champs) ; `record_llm.py --replay` le compare aux enregistrements.

## 3. Objectifs, non-objectifs, anti-objectifs

**Objectifs**

*Réessais*
- **Appels OpenAI** : chaque appel de modèle est réessayé quelle que soit la panne passagère : connexion coupée (avant ou pendant le flux), délai dépassé, limite de débit (429), erreur 5xx, réponse vide ou inutilisable (`output_parsed` nul, JSON invalide). 3 essais au total, délais croissants avec un peu d'aléa (_choix de Claude_ : ~2 s puis ~4 s ; respecter `Retry-After` s'il est donné et raisonnable). Pas de réessai sur ce qui ne passera pas mieux (clé invalide 401, requête refusée 400, enregistrement absent du `FakeLLM`). Chaque essai raté est journalisé (raison, numéro d'essai), jamais montré à l'utilisateur.
- Un essai qui avait commencé à écrire : le texte grisé (« Writing… ») de ses champs repart de zéro au nouvel essai. Un champ déjà publié (validé) par l'essai raté reste tel quel ; le nouvel essai ne doit ni le dupliquer de façon visible ni le dégrader (_au builder_ : soit on garde les champs publiés et on ne republie que les autres, soit on republie en remplaçant ; dans les deux cas un seul `answered` final cohérent à l'écran).
- **Indexation d'un document** : une panne passagère (base, modèle d'embeddings) est réessayée (_choix de Claude_ : 3 essais, délais courts) avant `error`. Un fichier illisible (`UnreadableDocumentError`) reste une erreur immédiate.
- **Front** : une lecture (`useQuery`) est réessayée sur panne réseau et 5xx (_choix de Claude_ : 3 fois, délai croissant), **jamais** sur 4xx (404 « introuvable » affiché tout de suite). Une écriture idempotente — sauvegarde d'un champ (`PATCH`), `DELETE /fill` — est réessayée seule (_choix de Claude_ : 2 fois) sur panne réseau / 5xx avant « Not saved ». `POST /fill` et l'ajout de documents ne sont pas réessayés automatiquement (pas idempotents).

- **Durée maximale** (_choix de Claude_) : les réessais du SDK sont désactivés (`max_retries=0`), seuls ceux de la façade comptent ; chaque essai est borné à 90 s (appel entier ; un appel normal de l'Annex 4 dure ~28 s) ; pas d'échéance globale par section : au pire ~4,5 min avant qu'une section bloquée soit marquée ratée.
- **Une seule des deux exécutions échoue** (décision utilisateur) : la section n'est pas ratée ; les réponses de l'exécution qui a marché sont gardées, **toutes à vérifier** (type `unsure`, *To check*, comme une valeur trouvée par une seule des deux exécutions aujourd'hui) ; un champ que cette exécution laisse vide reste `missing`. La section n'est ratée que si les deux exécutions échouent.

*Section ratée, remplissage gardé*
- Une section (groupe d'appel) qui échoue **après ses réessais** n'arrête plus les autres : les autres groupes continuent, leurs réponses sont gardées.
- Le run se termine alors dans un état « terminé avec des sections manquantes » (_au builder_ : nouveau statut ou statut `done` + liste des champs ratés ; il doit survivre à un rechargement). Les champs de la section ratée restent **sans réponse** et sont marqués dans la liste et la file (ligne : étiquette courte du type « Not filled » ; carte : « Couldn't be filled automatically. Retry above or enter it yourself. ») — ils sont comptés comme ouverts (*No value*).
- **Bouton global *Retry*** au-dessus de la liste des champs (décision utilisateur), visible seulement quand des champs ont raté : bandeau « n fields couldn't be filled » + `Retry`. Il relance **uniquement ces champs** (leurs groupes, mêmes règles : deux exécutions, fusion, publication au fil de l'eau) ; les réponses déjà là et les valeurs de l'utilisateur ne bougent pas, pas de *Discard*. Un champ raté que l'utilisateur a rempli entre-temps n'est pas relancé. Le *Retry* peut lui-même finir avec des champs ratés (le bandeau reste avec le nouveau nombre).
- **Toutes les sections ont raté** (OpenAI injoignable, clé invalide) : même mécanisme, tous les champs à répondre sont ratés ; le message dit en mots simples que le remplissage automatique n'est pas disponible pour l'instant, *Retry* reste proposé. Pas de détail technique, pas de mot « IA ».
- Le message d'échec (total ou partiel) **reste affiché après un rechargement** (il vient de l'état du formulaire, pas seulement du flux).
- Une panne inattendue hors appel de modèle (bug, base) garde le comportement actuel : run `failed`, message générique (« Discard its answers… »).

*Filets de sécurité*
- Front : `app/error.tsx` (erreur d'un écran, dans la coquille : titre simple, *Try again* = `reset()`), `app/global-error.tsx` (la coquille elle-même) ; textes via next-intl quand c'est possible (`global-error` est hors des providers : _au builder_, textes en dur autorisés là si l'i18n n'est pas disponible, avec une exception ESLint ciblée).
- Back : gestionnaire général des exceptions inattendues → 500 `{"detail": "Something went wrong on our side. Please try again in a moment."}`, exception journalisée avec la trace.
- États de chargement et messages : vérifier chaque écran (*Home*, *Tender*, *Company knowledge*, *Live fill*, *Setup*, *Export*) pour un état chargement / introuvable / erreur avec *Try again* (skill `frontend-code-style`) ; combler les trous trouvés, sans refonte.

*Évaluation*
- Vérité terrain de l'**Annex 7** ajoutée à `scripts/ground_truth.py` (d'après `knowledge-base/GROUND_TRUTH.md`).
- **`make eval`** : rejoue les enregistrements des deux annexes (aucun appel payant) et affiche par annexe : justes, doutes signalés à raison, « introuvable » correct, **erreurs silencieuses** (réponse fausse présentée comme sûre, objectif 0), coût et durée enregistrés.
- **`make eval-live RUNS=n`** : même chose avec le vrai modèle (et le vrai modèle d'embeddings), n essais par annexe, plus la stabilité d'un essai à l'autre (champs qui changent de résultat). N'écrase pas les enregistrements versionnés.
- Rapport écrit dans **`docs/EVALUATION.md`** (chiffres par annexe et par catégorie, erreurs silencieuses listées, coût et durée, date, modèle) ; réutilisé par le README (étape 9).
- **Chiffres réels** : 3 essais par annexe (~$0.20 au total, décision utilisateur), le résultat de chaque essai rapporté avant le suivant (règle de 6c).

**Non-objectifs**
- Faire marcher le remplissage quand OpenAI est hors service (pas de fournisseur de repli, pas de file d'attente).
- Reprendre un run tué par un arrêt du serveur (reste `failed` au démarrage, comme aujourd'hui).
- Améliorer la qualité du modèle ou du prompt : l'évaluation mesure, elle ne corrige pas (les écarts trouvés vont dans le rapport et le plan).
- Monitoring, alertes, métriques en continu (→ *Remaining features*).

**Anti-objectifs**
- Un réessai qui produit un doublon visible, une valeur qui clignote, ou qui remplace une valeur de l'utilisateur.
- Un message technique (« APIError », code HTTP, trace) ou le mot « AI » dans l'interface.
- Un *Retry* qui touche des réponses déjà obtenues.
- Des tests qui attendent réellement les délais de réessai (les délais doivent être injectables / nuls en test).

## 4. Contraintes

- Seul `app/llm/` connaît le SDK OpenAI : la classification « passager ou non » et la boucle de réessai vivent dans la façade / l'adaptateur (_choix de Claude_ : un enrobage `RetryingLLM` autour de n'importe quel `LLM`, testable avec un faux qui échoue n fois).
- `FakeLLM` : latence `none` dans les tests et l'e2e ; il faut pouvoir simuler une section qui échoue (pour les tests du job et l'e2e du *Retry*).
- Les événements du flux restent ordonnés par identifiant (verrou de publication actuel) ; le *Retry* doit pouvoir être suivi en direct comme un remplissage.
- Types du front régénérés (`make gen-api`) si l'API change ; `docs/DB_SCHEMA.md` régénéré (`make db-schema`) si une colonne est ajoutée (migration Alembic).
- Tests sur le critique (consigne du projet) : façade (réessais, classification, partiel remis à zéro), moteur (une exécution sur deux ratée → réponses `unsure`), job (une section ratée, toutes ratées, *Retry* ne relance que les ratés et garde l'utilisateur, discard pendant un *Retry*), indexation (passagère réessayée, illisible non), API (nouvel endpoint ou état), écran *Live fill* (bandeau, *Retry*, après rechargement), `error.tsx`, réessai des requêtes (pas sur 404), évaluation (rejeu des deux annexes sans erreur silencieuse). E2e : une section ratée puis *Retry* réussi, si le `FakeLLM` le permet simplement.

## 5. Laissé au builder

- Forme de l'API du *Retry* (_proposition_ : `POST /forms/{id}/fill/retry`, 409 si un run est en cours ou s'il n'y a rien à relancer) et de l'état exposé (`FillState.ai_run` : statut, message, nombre / ids des champs ratés).
- Stockage des champs ratés (colonne sur `form_fill`, état de réponse, ou déduit des événements) ; conservation ou non des événements du run précédent au lancement d'un *Retry* (le résumé final « n of m fields filled » doit rester juste).
- Paramètres exacts des réessais (dans `config.py`, surchargeables par variable d'environnement), libellés exacts en anglais (`en.json`).
- Découpage en commits.
