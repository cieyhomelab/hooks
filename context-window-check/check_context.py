#!/usr/bin/env python3
"""
Claude Code hook: checks context window fill level based on transcript_path.
Attach to UserPromptSubmit (see settings.json below).

How it works:
- Claude Code stores the session as a .jsonl file (transcript_path).
- Every assistant entry contains a "usage" field with the actual token
  counts returned by the API (input_tokens, cache_read_input_tokens,
  cache_creation_input_tokens), plus a "model" field naming the model that
  produced it.
- The sum of the three usage values from the LATEST assistant entry ~= how
  many tokens the conversation history currently occupies in context.
- The context window itself depends on which model produced that entry, so
  it's looked up from CONTEXT_WINDOW_BY_MODEL keyed on the "model" field,
  instead of being a single fixed constant.
"""
import json
import sys

# Context window (tokens) per model, keyed by model-ID prefix. Longest
# matching prefix wins, so a specific entry can override a shorter, more
# general one. Update this table when new models ship - see shared/models.md
# in the claude-api skill, or query the live Models API
# (client.models.retrieve(model_id).max_input_tokens) for current data.
CONTEXT_WINDOW_BY_MODEL = {
    "claude-fable-5": 1_000_000,
    "claude-mythos-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
}
# Fallback for models not in the table above - older/legacy models, or a
# model that shipped after this table was last updated.
DEFAULT_CONTEXT_WINDOW = 200_000

WARN_AT = 0.75   # warning
CRIT_AT = 0.90   # critical, suggest /compact


def get_context_window(model: str) -> int:
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    for prefix in sorted(CONTEXT_WINDOW_BY_MODEL, key=len, reverse=True):
        if model.startswith(prefix):
            return CONTEXT_WINDOW_BY_MODEL[prefix]
    return DEFAULT_CONTEXT_WINDOW


def get_latest_usage(transcript_path: str):
    latest_usage = None
    latest_model = None
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message", {})
                usage = msg.get("usage")
                if usage:
                    latest_usage = usage
                    latest_model = msg.get("model")
    except FileNotFoundError:
        return None, None
    return latest_usage, latest_model


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # don't block the session on a parse error

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    usage, model = get_latest_usage(transcript_path)
    if not usage:
        sys.exit(0)

    context_window = get_context_window(model)
    used = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    pct = used / context_window

    if pct >= CRIT_AT:
        note = (
            f"[context-check] CRITICAL: context is {pct:.0%} full "
            f"({used:,}/{context_window:,} tokens). Consider /compact."
        )
    elif pct >= WARN_AT:
        note = (
            f"[context-check] Warning: context is {pct:.0%} full "
            f"({used:,}/{context_window:,} tokens)."
        )
    else:
        # below threshold — print nothing, to avoid cluttering the context
        sys.exit(0)

    # For UserPromptSubmit: stdout on exit 0 is injected into Claude's context.
    print(note)
    sys.exit(0)


if __name__ == "__main__":
    main()
