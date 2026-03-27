from pydantic import BaseModel, Field


class RoleIntentResult(BaseModel):
    goal_parse: dict = Field(default_factory=dict)
    role_intent: dict = Field(default_factory=dict)


class ResearchResult(BaseModel):
    evidence_records: list[dict] = Field(default_factory=list)
    source_summary: dict = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    evidence_summary: dict = Field(default_factory=dict)


class PlanningResult(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    validation_result: dict = Field(default_factory=dict)
    draft_requirements: dict = Field(default_factory=dict)
    rationale: str = ""
    llm_plan: dict = Field(default_factory=dict)


class VerificationResult(BaseModel):
    passed: bool = False
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentRunTrace(BaseModel):
    role_intent: dict = Field(default_factory=dict)
    research: dict = Field(default_factory=dict)
    extraction: dict = Field(default_factory=dict)
    planning: dict = Field(default_factory=dict)
    verification: dict = Field(default_factory=dict)
