#!/usr/bin/env python3
"""
Claude Code hook (Stop event): agent-degradation-check.

Design decisions (per Socratic session with the user):
- Hook event: Stop — runs once per finished assistant turn, which is where
  degradation accumulated over an iterative reasoning loop is most visible.
- CONTEXT_SIZE / CONTEXT_CONTENT are not native Stop-hook fields. They are
  derived from transcript_path the same way check_context.py does:
    CONTEXT_SIZE    = latest assistant usage's
                       input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    CONTEXT_CONTENT = extracted text of the last RECENT_ENTRIES transcript entries
  The warn threshold is WARN_FRACTION (0.75, mirrors check_context.py's
  WARN_AT) of the context window for the model that produced the latest
  usage entry, looked up from the same CONTEXT_WINDOW_BY_MODEL table
  check_context.py uses - not a fixed token count, since context windows
  vary by model (1M for current Opus/Sonnet-tier models, 200k for Haiku).
- RULES are parsed dynamically from DOC_PATH (headings "## N.M Name" /
  "### N.M Name"), so if the doc gains/loses signals, RULES follows.
- Detection is hand-crafted heuristics per signal: a curated table of
  weak textual proxies (SIGNAL_HEURISTICS) keyed by signal name. This is
  a best-effort approximation, NOT semantic understanding — a signal like
  "Hallucinated Artifacts" can't be reliably detected by regex. Any rule
  parsed from the doc that isn't in the curated table falls back to a
  generic word-match on its own name, so newly added doc signals still
  produce *something* rather than being silently skipped.
- Non-blocking: this hook always exits 0 and never sets "decision": "block",
  so it never forces the agent to keep going — it's an observational signal,
  not an enforcement gate.
- Output goes through the hook JSON "systemMessage" field, which Claude Code
  shows directly to the user in the CLI and does NOT inject into Claude's
  context (unlike plain stdout on other hook events). Silent on OK — a
  message would otherwise pop up after every single turn.

Output (only on WARNING; silent otherwise):
  {"systemMessage": "agent-degradation-check: WARNING — N violations detected: [...]", "suppressOutput": true}
"""
import json
import re
import sys
from collections import deque
from pathlib import Path

# Context window (tokens) per model, keyed by model-ID prefix. Longest
# matching prefix wins. Kept in sync with context-window-check/check_context.py
# - update both when new models ship. See shared/models.md in the claude-api
# skill, or query the live Models API (client.models.retrieve(model_id)
# .max_input_tokens) for current data.
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

WARN_FRACTION = 0.40     # mirrors check_context.py's WARN_AT
VIOLATION_THRESHOLD = 2    # warn when MORE than this many rules are violated
RECENT_ENTRIES = 20        # trailing transcript entries used to build CONTEXT_CONTENT
DOC_PATH = Path(__file__).resolve().parent / "Agent_Degradation_Signals_Technical_Documentation.md"


def get_context_window(model: str) -> int:
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    for prefix in sorted(CONTEXT_WINDOW_BY_MODEL, key=len, reverse=True):
        if model.startswith(prefix):
            return CONTEXT_WINDOW_BY_MODEL[prefix]
    return DEFAULT_CONTEXT_WINDOW

RULE_HEADING_RE = re.compile(r'^#{2,3}\s+\d+\.\d+\s+(.+?)\s*$', re.MULTILINE)

