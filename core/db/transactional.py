from functools import wraps
from core.db.session import session

def transactional(func):
    @wraps(func)
    async def _transactional(*args, **kwargs):
        if session.in_transaction():
            return await func(*args, **kwargs)

        async with session() as db_session:
            async with db_session.begin():
                try:
                    result = await func(*args, **kwargs)
                    await db_session.commit()
                    return result
                except Exception as e:
                    await db_session.rollback()
                    raise e
                finally:
                    await db_session.close()

    return _transactional
