"""
LittleX backend, Postgresql Implementation
Database abstracted in the language runtime research
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

import jwt
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer

from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel


# --- Auth ---


JWT_SECRET = os.environ.get("JWT_SECRET", "supersecretkey_for_testing_only!")
JWT_ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["user_id"])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


# --- SETUP ---


SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    bio TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id BIGINT NOT NULL REFERENCES profiles(id),
    followee_id BIGINT NOT NULL REFERENCES profiles(id),
    PRIMARY KEY (follower_id, followee_id)
);
CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee_id);

CREATE TABLE IF NOT EXISTS tweets (
    id BIGSERIAL PRIMARY KEY,
    seed_id TEXT NOT NULL,
    author_id BIGINT NOT NULL REFERENCES profiles(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    likes TEXT[] NOT NULL DEFAULT '{}',
    comments JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_tweets_author_created
    ON tweets(author_id, created_at DESC);
"""

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres@localhost:5433/littleX"
)

pool = AsyncConnectionPool(
    DATABASE_URL, min_size=5, max_size=15, kwargs={"autocommit": True}, open=False
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await pool.open()
    async with pool.connection() as conn:
        await conn.execute(SCHEMA)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


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


PROFILE_SQL = "SELECT id, username, bio, created_at FROM profiles WHERE id  = %s"


FOLLOWERS_SQL = """
SELECT p.id, p.username, p.bio
FROM follows f JOIN profiles p on p.id = f.follower_id
WHERE f.followee_id = %s
"""


FOLLOWING_SQL = """
SELECT p.id, p.username, p.bio
FROM follows f JOIN profiles p ON p.id = f.followee_id
WHERE f.follower_id = %s
"""


OWN_TWEETS_SQL = """
SELECT t.id, t.seed_id, t.content, p.username, t.created_at, t.likes, t.comments
FROM tweets t JOIN profiles p ON p.id = t.author_id
WHERE t.author_id = %s 
ORDER BY t.created_at DESC
"""


async def _build_profile_view(
    conn, target_id: int, viewer_id: int | None
) -> ProfileRead:
    cur = await conn.execute(PROFILE_SQL, (target_id,))
    prow = await cur.fetchone()
    if prow is None:
        raise HTTPException(status_code=404, detail="profile not found")
    pid, username, bio, created_at = prow

    cur = await conn.execute(FOLLOWERS_SQL, (target_id,))
    followers = [
        UserSummary(id=r[0], username=r[1], bio=r[2]) for r in await cur.fetchall()
    ]

    cur = await conn.execute(FOLLOWING_SQL, (target_id,))
    following = [
        UserSummary(id=r[0], username=r[1], bio=r[2]) for r in await cur.fetchall()
    ]

    is_mine = viewer_id == target_id

    cur = await conn.execute(OWN_TWEETS_SQL, (target_id,))
    tweets = [
        TweetRead(
            id=r[0],
            seed_id=r[1],
            author_id=target_id,
            author_username=username,
            content=r[2],
            created_at=r[4],
            likes=r[5],
            comments=r[6],
            is_mine=is_mine,
        )
        for r in await cur.fetchall()
    ]

    return ProfileRead(
        id=pid,
        username=username,
        bio=bio,
        created_at=created_at,
        followers=followers,
        following=following,
        tweets=tweets,
    )


@app.get("/profile", response_model=ProfileRead)
async def get_profile(user_id: int = Depends(get_current_user_id)):
    async with pool.connection() as conn:
        return await _build_profile_view(conn, target_id=user_id, viewer_id=user_id)


@app.get("/profile/{target_id}", response_model=ProfileRead)
async def get_profile_by_id(
    target_id: int, user_id: int = Depends(get_current_user_id)
):
    async with pool.connection() as conn:
        return await _build_profile_view(conn, target_id=target_id, viewer_id=user_id)


# --- Accumulator Endpoints ---


FEED_SQL = """
SELECT t.id, t.seed_id, t.author_id, t.content, p.username, t.created_at, t.likes, t.comments
FROM tweets t
JOIN profiles p ON p.id = t.author_id 
WHERE t.author_id = %(me)s 
    OR t.author_id IN (SELECT followee_id FROM follows WHERE follower_id = %(me)s)
ORDER BY t.created_at DESC
"""


@app.get("/feed", response_model=list[TweetRead])
async def get_feed(user_id: int = Depends(get_current_user_id)):
    async with pool.connection() as conn:
        cur = await conn.execute(FEED_SQL, {"me": user_id})
        rows = await cur.fetchall()

    return [
        TweetRead(
            id=r[0],
            seed_id=r[1],
            author_id=r[2],
            content=r[3],
            author_username=r[4],
            created_at=r[5],
            likes=r[6],
            comments=r[7],
            is_mine=(r[2] == user_id),
        )
        for r in rows
    ]


# --- Create Endpoints ---


@app.post("/tweet", response_model=TweetRead)
async def create_tweet(body: TweetCreate, user_id: int = Depends(get_current_user_id)):
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT username FROM profiles WHERE id = %s", (user_id,)
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="profile not found")
        username = row[0]

        cur = await conn.execute(
            """
            INSERT INTO tweets (seed_id, author_id, content)
            VALUES (%s, %s, %s)
            RETURNING id, created_at
            """,
            (body.seed_id, user_id, body.content),
        )
        result = await cur.fetchone()
        assert result is not None
        tid, created_at = result

    return TweetRead(
        id=tid,
        seed_id=body.seed_id,
        author_id=user_id,
        author_username=username,
        content=body.content,
        created_at=created_at,
        likes=[],
        comments=[],
        is_mine=True,
    )
