"""Read-only live evaluation of the Claims Resolution Agent.

Evaluates:
- Real model-driven tool selection through the LangGraph runtime.
- Retrieval of actual claim-related policy evidence.
- Evidence references used by the final proposal.
- Grounding against the exact policy clause required by the
  existing faculty-provided classifier.

This script does not create agent runs, persist decisions,
approve claims, or execute refunds.

Run from the project root:
    python sprint3_live_qwen_eval.py --claim-id <EXISTING_CLAIM_ID>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4


# Allow imports when this script is saved in the project root.
REPOSITORY_ROOT = Path(__file__).resolve().parent

if not (REPOSITORY_ROOT / "claims_resolution_agent").is_dir():
    print(
        "ERROR: Save this script in the repository root, next to "
        "'claims_resolution_agent'.",
        file=sys.stderr,
    )
    raise SystemExit(2)

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


from claims_resolution_agent.application.agent_factory import (
    build_claim_agent_graph,
)
from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.application.services.customers import (
    CustomerService,
)
from claims_resolution_agent.application.services.policies import (
    PolicyService,
)
from claims_resolution_agent.domain.agent_models import (
    AgentContext,
    AgentEvidence,
)
from claims_resolution_agent.infrastructure.database import SessionLocal
from claims_resolution_agent.infrastructure.repositories.claims import (
    ClaimRepository,
)
from claims_resolution_agent.infrastructure.repositories.customers import (
    CustomerRepository,
)
from claims_resolution_agent.server.classification import (
    classify as faculty_classify,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only live-model evaluation of dynamic tool "
            "selection and policy-evidence grounding."
        )
    )

    parser.add_argument(
        "--claim-id",
        required=True,
        help="ID of an existing claim in the configured database.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Optional override for the graph iteration limit.",
    )

    parser.add_argument(
        "--max-tool-calls",
        type=int,
        default=None,
        help="Optional override for the graph tool-call limit.",
    )

    return parser.parse_args()


def print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def validate_positive_limit(
    name: str,
    value: int | None,
) -> None:
    if value is not None and value < 1:
        raise ValueError(f"{name} must be at least 1.")


def main() -> int:
    args = parse_args()

    claim_id = args.claim_id.strip()

    if not claim_id:
        print(
            "ERROR: --claim-id cannot be empty.",
            file=sys.stderr,
        )
        return 2

    try:
        validate_positive_limit(
            "--max-iterations",
            args.max_iterations,
        )
        validate_positive_limit(
            "--max-tool-calls",
            args.max_tool_calls,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print_header("SPRINT 3 LIVE QWEN EVALUATION")

    print(
        "Model:",
        os.getenv(
            "CLAIMS_AGENT_MODEL",
            "(not configured in environment)",
        ),
    )
    print(
        "Endpoint:",
        os.getenv(
            "OPENAI_BASE_URL",
            "(not configured in environment)",
        ),
    )
    print(f"Claim ID: {claim_id}")
    print("Execution mode: read-only graph evaluation")
    print("Decision persistence: disabled")
    print("Refund execution: not performed")

    session = SessionLocal()

    try:
        # Use the existing application services and repositories.
        claim_service = ClaimService(
            ClaimRepository(session)
        )

        customer_service = CustomerService(
            CustomerRepository(session)
        )

        policy_service = PolicyService()

        # Retrieve a real claim from the configured database.
        claim = claim_service.get_claim(claim_id)

        if claim is None:
            print(
                "\nERROR: Claim not found in the configured database. "
                "Use an existing claim ID.",
                file=sys.stderr,
            )
            return 2

        # Retrieve the associated customer record.
        customer = customer_service.get_customer(
            claim.customer_id
        )

        if customer is None:
            print(
                "\nERROR: The claim's associated customer record "
                "could not be retrieved. Evaluation stopped.",
                file=sys.stderr,
            )
            return 2

        # The existing deterministic classifier is used only as an
        # evaluation reference. It does not choose the LLM's tool path.
        classification = faculty_classify(
            claim.model_dump(mode="json"),
            customer.approved_refunds_trailing_90d,
        )

        expected_clause = classification["policy_clause"]
        expected_document = expected_clause.split("#", 1)[0]

        initial_evidence = AgentEvidence(
            evidence_id=f"claim:{claim.claim_id}",
            source_type="claim",
            source_id=claim.claim_id,
            content=claim.model_dump_json(),
            locator=f"claim:{claim.claim_id}",
            relevance=1.0,
        )

        context = AgentContext(
            run_id=f"RUN-LIVE-{uuid4().hex[:12]}",
            claim_id=claim.claim_id,
            claim=claim.model_dump(mode="json"),
            evidence=[initial_evidence],
        )

        graph_options = {}

        if args.max_iterations is not None:
            graph_options["max_iterations"] = (
                args.max_iterations
            )

        if args.max_tool_calls is not None:
            graph_options["max_tool_calls"] = (
                args.max_tool_calls
            )

        # Construct the real agent graph. The factory registers the
        # actual claim, customer, and policy context tools and uses
        # the configured OpenAI-compatible model.
        graph = build_claim_agent_graph(
            claim_service=claim_service,
            customer_service=customer_service,
            policy_service=policy_service,
            **graph_options,
        )

        print_header("AUTHORITATIVE VALIDATION TARGET")

        print(
            f"Classifier tier: {classification['tier']}"
        )
        print(
            f"Required policy clause: {expected_clause}"
        )
        print(
            "Customer history was read from the application service."
        )
        print(
            "Customer and claim record contents will not be printed."
        )

        print_header("RUNNING REAL AGENT GRAPH")

        # This invokes the actual reasoning engine and graph.
        # It does not invoke the persistence orchestrator.
        result = graph.invoke(context)

        final_context = result["context"]
        proposal = result.get("proposal")

        # Build an index of evidence actually accumulated by the graph.
        evidence_by_id = {
            item.evidence_id: item
            for item in final_context.evidence
        }

        proposal_evidence_ids = (
            list(proposal.evidence_ids)
            if proposal is not None
            else []
        )

        referenced_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in proposal_evidence_ids
            if evidence_id in evidence_by_id
        ]

        missing_evidence_ids = [
            evidence_id
            for evidence_id in proposal_evidence_ids
            if evidence_id not in evidence_by_id
        ]

        # Only retrieved policy evidence can satisfy these checks.
        policy_evidence = [
            item
            for item in final_context.evidence
            if item.source_type == "policy"
        ]

        referenced_policy_evidence = [
            item
            for item in referenced_evidence
            if item.source_type == "policy"
        ]

        exact_clause_retrieved = any(
            item.source_id == expected_document
            and item.locator == expected_clause
            for item in policy_evidence
        )

        exact_clause_referenced = any(
            item.source_id == expected_document
            and item.locator == expected_clause
            for item in referenced_policy_evidence
        )

        print_header("EXECUTION RESULTS")

        print(f"Graph status: {result['status']}")
        print(
            f"Reasoning iterations: {result['iteration_count']}"
        )
        print(
            f"Tool calls: {result['tool_call_count']}"
        )
        print(
            "Evidence items accumulated:",
            len(final_context.evidence),
        )

        print("\nTool selection sequence:")

        if not final_context.tool_calls:
            print("  No tools were selected.")

        for index, tool_call in enumerate(
            final_context.tool_calls,
            start=1,
        ):
            print(
                f"  {index}. {tool_call.tool_name}"
                f" — {tool_call.purpose}"
            )

            # Display policy search queries for evaluation.
            # Do not print customer or claim record contents.
            query = tool_call.arguments.get("query")

            if isinstance(query, str):
                print(f"     Search query: {query}")

        print("\nRecorded graph events:")

        if not final_context.reasoning_steps:
            print("  No reasoning/control-flow events recorded.")

        for step in final_context.reasoning_steps:
            print(f"  - {step.action}")

        print("\nRetrieved policy evidence (metadata only):")

        if not policy_evidence:
            print("  No policy evidence was retrieved.")

        for item in policy_evidence:
            exact_marker = ""

            if (
                item.source_id == expected_document
                and item.locator == expected_clause
            ):
                exact_marker = " [EXACT REQUIRED CLAUSE]"

            print(
                f"  - Evidence ID: {item.evidence_id}\n"
                f"    Document: {item.source_id}\n"
                f"    Locator: {item.locator}"
                f"{exact_marker}"
            )

        print_header("MODEL PROPOSAL")

        if proposal is None:
            print("No proposal was produced.")
        else:
            print(
                f"Recommendation: {proposal.recommendation}"
            )
            print(
                f"Model-proposed tier: {proposal.tier}"
            )
            print(
                f"Confidence: {proposal.confidence} "
                "(uncalibrated model assessment)"
            )

            print("Reasons:")

            for reason in proposal.reasons:
                print(f"  - {reason}")

            print(
                "Cited evidence IDs:",
                proposal.evidence_ids,
            )

        # These are separate checks. A policy clause being retrieved
        # does not establish that the model used it in its proposal.
        print_header("GROUNDING AND EXECUTION CHECKS")

        checks = {
            "Graph completed with a proposal": (
                result["status"] == "completed"
                and proposal is not None
            ),
            "At least one approved tool was selected": (
                len(final_context.tool_calls) > 0
            ),
            "All proposal evidence IDs exist": (
                not missing_evidence_ids
            ),
            "Proposal cites retrieved policy evidence": (
                len(referenced_policy_evidence) > 0
            ),
            "Required policy clause was retrieved": (
                exact_clause_retrieved
            ),
            "Proposal cites the exact required clause": (
                exact_clause_referenced
            ),
        }

        for check_name, passed in checks.items():
            label = "PASS" if passed else "FAIL"
            print(f"{label} — {check_name}")

        if missing_evidence_ids:
            print(
                "\nMissing evidence IDs:",
                missing_evidence_ids,
            )

        all_passed = all(checks.values())

        print_header("FINAL EVALUATION")

        if all_passed:
            print(
                "PASS — This live run satisfied every defined check."
            )
        else:
            print(
                "NOT ACCEPTED — One or more checks failed."
            )
            print(
                "Use the results above to identify the specific "
                "failure; do not treat this run as successful."
            )

        print(
            "\nResearch limitation: one successful run does not "
            "demonstrate general reasoning quality. Multiple claims, "
            "alternative investigation paths, adversarial cases, and "
            "failure cases must be evaluated separately."
        )

        return 0 if all_passed else 1

    except KeyboardInterrupt:
        print(
            "\nEvaluation interrupted.",
            file=sys.stderr,
        )
        return 130

    except Exception as exc:
        print(
            "\nERROR: Live evaluation failed "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )
        print(
            "Inspect the local configuration and application logs. "
            "This run must not be counted as a successful evaluation.",
            file=sys.stderr,
        )
        return 2

    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())