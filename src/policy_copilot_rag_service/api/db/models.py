from datetime import datetime
from sqlalchemy import Integer,String,Text,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column,DeclarativeBase


class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[Integer] = mapped_column(primary_key=True)
    title: Mapped[String] = mapped_column(String(255))
    category: Mapped[String] = mapped_column(String(50),index=True,default="general")
    filename: Mapped[String] = mapped_column(String(255))
    content: Mapped[Text] = mapped_column(Text)
    content_hash: Mapped[String] = mapped_column(String(64),unique=True)
    source: Mapped[String] = mapped_column(String(20),default="upload")
    chunk_count: Mapped[Integer] =  mapped_column(Integer,default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())

