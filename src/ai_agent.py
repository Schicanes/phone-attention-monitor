"""Replaceable structured-observation policy. No images enter this interface."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    message: str
    repetitions: int = 1


class RuleBasedAgent:
    def observe(self, context):
        return dict(context)

    def decide(self, context):
        count = context["warnings"] + 1
        slow = (context.get("average_response_to_voice") or 0) > 15
        return Decision("Phone break is over. Back to work." if count == 1 else
                        f"That is distraction number {count} this session. Please return to your task.",
                        3 if count >= 3 or slow else 1)

    def act(self, decision, tools):
        tools(decision)

    def observe_outcome(self, response_seconds):
        return {"response_seconds": response_seconds}
