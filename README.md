# hooks

A collection of Claude Code hooks, one folder per hook set. Each folder's
own `README.md` has the full explanation, flow diagram, and installation
steps.

## Available hooks

| Folder | Hooks | What it does |
|---|---|---|
| [`dumb-zone-40`](dumb-zone-40/README.md) | `check_context.py` (`UserPromptSubmit`), `agent_degradation_check.py` (`Stop`) | Watches a session for a filling context window and, once it's large, for heuristic signs of agent behavioral degradation (context drift, hallucinated artifacts, tool misuse, …). Both are observational only — they print `OK`/`WARNING` and never block. |
