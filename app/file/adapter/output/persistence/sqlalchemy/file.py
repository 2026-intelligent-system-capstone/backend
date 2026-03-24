from uuid import UUID

from sqlalchemy import select

from app.file.domain.entity.file import File, FileStatus
from app.file.domain.repository.file import FileRepository
from core.db.session import session
from core.db.sqlalchemy.models.file import file_table


class FileSQLAlchemyRepository(FileRepository):
    async def save(self, file: File) -> File:
        return await session.merge(file)

    async def get_by_id(self, file_id: UUID) -> File | None:
        query = select(File).where(
            file_table.c.id == file_id,
            file_table.c.status != FileStatus.DELETED,
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> list[File]:
        query = select(File).where(file_table.c.status != FileStatus.DELETED)
        result = await session.execute(query)
        return list(result.scalars().all())