# Best-effort keyword/phrase proxies per known signal (case-insensitive regex).
# Any single match on a rule's list counts as one violation of that rule.
SIGNAL_HEURISTICS = {
    "Context Drift": [
        r"let'?s revisit", r"going back to", r"as (we|i) discussed (earlier|before)",
        r"already (resolved|decided) this",
    ],
    "State Inconsistency": [
        r"on second thought", r"contradicts (my|our) earlier",
        r"reversing (my|the) (earlier|previous) decision", r"actually,? i was wrong",
    ],
    "Hallucinated Artifacts": [
        r"assum(e|ing) (the|this) file (exists|is there)",
        r"should (already )?exist at", r"presumably (located|found) (at|in)",
    ],
    "Constraint Violation": [
        r"despite (being told|the instruction) not to",
        r"even though this (violates|breaks) the (rule|constraint)",
        r"ignoring the constraint",
    ],
    "Root-Cause Blindness": [
        r"just (adjust|tweak|patch) the test", r"skip (the )?failing test",
        r"disable the test", r"patch around",
    ],
    "Decision Collapse": [
        r"to summarize.{0,200}to summarize", r"in summary.{0,200}in summary",
    ],
    "Plan Oscillation": [
        r"let'?s go back to the original plan", r"changing (the )?approach again",
        r"on second thought,? let'?s use",
    ],
    "Speculative Execution": [
        r"while i(’|')?m at it", r"also (decided to|went ahead and) refactor",
        r"additionally cleaned up",
    ],
    "Tool Misuse": [
        r"same error again", r"failed again", r"tried (that|this) again anyway",
    ],
    "Semantic Drift in Code": [
        r"silently changed", r"without mentioning", r"changed the (return type|public api)",
    ],
    "Regression Introduction": [
        r"this may break", r"introduced a regression", r"unrelated test (now )?fails",
    ],
    "Prompt Overfitting": [
        r"strictly following the earlier phrasing", r"literally interpreting",
        r"taking (that|this) instruction literally",
    ],
    "Memory Contamination": [
        r"in the previous (project|task)", r"from (an|the) earlier (task|project)",
    ],
    "Temporal Inconsistency": [
        r"after we merge this", r"once this is deployed", r"after the release",
        r"now that we'?ve shipped",
    ],
    "Evaluation Degradation": [
        r"(looks|should be) good enough", r"this (looks|seems) fine",
    ],
}


def load_rules(doc_path: Path):
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return []
    names = []
    for m in RULE_HEADING_RE.finditer(text):
        name = m.group(1).strip()
        if name not in names:
            names.append(name)
    return names


def fallback_patterns(rule_name: str):
    words = [w for w in re.split(r'\W+', rule_name.lower()) if len(w) > 3]
    return [re.escape(w) for w in words]


def get_transcript_tail(transcript_path: str, max_entries: int):
    entries = deque(maxlen=max_entries)
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
                entries.append(entry)
                msg = entry.get("message", {})
                usage = msg.get("usage")
                if usage:
                    latest_usage = usage
                    latest_model = msg.get("model")
    except FileNotFoundError:
        return None, None, None
    return list(entries), latest_usage, latest_model


def extract_text(entry: dict) -> str:
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                parts.append(f"{block.get('name', '')} {json.dumps(block.get('input', {}))}")
            elif btype == "tool_result":
                result_content = block.get("content")
                if isinstance(result_content, str):
                    parts.append(result_content)
                elif isinstance(result_content, list):
                    for rc in result_content:
                        if isinstance(rc, dict) and rc.get("type") == "text":
                            parts.append(rc.get("text", ""))
    return "\n".join(parts)


def evaluate_rules(content: str, rules: list):
    violations = []
    for rule in rules:
        patterns = SIGNAL_HEURISTICS.get(rule) or fallback_patterns(rule)
        if any(re.search(pat, content, re.IGNORECASE) for pat in patterns):
            violations.append(rule)
    return violations


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    tail_entries, usage, model = get_transcript_tail(transcript_path, RECENT_ENTRIES)
    if tail_entries is None or not usage:
        sys.exit(0)

    context_size = (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    warn_threshold = WARN_FRACTION * get_context_window(model)

    if context_size <= warn_threshold:
        sys.exit(0)

    rules = load_rules(DOC_PATH)
    if not rules:
        sys.exit(0)

    content = "\n".join(extract_text(e) for e in tail_entries)
    violations = evaluate_rules(content, rules)

    if len(violations) > VIOLATION_THRESHOLD:
        note = f"agent-degradation-check: WARNING — {len(violations)} violations detected: {violations}"
        # systemMessage is shown directly to the user in the CLI and is NOT
        # injected into Claude's context. Silent (no output) on OK, to avoid
        # popping a message after every single turn.
        print(json.dumps({"systemMessage": note, "suppressOutput": True}))
    sys.exit(0)


if __name__ == "__main__":
    main()

# Example settings.json registration (Stop event):
#
# {
#   "hooks": {
#     "Stop": [
#       {
#         "hooks": [
#           {
#             "type": "command",
#             "command": "python \"D:\\hooks\\dumb-zone-40\\agent_degradation_check.py\""
#           }
#         ]
#       }
#     ]
#   }
# }
