Argus-PG: Code Push & Repository Discipline

Argus-PG is developed as a production-grade infrastructure tool.
Code changes must reflect completed, scoped work, not experimentation.

The repository follows strict Git discipline to prevent:

accidental rework

scope bleed

unstable main branches

loss of execution history

Branching Model

main

Always stable

Always runnable

Represents approved, completed work only

Task

One branch per task 

Examples:

phase-0-setup

phase-1-domain-models

task-2.3-sandbox-lifecycle

Direct commits to main are forbidden.

Commit Rules

A commit is allowed only when a task is fully complete.

Rules:

One task = one branch

One task = one meaningful commit (max 2 if unavoidable)

No “WIP”, “fix”, or partial commits

No mixing tasks or phases in a single commit

Each commit must correspond to a task listed in WORK_PLAN.md.

Commit Message Format (Mandatory)

All commits must follow:

<type>(<scope>): <clear outcome>


Allowed types:

chore – setup, tooling, configuration

feat – new functionality

refactor – internal cleanup, no behavior change

test – tests only

docs – documentation only

Examples:

chore(setup): initialize venv, poetry, and repo structure
feat(domain): define query and execution plan domain models
feat(core): implement docker sandbox lifecycle

Progress Tracking (Non-Negotiable)

Every completed task requires:

Code commit

Update to WORK_STATUS.md

A task must exist in exactly one section:

✅ Completed

🚧 In Progress

⏳ Pending

No task may be worked on unless it is marked In Progress.

Merging Policy

Merging to main is allowed only when:

Task is marked Completed

Branch scope matches exactly one task

Code is stable and clean

Tests (if applicable) pass

Preferred merge method: Squash merge
Branches should be deleted after merge.

Prohibited Actions

Pushing unfinished work

Mixing multiple tasks in one commit

Editing unrelated files “while here”

Rewriting history on main

Large, unfocused commits

Guiding Principle

main must always represent a point-in-time where development could stop without regret.`