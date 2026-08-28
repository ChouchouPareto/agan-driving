from dataclasses import dataclass
from typing import Literal


SkillAction = Literal["ANSWER", "NAVIGATE", "RESPOND"]


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    intents: tuple[str, ...]
    action: SkillAction
    required_context: tuple[str, ...]
    tools: tuple[str, ...]
    completion: str
    fallback: str


@dataclass(frozen=True)
class SkillDecision:
    spec: SkillSpec
    action: SkillAction
    destination: str | None = None
    assistant_message: str | None = None
