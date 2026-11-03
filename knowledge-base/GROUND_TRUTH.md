# Ground truth — Alpenlogic AG (fictitious)

Reference for tests and AI evaluation. "Today" for freshness checks: **2026-11-02**.
Documents are in `documents/` (regenerate with `generator/generate.py`). Everything is fictitious.

Expected statuses: `answer` (found, sourced) · `not_found` · `conflict` (sources disagree) · `stale` (found but out of date) · `human` (engaging declaration: auto-ticked when the AI finds evidence, shown with its proof and changeable by the user; left empty without evidence — see `docs/USER_FLOW.md` §4).

## Annex 4 — factual fields

| Field | Expected value | Source | Status |
|---|---|---|---|
| Exact company name | Alpenlogic AG | 01 | answer |
| Street, postcode, city, country | Pfingstweidstrasse 31, 8005 Zurich, Switzerland | 01 | answer |
| Telephone / e-mail | +41 44 555 01 20 / marc.keller@alpenlogic.example (general: info@alpenlogic.example) | 04 | answer |
| Responsible / contact person | Marc Keller, CEO | 04, 01 | answer |
| UID | CHE-123.456.789 | 01 | answer |
| Legal form | Company limited by shares (AG) | 01 | answer |
| Registered office | Zurich (ZH) | 01 | answer |
| Legal form since | 14 March 2016 | 01 | answer |
| Ownership structure | Founders 60 %, Helvetia Growth Fund 25 %, employee participation foundation 15 %; no treasury shares | 09 (shares), 09 | answer |
| Share capital | CHF 500,000 (1,000 registered shares of CHF 500, fully paid) | 01, 09 | answer |
| Business purpose | See purpose in commercial register | 01 | answer |
| Main activity | Digital transformation consulting and development of AI technical solutions | 04 | answer |
| Secondary activities | Cloud platform operation/support and training | 04 | answer |
| Certificates | ISO 27001, ISO 9001 (valid until 12 March 2028) | 05, 04 | answer |
| Employees with higher professional training | 14 | 04 | **conflict** with 09 on totals; category count only in 04 → answer, flag date |
| Employees with professional training | 9 | 04 | answer |
| Auxiliary staff | not documented (04 only gives "other staff and apprentices: 5") | — | **not_found** |
| Apprentices | not documented separately in the current brochure (09 says 3 at end-2024, outdated) | 04, 09 | **not_found** (do not reuse the 2024 figure silently) |
| Total headcount (if asked) | 28 (June 2026) vs 31 (Dec 2024) | 04 vs 09 | **conflict** — propose the most recent (28) with both sources shown |
| Insurance company | Limmat Versicherungen AG | 03 | answer |
| Amount per claim — personal injury | CHF 10,000,000 | 03 | **stale** |
| Amount per claim — property damage | CHF 10,000,000 | 03 | **stale** |
| Amount per claim — financial loss | CHF 5,000,000 | 03 | **stale** |
| Competent tax office | Cantonal Tax Office Zurich, Corporate Taxes, Steuerweg 12, 8090 Zurich | 06 | answer |
| AHV compensation office | SVA Zurich, **Hardturmstrasse 120**, 8005 Zurich (certificate 2026) vs Röntgenstrasse 17 (09, 10) | 07 vs 09, 10 | **conflict** — most recent official document (07) proposed |
| BVG pension fund | Sammelstiftung Limmat BVG, Seestrasse 200, 8002 Zurich | 08 | answer |
| Foreign bidders: pension scheme details (two fields) | Not applicable (Swiss bidder) | — | not_found / not applicable |

## Annex 4 — Yes/No declarations (`human`: auto-ticked with evidence, empty otherwise)

