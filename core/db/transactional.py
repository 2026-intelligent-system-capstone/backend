from functools import wraps

import stamina
from sqlalchemy.orm.exc import StaleDataError

from core.db.session import session


def transactional(func):
    @wraps(func)
    async def _transactional(*args, **kwargs):
        # NOTE: async_scoped_session does not expose in_transaction(); treat this decorator
        # as the outer transaction boundary.

        @stamina.retry(
            on=StaleDataError,
            attempts=3,
            wait_initial=0.1,
        )
        async def _execute_with_retry():
            async with session() as db_session:
                try:
                    result = await func(*args, **kwargs)
                    await db_session.commit()
                    return result
                except Exception as e:
                    await db_session.rollback()
                    raise e
                finally:
                    await db_session.close()

        return await _execute_with_retry()

    return _transactional
