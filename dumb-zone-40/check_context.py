#!/usr/bin/env python3
"""
Claude Code hook: checks context window fill level based on transcript_path.
Attach to UserPromptSubmit (see settings.json below).

How it works:
- Claude Code stores the session as a .jsonl file (transcript_path).
- Every assistant entry contains a "usage" field with the actual token
  counts returned by the API (input_tokens, cache_read_input_tokens,
  cache_creation_input_tokens).
- The sum of these three values from the LATEST assistant entry ~= how many
  tokens the conversation history currently occupies in context.
"""
import json
import sys

# Match this to the model you're using (Sonnet/Opus/Haiku standard is 200k,
# [1m] variants have 1,000,000).
CONTEXT_WINDOW = 200_000
WARN_AT = 0.75   # warning
CRIT_AT = 0.90   # critical, suggest /compact


def get_latest_usage(transcript_path: str):
    latest = None
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
                    latest = usage
    except FileNotFoundError:
        return None
    return latest


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # don't block the session on a parse error

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    usage = get_latest_usage(transcript_path)
    if not usage:
        sys.exit(0)

    used = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    pct = used / CONTEXT_WINDOW

    if pct >= CRIT_AT:
        note = (
            f"[context-check] CRITICAL: context is {pct:.0%} full "
            f"({used:,}/{CONTEXT_WINDOW:,} tokens). Consider /compact."
        )
    elif pct >= WARN_AT:
        note = (
            f"[context-check] Warning: context is {pct:.0%} full "
            f"({used:,}/{CONTEXT_WINDOW:,} tokens)."
        )
    else:
        # below threshold — print nothing, to avoid cluttering the context
        sys.exit(0)

    # For UserPromptSubmit: stdout on exit 0 is injected into Claude's context.
    print(note)
    sys.exit(0)


if __name__ == "__main__":
    main()
