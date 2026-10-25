# Sprint 3 — Agentic Reasoning Core

## Objective

Implement a single-agent reasoning runtime that uses an OpenAI-compatible
LLM, dynamically selects approved tools, retrieves real application evidence,
and produces a validated decision proposal without directly approving or
executing refunds.

## Implementation

- LangGraph coordinates the reasoning, validation, tool execution, recovery,
  proposal finalization, and execution-limit paths.
- The configured LLM chooses investigation actions and constructs tool inputs.
- Claim, customer, and policy tools use the existing application services.
- Tool registration, argument validation, active-claim scope checks, evidence
  validation, iteration limits, and tool-call limits provide deterministic
  safeguards.
- Proposals must cite evidence that exists in the execution context and must
  reference retrieved policy evidence.
- Where a proposal rationale explicitly discusses customer or refund history,
  the graph requires cited customer evidence.
- The existing faculty-provided classifier remains authoritative in the
  orchestration layer for classification tier, reasons, and required policy
  clause.
- The agent produces proposals. It does not independently authorize or execute
  refunds.

## Automated validation

The recorded regression run completed with:

- Agent graph tests: 12 passed.
- Dynamic investigation-path test: 1 passed.
- Complete test suite: 79 passed, 0 failed.
- `git diff --check`: no whitespace errors; Git emitted Windows line-ending
  conversion warnings for existing modified files.

The suite includes scripted reasoning tests. These validate software behavior
and graph control flow; they do not independently demonstrate live LLM quality.

## Live-model evaluation

Model: `qwen3.5:4b`

Endpoint: local Ollama OpenAI-compatible endpoint.

Evaluation claim:
`CLM-S3-LIVE-EVAL-20261025222830787`

Recorded live result:

- Graph completed.
- Three reasoning iterations.
- One actual policy-tool call.
- The graph rejected an initial proposal lacking policy evidence, continued
  the investigation, and accepted a later proposal.
- The proposal cited existing evidence and the exact policy clause required
  by the faculty classifier.
- All checks implemented in the live evaluation script passed.

The evaluation script did not persist a decision or execute a refund. The
synthetic evaluation claim was created separately through the claims API.

## Known limitations

The live evaluation was one scenario, not a comprehensive benchmark.

The final rationale referred to Section 3 restrictions without including that
section in the proposal's cited evidence IDs. The current evaluation checks
evidence references and the required policy clause, but it does not establish
that every material statement in the rationale is semantically supported by
the cited evidence.

The customer-history safeguard currently uses explicit textual markers. It is
a targeted check, not a general semantic fact-verification system.

Model confidence is an uncalibrated model assessment and must not be reported
as calibrated confidence.

Broader rationale-grounding evaluation, adversarial cases, alternative
investigation paths, and robustness testing remain necessary. Policy-grounded
retrieval and evidence evaluation are retained in the agreed Sprint 4 scope.

## Acceptance summary

Sprint 3 has demonstrated the core agent graph, deterministic execution
safeguards, automated regression behavior, and one successful live Qwen run.

These results do not establish production readiness or comprehensive reasoning
robustness. The limitations above must remain visible in project documentation
and subsequent evaluation work.
