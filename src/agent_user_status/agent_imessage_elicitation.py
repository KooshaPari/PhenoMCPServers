"""Structured elicitation schemas for agent-to-user prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

QuestionKind = Literal["single_answer", "multi_answer"]
SchemaKind = Literal["single_question", "multi_question"]

ANSWER_ID_RE = re.compile(r"\bA(?P<number>\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AnswerOption:
    """One stable answer choice in an elicitation prompt."""

    id: str
    label: str
    description: str = ""

    @classmethod
    def create(cls, index: int, label: str, description: str = "") -> AnswerOption:
        if index < 1:
            raise ValueError("Answer option index must be positive")
        return cls(id=f"A{index}", label=label.strip(), description=description.strip())

    def to_dict(self) -> dict[str, str]:
        payload = {"id": self.id, "label": self.label}
        if self.description:
            payload["description"] = self.description
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any], index: int) -> AnswerOption:
        option_id = str(payload.get("id") or f"A{index}").upper()
        if not ANSWER_ID_RE.fullmatch(option_id):
            raise ValueError(f"Invalid answer option id: {option_id}")
        label = str(payload.get("label") or "").strip()
        if not label:
            raise ValueError(f"Answer option {option_id} requires a label")
        return cls(id=option_id, label=label, description=str(payload.get("description") or "").strip())


@dataclass(frozen=True)
class ElicitationQuestion:
    """One user-facing question with stable answer IDs."""

    id: str
    prompt: str
    kind: QuestionKind = "single_answer"
    options: list[AnswerOption] = field(default_factory=list)
    default_answer_ids: list[str] = field(default_factory=list)
    allow_freeform: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"single_answer", "multi_answer"}:
            raise ValueError(f"Unsupported question kind: {self.kind}")
        if not self.id.strip():
            raise ValueError("Question id is required")
        if not self.prompt.strip():
            raise ValueError("Question prompt is required")
        if not self.options:
            raise ValueError("At least one answer option is required")
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("Answer option IDs must be unique")
        unknown_defaults = set(self.default_answer_ids) - set(ids)
        if unknown_defaults:
            raise ValueError(f"Default answer IDs are not valid options: {sorted(unknown_defaults)}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "prompt": self.prompt,
            "kind": self.kind,
            "options": [option.to_dict() for option in self.options],
            "allow_freeform": self.allow_freeform,
        }
        if self.default_answer_ids:
            payload["default_answer_ids"] = self.default_answer_ids
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any], index: int = 1) -> ElicitationQuestion:
        options_payload = payload.get("options") or []
        if not isinstance(options_payload, list):
            raise ValueError("Question options must be a list")
        options = [
            AnswerOption.from_dict(option, option_index)
            for option_index, option in enumerate(options_payload, start=1)
            if isinstance(option, dict)
        ]
        return cls(
            id=str(payload.get("id") or f"Q{index}"),
            prompt=str(payload.get("prompt") or payload.get("question") or ""),
            kind=str(payload.get("kind") or "single_answer"),  # type: ignore[arg-type]
            options=options,
            default_answer_ids=[str(value).upper() for value in payload.get("default_answer_ids", [])],
            allow_freeform=bool(payload.get("allow_freeform", False)),
        )

    def render(self) -> str:
        lines = [f"{self.id}. {self.prompt}"]
        for option in self.options:
            detail = f" - {option.description}" if option.description else ""
            lines.append(f"{option.id}: {option.label}{detail}")
        if self.kind == "multi_answer":
            lines.append("Reply with one or more option IDs, for example: A1, A3.")
        else:
            lines.append("Reply with one option ID, for example: A1.")
        if self.allow_freeform:
            lines.append("Freeform detail is allowed after the option ID.")
        return "\n".join(lines)


@dataclass(frozen=True)
class ElicitationSchema:
    """Machine-readable prompt shape for one or more questions."""

    kind: SchemaKind
    questions: list[ElicitationQuestion]

    def __post_init__(self) -> None:
        if self.kind not in {"single_question", "multi_question"}:
            raise ValueError(f"Unsupported elicitation schema kind: {self.kind}")
        if not self.questions:
            raise ValueError("At least one question is required")
        if self.kind == "single_question" and len(self.questions) != 1:
            raise ValueError("single_question schemas must contain exactly one question")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "questions": [question.to_dict() for question in self.questions]}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ElicitationSchema:
        questions_payload = payload.get("questions")
        if questions_payload is None and ("prompt" in payload or "question" in payload):
            questions_payload = [payload]
        if not isinstance(questions_payload, list):
            raise ValueError("Elicitation schema requires a questions list")
        questions = [
            ElicitationQuestion.from_dict(question, index)
            for index, question in enumerate(questions_payload, start=1)
            if isinstance(question, dict)
        ]
        kind = str(payload.get("kind") or ("single_question" if len(questions) == 1 else "multi_question"))
        return cls(kind=kind, questions=questions)  # type: ignore[arg-type]

    def render(self) -> str:
        return "\n\n".join(question.render() for question in self.questions)


@dataclass(frozen=True)
class ParsedElicitationReply:
    selected_answer_ids: list[str]
    freeform_text: str
    confidence: float
    ambiguous: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_answer_ids": self.selected_answer_ids,
            "freeform_text": self.freeform_text,
            "confidence": self.confidence,
            "ambiguous": self.ambiguous,
            "notes": self.notes,
        }


def parse_reply(text: str, schema: ElicitationSchema) -> ParsedElicitationReply:
    """Parse a short user reply such as ``A1, A3`` against a schema."""

    allowed = {option.id for question in schema.questions for option in question.options}
    selected: list[str] = []
    notes: list[str] = []
    for match in ANSWER_ID_RE.finditer(text):
        option_id = f"A{int(match.group('number'))}"
        if option_id in allowed and option_id not in selected:
            selected.append(option_id)
        elif option_id not in allowed:
            notes.append(f"Unknown option ignored: {option_id}")

    freeform = ANSWER_ID_RE.sub("", text).strip(" ,;:-\n\t")
    multi_allowed = any(question.kind == "multi_answer" for question in schema.questions)
    ambiguous = False
    if not selected:
        ambiguous = True
        notes.append("No known answer ID found")
    if len(selected) > 1 and not multi_allowed:
        ambiguous = True
        notes.append("Multiple answer IDs provided for a single-answer question")

    confidence = 0.95 if selected and not ambiguous else 0.45 if selected else 0.1
    return ParsedElicitationReply(
        selected_answer_ids=selected,
        freeform_text=freeform,
        confidence=confidence,
        ambiguous=ambiguous,
        notes=notes,
    )
