import json
from datetime import datetime, timezone

from claims_resolution_agent.domain.models import (
    EvaluationCreate,
    EvaluationData,
)
from claims_resolution_agent.infrastructure.models import Evaluation
from claims_resolution_agent.infrastructure.repositories.evaluations import (
    EvaluationRepository,
)


class EvaluationService:
    def __init__(self, repository: EvaluationRepository):
        self.repository = repository

    def get_evaluation(
        self,
        evaluation_id: str,
    ) -> EvaluationData | None:
        evaluation = self.repository.get_by_id(evaluation_id)

        if evaluation is None:
            return None

        return self._to_domain(evaluation)

    def create_evaluation(
        self,
        evaluation: EvaluationCreate,
    ) -> EvaluationData:
        existing = self.repository.get_by_id(
            evaluation.evaluation_id
        )

        if existing is not None:
            raise ValueError(
                f"evaluation already exists: {evaluation.evaluation_id}"
            )

        claim_id = self.repository.get_claim_id_for_run(
            evaluation.run_id
        )

        if claim_id is None:
            raise ValueError(
                f"agent run not found or has no claim: {evaluation.run_id}"
            )

        record = Evaluation(
            evaluation_id=evaluation.evaluation_id,
            claim_id=claim_id,
            run_id=evaluation.run_id,
            evaluator_type="system",
            metric=evaluation.evaluation_type,
            score=evaluation.accuracy,
            passed=evaluation.passed,
            details=json.dumps(
                {
                    "evaluation_type": evaluation.evaluation_type,
                    "accuracy": evaluation.accuracy,
                    "accuracy_floor": evaluation.accuracy_floor,
                    "total_cases": evaluation.total_cases,
                    "passed_cases": evaluation.passed_cases,
                    "passed": evaluation.passed,
                    "results": evaluation.results,
                },
                sort_keys=True,
            ),
            created_at=datetime.now(timezone.utc),
        )

        try:
            created = self.repository.add(record)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return self._to_domain(created)

    @staticmethod
    def _to_domain(
        evaluation: Evaluation,
    ) -> EvaluationData:
        details = json.loads(evaluation.details)

        return EvaluationData(
            evaluation_id=evaluation.evaluation_id,
            run_id=evaluation.run_id,
            evaluation_type=details.get(
                "evaluation_type",
                evaluation.metric,
            ),
            accuracy=details.get(
                "accuracy",
                evaluation.score,
            ),
            accuracy_floor=details.get(
                "accuracy_floor",
                0.0,
            ),
            total_cases=details.get(
                "total_cases",
                0,
            ),
            passed_cases=details.get(
                "passed_cases",
                0,
            ),
            passed=evaluation.passed,
            results=details.get(
                "results",
                [],
            ),
            created_at=evaluation.created_at,
        )