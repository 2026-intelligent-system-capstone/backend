from pydantic import BaseModel, Field
from typing import Optional, List

class EvaluationResultResponse(BaseModel):
    status: str = Field(..., description="평가 상태 (PASS: 통과, FOLLOW_UP: 꼬리질문 필요, FAIL: 오답)")
    feedback: str = Field(..., description="학생 답변에 대한 AI의 상세 피드백")
    score: int = Field(default=0, description="해당 답변에 대한 점수 (0~100)")
    follow_up_question: Optional[str] = Field(None, description="상태가 FOLLOW_UP일 때 제공되는 꼬리 질문")
    suggested_keywords: List[str] = Field(default_factory=list, description="학습이 더 필요한 키워드 추천")