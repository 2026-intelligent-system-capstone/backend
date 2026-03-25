from pydantic import BaseModel, Field


class CreateClassroomMaterialCommand(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    week: int = Field(..., ge=1, le=16)
    description: str | None = Field(None, max_length=1000)


class UpdateClassroomMaterialCommand(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    week: int | None = Field(None, ge=1, le=16)
    description: str | None = Field(None, max_length=1000)
