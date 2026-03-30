from pydantic import BaseModel, Field

class EvaluationRequest(BaseModel):
    session_id: str = Field(..., description="대화 세션 ID (학생별 구분)")
    question_id: int = Field(..., description="현재 답변 중인 문제 번호")
    student_answer: str = Field(..., description="학생의 주관식 답변")
    context_subject: str = Field(..., description="검색할 과목명")