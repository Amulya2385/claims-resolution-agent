"""M8 · Staged deployment. Promotion requires a linked, passing
evaluation-gate run — refused without one, naming the unmet gate.
Demotion on a harness failure is automatic; no human approves a
demotion, the same way no human is needed to notice a fire alarm
before leaving the building.
"""
import time

STAGES = ["canary", "staged", "production"]


class Deployment:
    def __init__(self):
        self.stage_index = 0
        self.history = []

    @property
    def stage(self) -> str:
        return STAGES[self.stage_index]

    def attempt_promotion(self, evidence: dict | None) -> dict:
        if self.stage_index >= len(STAGES) - 1:
            return {"ok": False, "reason": "already at the highest stage"}

        if evidence is None:
            return {"ok": False, "reason": "no evidence run linked — promotion refused"}
        if not evidence.get("passed"):
            return {"ok": False, "reason": f"linked evidence run did not pass "
                     f"(accuracy {evidence.get('layer2', {}).get('accuracy')}, "
                     f"floor {evidence.get('accuracy_floor')})"}

        from_stage = self.stage
        self.stage_index += 1
        self.history.append({"event": "promoted", "from": from_stage, "to": self.stage,
                               "evidence_accuracy": evidence["layer2"]["accuracy"],
                               "at": time.time(), "approved_by": "evidence, no human sign-off required"})
        return {"ok": True, "from": from_stage, "to": self.stage}

    def demote_on_failure(self, evidence: dict) -> dict:
        """Called with a fresh, failing evaluation run. No human is
        asked; the demotion is unconditional and immediate."""
        if evidence.get("passed"):
            return {"ok": False, "reason": "evidence passed — nothing to demote for"}
        if self.stage_index == 0:
            return {"ok": False, "reason": "already at the lowest stage"}

        from_stage = self.stage
        self.stage_index -= 1
        self.history.append({"event": "demoted", "from": from_stage, "to": self.stage,
                               "evidence_accuracy": evidence["layer2"]["accuracy"],
                               "at": time.time(), "approved_by": None})
        return {"ok": True, "from": from_stage, "to": self.stage}
