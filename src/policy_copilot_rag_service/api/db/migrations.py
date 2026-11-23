"""Additive startup upgrades for schemas created before library support.

There is no migration framework configured in this project. Keep this upgrade
idempotent and preserve existing tables, document IDs, content, and categories.
"""

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def upgrade_schema(connection: Connection) -> None:
    """Add the indexed document-library foreign key after ``create_all``."""
    dialect = connection.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise NotImplementedError(f"Schema upgrades are not supported for {dialect}")

    inspector = inspect(connection)
    library_columns = {column["name"] for column in inspector.get_columns("libraries")}
    if "system_key" not in library_columns:
        if_not_exists = "IF NOT EXISTS " if dialect == "postgresql" else ""
        connection.exec_driver_sql(
            f"ALTER TABLE libraries ADD COLUMN {if_not_exists}system_key VARCHAR(50)"
        )
    # NULL is distinct in both supported databases, so user libraries may all
    # omit this key while concurrent bootstraps cannot create two system rows.
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_libraries_system_key ON libraries (system_key)"
    )

    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "library_id" not in columns:
        if_not_exists = "IF NOT EXISTS " if dialect == "postgresql" else ""
        connection.exec_driver_sql(
            f"ALTER TABLE documents ADD COLUMN {if_not_exists}library_id INTEGER "
            "CONSTRAINT fk_documents_library_id_libraries "
            "REFERENCES libraries (id) ON DELETE SET NULL"
        )

    # SQLite reflection can omit ON DELETE for inline constraints added with
    # ALTER TABLE. Its PRAGMA reports the actual enforced constraint instead.
    # PostgreSQL can also finish a partial upgrade that only added the column.
    if dialect == "sqlite":
        foreign_keys = [
            {
                "constrained_columns": [foreign_key["from"]],
                "referred_table": foreign_key["table"],
                "referred_columns": [foreign_key["to"]],
                "options": {"ondelete": foreign_key["on_delete"]},
            }
            for foreign_key in connection.exec_driver_sql(
                "PRAGMA foreign_key_list(documents)"
            ).mappings()
        ]
    else:
        foreign_keys = inspect(connection).get_foreign_keys("documents")
    library_foreign_keys = [
        foreign_key
        for foreign_key in foreign_keys
        if foreign_key["constrained_columns"] == ["library_id"]
    ]
    if not library_foreign_keys:
        if dialect == "sqlite":
            raise RuntimeError(
                "documents.library_id exists without its library foreign key; "
                "SQLite cannot add that constraint without rebuilding the table. "
                "No existing tables or data were changed by this upgrade."
            )
        connection.exec_driver_sql(
            "ALTER TABLE documents ADD CONSTRAINT fk_documents_library_id_libraries "
            "FOREIGN KEY (library_id) REFERENCES libraries (id) ON DELETE SET NULL"
        )
    elif not any(
        foreign_key["referred_table"] == "libraries"
        and foreign_key["referred_columns"] == ["id"]
        and (foreign_key.get("options", {}).get("ondelete") or "").upper() == "SET NULL"
        for foreign_key in library_foreign_keys
    ):
        raise RuntimeError(
            "documents.library_id has an incompatible foreign key; "
            "expected REFERENCES libraries(id) ON DELETE SET NULL"
        )

    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_documents_library_id ON documents (library_id)"
    )
