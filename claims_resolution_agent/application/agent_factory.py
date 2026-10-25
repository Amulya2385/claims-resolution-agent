import os

from claims_resolution_agent.application.agent_executor import AgentToolExecutor
from claims_resolution_agent.application.agent_graph import AgentGraph
from claims_resolution_agent.application.agent_tools import (
    ClaimContextTool,
    CustomerContextTool,
    PolicyContextTool,
)
from claims_resolution_agent.application.llm import LLMClient
from claims_resolution_agent.application.llm_reasoning_engine import (
    LLMReasoningEngine,
)
from claims_resolution_agent.application.openai_compatible_llm import (
    OpenAICompatibleLLMClient,
)
from claims_resolution_agent.application.reasoning_validator import (
    ReasoningOutputValidator,
)
from claims_resolution_agent.application.tool_registry import AgentToolRegistry
from claims_resolution_agent.application.services.claims import ClaimService
from claims_resolution_agent.application.services.customers import CustomerService
from claims_resolution_agent.application.services.policies import PolicyService


def _resolve_positive_limit(
    explicit_value: int | None,
    environment_name: str,
    default_value: int,
) -> int:
    if explicit_value is not None:
        value = explicit_value
    else:
        raw_value = os.getenv(environment_name)

        if raw_value is None:
            value = default_value
        else:
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise ValueError(
                    f"{environment_name} must be a positive integer"
                ) from exc

    if value < 1:
        raise ValueError(
            f"{environment_name} must be a positive integer"
        )

    return value


def build_claim_agent_graph(
    claim_service: ClaimService,
    customer_service: CustomerService,
    policy_service: PolicyService,
    *,
    llm_client: LLMClient | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_iterations: int | None = None,
    max_tool_calls: int | None = None,
) -> AgentGraph:
    """
    Compose the single-agent runtime from application dependencies.

    Production usage creates an OpenAI-compatible client. Tests may inject
    a fake LLMClient to exercise the actual graph without network requests.
    """

    registry = AgentToolRegistry()

    registry.register(
        ClaimContextTool(claim_service)
    )
    registry.register(
        CustomerContextTool(customer_service)
    )
    registry.register(
        PolicyContextTool(policy_service)
    )

    if llm_client is None:
        llm_client = OpenAICompatibleLLMClient(
            tool_registry=registry,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    elif any(
        value is not None
        for value in (model, api_key, base_url)
    ):
        raise ValueError(
            "model, api_key and base_url cannot be supplied when "
            "llm_client is injected"
        )

    reasoning_engine = LLMReasoningEngine(
        llm_client=llm_client
    )

    output_validator = ReasoningOutputValidator(
        tool_registry=registry
    )

    tool_executor = AgentToolExecutor(
        registry=registry
    )

    resolved_max_iterations = _resolve_positive_limit(
        max_iterations,
        "CLAIMS_AGENT_MAX_ITERATIONS",
        8,
    )

    resolved_max_tool_calls = _resolve_positive_limit(
        max_tool_calls,
        "CLAIMS_AGENT_MAX_TOOL_CALLS",
        8,
    )

    return AgentGraph(
        reasoning_engine=reasoning_engine,
        output_validator=output_validator,
        tool_executor=tool_executor,
        max_iterations=resolved_max_iterations,
        max_tool_calls=resolved_max_tool_calls,
    )