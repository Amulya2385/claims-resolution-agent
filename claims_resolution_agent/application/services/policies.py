from claims_resolution_agent.domain.models import PolicySearchResult
from claims_resolution_agent.policy.policy_index import get_index


class PolicyService:
    def search_policy(
        self,
        query: str,
        k: int = 4,
    ) -> list[PolicySearchResult]:
        if not query.strip():
            raise ValueError("policy query cannot be empty")

        if k < 1 or k > 20:
            raise ValueError("policy result count must be between 1 and 20")

        index = get_index()
        results = index.search(query, k=k)

        return [
            PolicySearchResult(
                doc_id=result["doc_id"],
                locator=result["locator"],
                heading=result["heading"],
                text=result["text"],
                rrf_score=result["rrf_score"],
            )
            for result in results
        ]
