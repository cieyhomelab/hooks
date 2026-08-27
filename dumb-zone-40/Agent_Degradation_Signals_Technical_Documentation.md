# Agent Degradation Signals - Technical Documentation

## 1. Overview

This document defines degradation signals observed in LLM-based agents operating in iterative reasoning loops, CI/CD pipelines, code-modification workflows, and multi-turn planning tasks. Each signal represents a measurable deviation from expected agent behavior and can be used for monitoring, evaluation, and automated guardrail enforcement.

## 2. Core Degradation Signals (Baseline Set)

### 2.1 Context Drift

Loss of previously established constraints, goals, or decisions. The agent reintroduces resolved issues or treats old conclusions as new.

### 2.2 State Inconsistency

Contradictions between the agent’s earlier outputs or accepted assumptions. Includes reversing decisions without justification.

### 2.3 Hallucinated Artifacts

Generation of non-existent files, directories, commands, API endpoints, or configuration keys.

### 2.4 Constraint Violation

Ignoring hard rules such as “do not modify public API”, “do not change schema”, or “do not touch CI config”.

### 2.5 Root-Cause Blindness

Patching symptoms (e.g., adjusting tests) instead of analyzing underlying defects in logic or architecture.

### 2.6 Decision Collapse

Summaries become longer and more verbose while the number of concrete decisions decreases.

## 3. Extended Degradation Signals (Advanced Set)

### 3.1 Plan Oscillation

Frequent switching between incompatible plans, reintroducing rejected approaches, or abandoning validated steps.

### 3.2 Speculative Execution

Performing actions not requested by the user or unrelated to the task (e.g., refactoring unrelated modules).

### 3.3 Tool Misuse

Incorrect tool invocation, ignoring tool outputs, or repeating failed tool calls.

### 3.4 Semantic Drift in Code

Modifying code in ways that change behavior without acknowledging the change, especially in public interfaces.

### 3.5 Regression Introduction

Fixing one issue while silently breaking unrelated functionality due to incomplete dependency reasoning.

### 3.6 Prompt Overfitting

Overly literal interpretation of irrelevant details from earlier turns; misalignment due to accumulated prompt noise.

### 3.7 Memory Contamination

Mixing constraints or assumptions from previous tasks into current reasoning.

### 3.8 Temporal Inconsistency

Referencing states or events that should not exist yet (e.g., “after we merge this branch” when no merge occurred).

### 3.9 Evaluation Degradation

Declining ability to critique its own output; accepting flawed reasoning, incorrect code, or failing tests as valid.

## 4. Mapping to Baseline List

| Original item | Technical category |
|---|---|
| repeats previous arrangements | Context Drift / State Inconsistency |
| invents paths/commands/files | Hallucinated Artifacts |
| ignores constraints | Constraint Violation |
| patches around failing test | Root-Cause Blindness |
| summaries longer, decisions fewer | Decision Collapse |
| contradicts earlier agreements | State Inconsistency |

Missing items include: Plan Oscillation, Speculative Execution, Tool Misuse, Semantic Drift, Regression Introduction, Prompt Overfitting, Memory Contamination, Temporal Inconsistency, Evaluation Degradation.

## 5. Recommended Usage

This documentation section can be placed under:

- Agent Reliability
- LLM Operational Risks
- Evaluation & Monitoring
- Guardrails & Safety
- CI/CD Agent Behavior
