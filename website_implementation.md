Argus-PG Landing Page — Final Implementation Plan
0. Goal (non-negotiable)

The landing page must:

Explain Argus-PG in 30 seconds

Prove it works with real evidence

Convert engineers to running the CLI locally

Avoid hype, signup flows, or backend infra

Primary CTA: GitHub
Secondary CTA: “Try it in 5 minutes”

1. Tech Stack (Final)
Frontend

Astro (static site generator)

Tailwind CSS

TypeScript (optional but recommended)

Hosting

Vercel

Static deployment

Preview builds on PRs

Zero backend

What we explicitly do NOT use

❌ Next.js

❌ React SPA

❌ Serverless functions

❌ Auth / database

❌ Analytics initially

2. Repository Strategy (Choose One)
✅ Recommended: Separate Repo
argus-pg-site/
├── src/
│   ├── pages/
│   │   └── index.astro
│   ├── components/
│   │   ├── Hero.astro
│   │   ├── Flow.astro
│   │   ├── Proof.astro
│   │   ├── Safety.astro
│   │   ├── TryIt.astro
│   │   └── Footer.astro
│   └── styles/
│       └── global.css
├── public/
│   └── diagrams/
├── astro.config.mjs
├── tailwind.config.js
└── package.json


Reason: Keeps infra code and product messaging isolated.

3. Page Structure (Single Page, High Signal)
3.1 Hero (Above the Fold)

Text

An automated DBA that never touches production.

Subtext:

Sandbox-validated PostgreSQL index recommendations.

CTAs

View on GitHub (primary)

See Real Validation (scrolls to proof)

3.2 Problem Statement

Explain:

Schema drift

Missing indexes

Silent regressions

Manual DBA bottleneck

Keep it technical and brief.

3.3 How Argus-PG Works

Visual flow (text or simple SVG):

Observe → Analyze → Hypothesize → Sandbox → Decide


One sentence per step.

3.4 Proof (MOST IMPORTANT SECTION)

This is the conversion engine.

Include verbatim output:

PASS | Improvement: 82.34x (Cost: 4.46 → 0.05)
Index: idx_users_email


Explain:

Seq Scan was the bottleneck

Index Scan fixed it

Measured, not guessed

Production untouched

3.5 Safety Guarantees

Bullets:

Read-only production access

All writes in ephemeral Docker

No auto-apply

LLM is optional and untrusted

3.6 Try It in 5 Minutes (Conversion Bridge)

Copy-paste friendly:

git clone https://github.com/SpaceCypher/argus-pg.git
cd argus-pg
poetry install
poetry shell

argus audit --dsn postgres://...
argus check query.sql


Link directly to README.

3.7 What Argus-PG Is NOT

Explicitly repel wrong expectations:

Not AI auto-tuning

Not config magic

Not production-mutating

This increases trust.

3.8 Footer

GitHub link

License

“Built as infra, not a demo”

4. Astro Setup (Concrete Steps)
4.1 Create Project
npm create astro@latest argus-pg-site
cd argus-pg-site
npm install


Choose:

Static site

TypeScript: yes

Tailwind: yes

4.2 Styling Rules

One global stylesheet

No JS unless absolutely required

No animations beyond subtle transitions

5. Vercel Deployment (Step-by-Step)
5.1 Create Vercel Project

Import GitHub repo

Framework preset: Astro

Output directory: dist

5.2 Build Settings

Build command: npm run build

Output: dist

No environment variables needed

5.3 Deployment Model

main → production

PRs → preview URLs

6. Conversion Mechanics (Critical)
Funnel
Landing Page
  ↓
GitHub Repo
  ↓
README (Proof + Safety)
  ↓
Local CLI Trial
  ↓
Adoption (watch / CI / PR bot later)

Rules

No signup

No email capture

No pricing

GitHub is the product surface

7. Success Criteria

The landing page is successful if:

A backend engineer can go from page → running argus audit in under 10 minutes.

Not stars.
Not signups.
Execution.

8. What Comes After (Not Now)

GitHub PR Bot

CLI explanation formatter (--explain)

Optional read-only dashboard

No core changes required.

Final Lock-In Recommendation

Astro + Tailwind + Vercel, single static page, GitHub-first conversion.

You already built the hard part.
This page just needs to tell the truth clearly.