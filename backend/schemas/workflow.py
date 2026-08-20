from typing import Literal

from pydantic import BaseModel, Field, field_validator


WorkflowAction = Literal["dispatch", "submit_result", "return_for_rework", "approve_close"]


class WorkflowActionRequest(BaseModel):
    action: WorkflowAction
    responsible_unit: str | None = Field(default=None, max_length=40)
    collaborator_units: list[str] = Field(default_factory=list, max_length=8)
    evidence_complete: bool | None = None
    note: str | None = Field(default=None, max_length=300)
    operator_role: str = Field(default="基层治理协同智能体（人工确认）", min_length=1, max_length=50)

    @field_validator("responsible_unit", "note", mode="before")
    @classmethod
    def trim_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("collaborator_units")
    @classmethod
    def normalize_collaborators(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))
