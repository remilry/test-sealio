# AI form filler

This repository is a technical test for Sealio (Swiss AI SaaS for tenders and RFPs), due Thursday, November 5.

## Product

### Context

Besides a written proposal (Word or PowerPoint), buyers often send forms
that bidders must fill in: company information, insurance, tax and legal
declarations. Filling a form by hand takes hours, while most answers
already exist somewhere in the company's documents.

The goal is to build the feature that lets a user fill in forms like these
with AI. The user clicks on the file; the following screens, buttons and
steps are up to us.

Two real forms from a Swiss public tender are in `forms/` (Annex 4 in Word,
Annex 7 in PDF).

Constraints:
    - Runs on localhost. No deployment, no real login.
    - We invent the bidder company and its knowledge base.

### Priorities

1. A clear, smooth user flow
2. Reliable AI: answers grounded in the company's documents, with sources,
   no invented answers, a human in the loop where it matters
3. The filled form exported in its original format and layout

This is an MVP built in 3-4 days, and it must work end to end. Secondary
features (monitoring, metrics, ...) go in a "Remaining features" section
of the README and are implemented only if time allows.

Testing is not secondary: the critical parts (form parsing, answer
validation, export to the original format) must be covered by tests.

## How we work

    - Work in small steps, with tests for the critical parts, and commit as we go
    - When a something is unclear, ask me instead of guessing.
    - Keep this file up to date as decisions are made and add sections if needed, so it always reflects the current state of the project. Ask for validation when upating this file.