| Question (short) | Proposed answer | Evidence | Status |
|---|---|---|---|
| Occupational health and safety | Yes | 10 §1 | human |
| Applicable collective employment agreement | Yes (none applicable; no CEA binds the activity) — must be explained, not a plain Yes | 10 §2 | human |
| Standard employment contract | Yes (none applicable) | 10 §2 | human |
| Customary wages / BGSA | Yes | 10 §3 | human |
| ILO core conventions (services abroad) | — | none | not_found |
| Non-discrimination / equal treatment | Yes | 10 §4 | human |
| Taxes paid (cantonal, municipal, federal) | Yes | 06 | human |
| VAT paid | — (06 explicitly excludes VAT) | none | not_found |
| Social security paid (AHV, IV, EO, FAK, ALV, BVG) | Yes | 07, 08 | human |
| …including UVG | — (UVG not covered by any document) | none | not_found |
| Contributions under generally binding CEAs | Yes (none applicable) | 10 §2 | human |
| Debt enforcement / bankruptcy / collection pending | No | 02 | human |
| Seizures in the past 12 months | No | 02 | human |
| Agreements restricting competition | No | 11 §1 | human |
| Not on sanctioned-bidders list (Art. 45 para. 3 IVöB) | Yes | 11 §2 | human |
| Swiss environmental regulations | Yes | 10 §5 | human |
| Environmental conventions (services abroad) | — | none | not_found |
| Obligations included in subcontractor agreements | Yes | 11 §3 | human |

## Annex 7 — fields

| Field | Expected value | Status |
|---|---|---|
| Project number / title / name | Provided by the user | user input |
| Name of the contracting authority | Provided by the user | user input |
| Name and legal form | Alpenlogic AG, company limited by shares (AG) | answer (01) |
| Business address | Pfingstweidstrasse 31, 8005 Zurich | answer (01) |
| Contact person / phone / e-mail | Marc Keller / +41 44 555 01 20 / marc.keller@alpenlogic.example | answer (04) |
| Art. 29c declaration (no Russian connection) | Supported by 09 and 11 §2 but legally binding | human |
| Place and date | User input | user input |
| First name(s) and surname(s) of signatory | Marc Keller (sole signature, 01) — proposal only | human |
| Signature | Never filled by the AI | user input |

## Deliberate traps (summary)

1. **Stale**: insurance certificate (03) expired on 2026-10-31.
2. **Conflict**: headcount (28 vs 31) and AHV office address (Hardturmstrasse 120 vs Röntgenstrasse 17).
3. **Not found**: auxiliary staff, apprentices, VAT, UVG, all "services abroad" questions, foreign-scheme fields.
4. **Fresh**: register extracts (01, 02) are under 3 months old (20 and 22 October 2026).
5. **Engaging**: every Yes/No and the Art. 29c declaration are ticked only with verified evidence, the proof is always shown, and those without evidence stay empty for the user.

## Noise and distractors (added so extraction is realistic)

Every document has a letterhead, reference number, "Page x of y", legal boilerplate and unrelated sections (fees, audit history, salary bands, references, premiums, etc.). Distractors that look like answers but are **not**:

| Distractor | Where | Correct reading |
|---|---|---|
| Share capital CHF 100,000 (200 shares) | 01 register history, entry 1 | Superseded (status "modified"); current capital is CHF 500,000 |
| Former address Hardstrasse 201, 8005 Zurich | 01 history | Old address; current is Pfingstweidstrasse 31 |
| Cyber liability CHF 2,000,000, legal expenses CHF 250,000, aggregate CHF 20,000,000 | 03 schedule | Not the "per claim" amounts asked for in the form |
| Premium CHF 14,860, deductibles | 03 | Irrelevant to the form |
| Customer satisfaction 4.6 (2025) vs 4.5 (2024) | 04, 09 | Irrelevant |
| Headcount 31, 29.2 FTE, 3 apprentices (2024) | 09 | Outdated; see conflict rule above |
| Payroll and contribution amounts per year | 07 | Irrelevant to the form |
| Management: Nadine Frei, CFO (no signing authority) | 09 | Not a signatory; Annex 7 signatory proposal stays Marc Keller |
| Pension plan rates, funding ratio | 08 | Irrelevant to the form |
| Individual tax periods, provisional assessment 2025 | 06 | Statement that all taxes are paid still holds |
| Founding address in the brochure's "single site" line | 04 | Same as current address |
