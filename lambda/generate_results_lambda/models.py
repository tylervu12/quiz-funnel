from pydantic import BaseModel, field_validator
from typing import Union, List

class QuizInput(BaseModel):
    primary_goal: str
    tech_skill: Union[str, List[str]]
    tools: str
    budget: Union[str, List[str]]

    @field_validator('tech_skill', 'budget', mode='before')
    @classmethod
    def convert_list_to_string(cls, v):
        if isinstance(v, list):
            return ", ".join(v)
        return v

class AIStackOutput(BaseModel):
    ai_stack_summary: str

class B2BAssessment(BaseModel):
    b2b_qualified: bool

class RelevanceAssessmentOutput(BaseModel):
    is_relevant: bool
    reasoning: str
