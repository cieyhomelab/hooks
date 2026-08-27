#!/usr/bin/env python3
"""
Hook Claude Code: sprawdza zapełnienie okna kontekstu na podstawie transcript_path.
Podłącz do UserPromptSubmit (patrz settings.json poniżej).

Zasada działania:
- Claude Code zapisuje sesję jako plik .jsonl (transcript_path).
- Każdy wpis asystenta zawiera pole "usage" z faktycznymi liczbami tokenów
  zwróconymi przez API (input_tokens, cache_read_input_tokens,
  cache_creation_input_tokens).
- Suma tych trzech wartości z NAJNOWSZEGO wpisu asystenta ~= ile tokenów
  aktualnie zajmuje historia rozmowy w kontekście.
"""
import json
import sys

# Dopasuj do modelu, którego używasz (Sonnet/Opus/Haiku standardowo 200k,
# warianty [1m] mają 1 000 000).
CONTEXT_WINDOW = 200_000
WARN_AT = 0.75   # ostrzeżenie
CRIT_AT = 0.90   # krytyczne, sugestia /compact


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
        sys.exit(0)  # nie blokujemy sesji przez błąd parsowania

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
            f"[context-check] KRYTYCZNE: kontekst zapełniony w {pct:.0%} "
            f"({used:,}/{CONTEXT_WINDOW:,} tokenów). Rozważ /compact."
        )
    elif pct >= WARN_AT:
        note = (
            f"[context-check] Uwaga: kontekst zapełniony w {pct:.0%} "
            f"({used:,}/{CONTEXT_WINDOW:,} tokenów)."
        )
    else:
        # poniżej progu — nic nie wypisujemy, żeby nie zaśmiecać kontekstu
        sys.exit(0)

    # Dla UserPromptSubmit: stdout przy exit 0 trafia do kontekstu Claude.
    print(note)
    sys.exit(0)


if __name__ == "__main__":
    main()
