from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Exam:
    id: Optional[int]
    subject: str
    scope: str
    total_questions: int
    difficulty: str
    created_at: datetime = field(default_factory=datetime.now)
    # 여기에 생성된 문제 리스트(Question 엔티티 등)가 연결될 수 있습니다.