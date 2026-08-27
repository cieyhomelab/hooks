# hooks

A collection of Claude Code hooks, one folder per hook set. Each folder's
own `README.md` has the full explanation, flow diagram, and installation
steps.

## Available hooks

| Folder | Hooks | What it does |
|---|---|---|
| [`context-window-check`](context-window-check/README.md) | `check_context.py` (`UserPromptSubmit`) | Watches a session's context window fill level and prints a warning as it approaches the limit. Observational only — prints a note and never blocks. |
| [`dumb-zone-40`](dumb-zone-40/README.md) | `agent_degradation_check.py` (`Stop`) | Once context is large, checks for heuristic signs of agent behavioral degradation (context drift, hallucinated artifacts, tool misuse, …). Observational only — prints `OK`/`WARNING` and never blocks. |

Each hook is installed and runs independently — they don't call or depend
on each other, and either can be used without the other.
