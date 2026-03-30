from pydantic import BaseModel, Field
from typing import List

class ClassInfoDTO(BaseModel):
    name: str = Field(..., description="강의명 (예: 지능시스템 캡스톤디자인)")
    grade: str = Field(..., description="대상 학년")
    term: str = Field(..., description="학기")

class ExamQuestionDTO(BaseModel):
    question: str = Field(..., description="생성된 평가 문제 (구어체 형태)")
    criteria: str = Field(..., description="해당 문제의 평가 기준")
    scope: str = Field(..., description="출제 범위")
    follow_up_questions: List[str] = Field(
        default_factory=list, 
        description="학생의 오답이나 모호한 답변 시 사용할 예상 꼬리 질문 리스트"
    )

class ExamGenerationResponse(BaseModel):
    class_info: ClassInfoDTO = Field(..., alias="class", description="강의실 정보") 
    questions: List[ExamQuestionDTO] = Field(..., description="AI가 생성한 문제 목록")