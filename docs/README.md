# Documentation

Reference material for the SHPE UH website. Setup and contributing live in the
[main README](../README.md) — start there. These pages are for looking things up once you're
already running.

## Start here

| Page | Read it when |
|---|---|
| [glossary.md](glossary.md) | A term in the code or a ticket means nothing to you — PSID, pillar, E-Board, seed vs. bootstrap |
| [architecture.md](architecture.md) | You want to know where code goes and how a request travels front to back |
| [features.md](features.md) | You need to know what a feature is *supposed* to do before you change it |

## Reference

| Page | Contents |
|---|---|
| [api.md](api.md) | Every endpoint, with the role each one requires |
| [environment.md](environment.md) | Every environment variable, backend and frontend |
| [database.md](database.md) | Migrations, seed data, seeded test accounts, resetting locally |
| [testing.md](testing.md) | Running the suite, writing a test, CI, testing a real phone QR scan |

## Operations

Only relevant if you run the live site.

| Page | Contents |
|---|---|
| [integrations.md](integrations.md) | One-time setup for Square, Google Drive, and both Google Sheets |
| [deployment.md](deployment.md) | Vercel + Railway deploy, production database setup, going-live checklist |

## A note on accuracy

These pages describe behaviour that's enforced in code. If you change that behaviour, the doc is
part of the change — update it in the same pull request. A doc that quietly goes stale is worse
than no doc, because the next person trusts it.
