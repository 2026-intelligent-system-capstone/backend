from sqlalchemy import BigInteger, Column, DateTime, MetaData, Table, func

metadata = MetaData()


class BaseTable(Table):
    def __init__(self, name: str, metadata_obj: MetaData = metadata, *args, **kwargs):
        column_names = {col.name for col in args if isinstance(col, Column)}

        extra_columns = []
        if "created_at" not in column_names:
            extra_columns.append(Column("created_at", DateTime, nullable=False, default=func.now()))
        if "updated_at" not in column_names:
            extra_columns.append(
                Column("updated_at", DateTime, nullable=False, default=func.now(), onupdate=func.now())
            )
        if "version_id" not in column_names:
            extra_columns.append(Column("version_id", BigInteger, nullable=False, default=0))

        super().__init__(name, metadata_obj, *(args + tuple(extra_columns)), **kwargs)
