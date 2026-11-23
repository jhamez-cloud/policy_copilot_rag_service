from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Library(Base):
    __tablename__ = "libraries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Nullable unique identity leaves ordinary user libraries unrestricted.
    system_key: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # No delete cascade: removing a library preserves its documents and sessions.
    documents: Mapped[list[Document]] = relationship(back_populates="library")
    sessions: Mapped[list[ChatSession]] = relationship(back_populates="library")

    @property
    def is_system(self) -> bool:
        return self.system_key is not None


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), index=True, default="general")
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    source: Mapped[str] = mapped_column(String(20), default="upload")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    library_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "libraries.id", name="fk_documents_library_id_libraries", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )
    library: Mapped[Library | None] = relationship(back_populates="documents")


class ChatSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    library_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "libraries.id", name="fk_sessions_library_id_libraries", ondelete="SET NULL"
        ),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    library: Mapped[Library | None] = relationship(back_populates="sessions")

