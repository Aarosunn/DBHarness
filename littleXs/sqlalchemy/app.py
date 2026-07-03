"""
LittleX backend, Sqlalchemy Implementation
Database abstracted in the language runtime research
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import ForeignKey, Index, Text, select, or_
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
    joinedload,
)
from sqlalchemy.sql import func

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# --- SETUP ---


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/littleX"
)

engine = create_async_engine(DATABASE_URL)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tweets: Mapped[list["Tweet"]] = relationship(
        back_populates="author", order_by="Tweet.created_at.desc()"
    )
    following: Mapped[list["Profile"]] = relationship(
        secondary="follows",
        primaryjoin="Profile.id == Follow.follower_id",
        secondaryjoin="Profile.id == Follow.followee_id",
        back_populates="followers",
    )
    followers: Mapped[list["Profile"]] = relationship(
        secondary="follows",
        primaryjoin="Profile.id == Follow.followee_id",
        secondaryjoin="Profile.id == Follow.follower_id",
        back_populates="following",
    )


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (Index("idx_follows_followee", "followee_id"),)

    follower_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id"), primary_key=True
    )
    followee_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id"), primary_key=True
    )


class Tweet(Base):
    __tablename__ = "tweets"
    __table_args__ = (Index("idx_tweets_author_created", "author_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seed_id: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    likes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    comments: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    author: Mapped["Profile"] = relationship(back_populates="tweets")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


# --- Models ---


class UserSummary(BaseModel):
    id: int
    username: str
    bio: str = ""


class TweetRead(BaseModel):
    id: int
    seed_id: str
    author_id: int
    author_username: str
    content: str
    created_at: datetime
    likes: list[str] = []
    comments: list[dict[str, str]] = []

    is_mine: bool = False


class TweetCreate(BaseModel):
    content: str
    seed_id: str


class ProfileRead(BaseModel):
    id: int
    username: str
    bio: str
    created_at: datetime
    followers: list[UserSummary]
    following: list[UserSummary]
    tweets: list[TweetRead]


# --- Profile Endpoints ---


async def _build_profile_view(
    session: AsyncSession, target_id: int, viewer_id: int
) -> ProfileRead:
    stmt = (
        select(Profile)
        .where(Profile.id == target_id)
        .options(
            selectinload(Profile.followers),
            selectinload(Profile.following),
            selectinload(Profile.tweets),
        )
    )

    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")

    return ProfileRead(
        id=profile.id,
        username=profile.username,
        bio=profile.bio,
        created_at=profile.created_at,
        followers=[
            UserSummary(id=p.id, username=p.username, bio=p.bio)
            for p in profile.followers
        ],
        following=[
            UserSummary(id=p.id, username=p.username, bio=p.bio)
            for p in profile.following
        ],
        tweets=[
            TweetRead(
                id=t.id,
                seed_id=t.seed_id,
                author_id=t.author_id,
                author_username=profile.username,
                content=t.content,
                created_at=t.created_at,
                likes=t.likes,
                comments=t.comments,
                is_mine=(viewer_id == target_id),
            )
            for t in profile.tweets
        ],
    )


@app.get("/profile", response_model=ProfileRead)
async def get_profile(user_id: int, session: AsyncSession = Depends(get_session)):
    return await _build_profile_view(session, target_id=user_id, viewer_id=user_id)


@app.get("/profile/{target_id}", response_model=ProfileRead)
async def get_profile_by_id(
    target_id: int, user_id: int, session: AsyncSession = Depends(get_session)
):
    return await _build_profile_view(session, target_id=target_id, viewer_id=user_id)


# --- Accumulator Endpoints ---


@app.get("/feed", response_model=list[TweetRead])
async def get_feed(user_id: int, session: AsyncSession = Depends(get_session)):
    following_ids = (
        select(Follow.followee_id)
        .where(Follow.follower_id == user_id)
        .scalar_subquery()
    )

    stmt = (
        select(Tweet)
        .where(or_(Tweet.author_id == user_id, Tweet.author_id.in_(following_ids)))
        .options(joinedload(Tweet.author))
        .order_by(Tweet.created_at.desc())
    )

    result = await session.execute(stmt)
    tweets = result.scalars().all()

    return [
        TweetRead(
            id=t.id,
            seed_id=t.seed_id,
            author_id=t.author_id,
            author_username=t.author.username,
            content=t.content,
            created_at=t.created_at,
            likes=t.likes,
            comments=t.comments,
            is_mine=(t.author_id == user_id),
        )
        for t in tweets
    ]


# --- Create Endpoints ---


@app.post("/tweet", response_model=TweetRead)
async def create_tweet(
    user_id: int, body: TweetCreate, session: AsyncSession = Depends(get_session)
):
    author = await session.get(Profile, user_id)
    if author is None:
        raise HTTPException(status_code=404, detail="profile not found")

    tweet = Tweet(seed_id=body.seed_id, author_id=user_id, content=body.content)
    session.add(tweet)
    await session.commit()
    await session.refresh(tweet)

    return TweetRead(
        id=tweet.id,
        seed_id=tweet.seed_id,
        author_id=tweet.author_id,
        author_username=author.username,
        content=tweet.content,
        created_at=tweet.created_at,
        likes=tweet.likes,
        comments=tweet.comments,
        is_mine=True,
    )
