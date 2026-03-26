from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.auth.domain.entity import CurrentUser
from app.classroom.adapter.input.api.v1.request import (
    CreateClassroomRequest,
    InviteClassroomStudentsRequest,
    UpdateClassroomRequest,
)
from app.classroom.adapter.input.api.v1.response import (
    ClassroomListResponse,
    ClassroomPayload,
    ClassroomResponse,
)
from app.classroom.container import ClassroomContainer
from app.classroom.domain.command import (
    CreateClassroomCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
)
from app.classroom.domain.usecase import ClassroomUseCase
from core.fastapi.dependencies import (
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


@router.post(
    "",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def create_classroom(
    request: CreateClassroomRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.create_classroom(
        current_user=current_user,
        command=CreateClassroomCommand(
            organization_id=current_user.organization_id,
            name=request.name,
            professor_ids=request.professor_ids,
            grade=request.grade,
            semester=request.semester,
            section=request.section,
            description=request.description,
            student_ids=request.student_ids,
            allow_student_material_access=request.allow_student_material_access,
        ),
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )


@router.get(
    "",
    response_model=ClassroomListResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def list_classrooms(
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classrooms = await usecase.list_classrooms(current_user=current_user)
    return ClassroomListResponse(
        data=[
            ClassroomPayload(
                id=str(classroom.id),
                name=classroom.name,
                professor_ids=[
                    str(user_id) for user_id in classroom.professor_ids
                ],
                grade=classroom.grade,
                semester=classroom.semester,
                section=classroom.section,
                description=classroom.description,
                student_ids=[str(user_id) for user_id in classroom.student_ids],
                allow_student_material_access=(
                    classroom.allow_student_material_access
                ),
            )
            for classroom in classrooms
        ]
    )


@router.get(
    "/{classroom_id}",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def get_classroom(
    classroom_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.get_classroom(
        classroom_id=classroom_id,
        current_user=current_user,
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )


@router.patch(
    "/{classroom_id}",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def update_classroom(
    classroom_id: UUID,
    request: UpdateClassroomRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.update_classroom(
        classroom_id=classroom_id,
        current_user=current_user,
        command=UpdateClassroomCommand(
            **request.model_dump(exclude_unset=True)
        ),
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )


@router.post(
    "/{classroom_id}/students",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def invite_classroom_students(
    classroom_id: UUID,
    request: InviteClassroomStudentsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.invite_classroom_students(
        classroom_id=classroom_id,
        current_user=current_user,
        command=InviteClassroomStudentsCommand(student_ids=request.student_ids),
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )


@router.delete(
    "/{classroom_id}/students/{student_id}",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def remove_classroom_student(
    classroom_id: UUID,
    student_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.remove_classroom_student(
        classroom_id=classroom_id,
        current_user=current_user,
        command=RemoveClassroomStudentCommand(student_id=student_id),
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )


@router.delete(
    "/{classroom_id}",
    response_model=ClassroomResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def delete_classroom(
    classroom_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    classroom = await usecase.delete_classroom(
        classroom_id=classroom_id,
        current_user=current_user,
    )
    return ClassroomResponse(
        data=ClassroomPayload(
            id=str(classroom.id),
            name=classroom.name,
            professor_ids=[str(user_id) for user_id in classroom.professor_ids],
            grade=classroom.grade,
            semester=classroom.semester,
            section=classroom.section,
            description=classroom.description,
            student_ids=[str(user_id) for user_id in classroom.student_ids],
            allow_student_material_access=(
                classroom.allow_student_material_access
            ),
        )
    )
