from config import *
from typing import List
from sqlalchemy.engine import URL
from sqlalchemy.orm import Mapped
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine


url = URL.create(
    "postgresql+asyncpg",
    host = "ep-soft-cherry-a21b0b8v.eu-central-1.aws.neon.tech",
    database = "livequeue",
    port = "5432",
    username = "livequeue_owner",
    password = "NZmtvFxRc4C2"
)

engine = create_async_engine(url)

session = sessionmaker(
    engine, class_ = AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id : Mapped[int] = mapped_column(primary_key=True)
    role : Mapped[int] = mapped_column(default=0) # 0 - взаимодействовать нельзя, 1 - можно выполнять задачи, 2 - можно выполнять и создавать, 3 - одобрять задачи и выдавать роли, 4 - суперпользователь 
    name : Mapped[str]

class Queue(Base):
    __tablename__ = 'queues'
    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name : Mapped[str]
    tasks : Mapped[List["Task"]] = relationship(back_populates="queue", lazy="selectin")

class Task(Base):
    __tablename__ = 'tasks'
    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title : Mapped[str]
    text : Mapped[str]

    statuscode : Mapped[int] = mapped_column(default = 0) #0 - ожидает проверки, 1 - не выполнена, 2 - в работе, 3 - выполнена
    timestamp_start : Mapped[int]
    timestamp_end : Mapped[int] = mapped_column(nullable = True)

    started : Mapped[int] = mapped_column(ForeignKey('users.id'))

    ended : Mapped[int] = mapped_column(ForeignKey('users.id'), nullable = True)
   
    queueID : Mapped[int] = mapped_column(ForeignKey('queues.id'))
    queue : Mapped[Queue] = relationship(back_populates = "tasks")

class Invite(Base):
    __tablename__ = "invites"
    id : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text : Mapped[str] = mapped_column(unique=True)
    author : Mapped[int] = mapped_column(ForeignKey('users.id'))

