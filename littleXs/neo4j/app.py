"""
LittleX backend, Neo4j Implementation
Database abstracted in the language runtime research
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

import jwt
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from neo4j import AsyncGraphDatabase
from pydantic import BaseModel
from typing import LiteralString


# --- Auth ---


JWT_SECRET = os.environ.get("JWT_SECRET", "supersecretkey_for_testing_only!")
JWT_ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return str(payload["user_id"])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


# --- SETUP ---


NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "littleXpassword")

driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

CONSTRAINTS: list[LiteralString] = [
    "CREATE CONSTRAINT profile_id_unique IF NOT EXISTS FOR (p:Profile) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT profile_username_unique IF NOT EXISTS FOR (p:Profile) REQUIRE p.username IS UNIQUE",
    "CREATE CONSTRAINT tweet_id_unique IF NOT EXISTS FOR (t:Tweet) REQUIRE t.id IS UNIQUE",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await driver.verify_connectivity()
    async with driver.session() as session:
        for stmt in CONSTRAINTS:
            await session.run(stmt)
    yield
    await driver.close()


app = FastAPI(lifespan=lifespan)


# --- Models ---


class UserSummary(BaseModel):
    id: str
    username: str
    bio: str = ""


class TweetRead(BaseModel):
    id: str
    seed_id: str
    author_id: str
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
    id: str
    username: str
    bio: str
    created_at: datetime
    followers: list[UserSummary]
    following: list[UserSummary]
    tweets: list[TweetRead]


# --- Profile Endpoints ---


PROFILE_VIEW_CYPHER = """
MATCH (p:Profile {id: $target_id})
OPTIONAL MATCH (p)-[:POSTED]->(t:Tweet)
WITH p, t 
ORDER BY t.created_at DESC 
WITH p, collect(t) AS tweetNodes
RETURN
    p.id AS id,
    p.username AS username,
    p.bio AS bio,
    p.created_at AS created_at,
    [(p)<-[:FOLLOWS]-(follower:Profile) | {id: follower.id, username: follower.username, bio: follower.bio}] AS followers,
    [(p)-[:FOLLOWS]->(followee:Profile) | {id: followee.id, username: followee.username, bio: followee.bio}] AS following,
    [tw IN tweetNodes | {
        id: tw.id, seed_id: tw.seed_id, content: tw.content,
        author_username: tw.author_username, created_at: tw.created_at,
        likes: tw.likes, comments: tw.comments
    }] AS tweets
"""


async def _build_profile_view(session, target_id: str, viewer_id: str) -> ProfileRead:
    result = await session.run(PROFILE_VIEW_CYPHER, target_id=target_id)
    record = await result.single()

    if record is None:
        raise HTTPException(status_code=404, detail="profile not found")

    is_mine = viewer_id == target_id
    tweets = [
        TweetRead(
            id=t["id"],
            seed_id=t["seed_id"],
            author_id=target_id,
            author_username=t["author_username"],
            content=t["content"],
            created_at=t["created_at"].to_native(),
            likes=t["likes"],
            comments=t["comments"],
            is_mine=is_mine,
        )
        for t in record["tweets"]
    ]

    return ProfileRead(
        id=record["id"],
        username=record["username"],
        bio=record["bio"],
        created_at=record["created_at"].to_native(),
        followers=[UserSummary(**f) for f in record["followers"]],
        following=[UserSummary(**f) for f in record["following"]],
        tweets=tweets,
    )


@app.get("/profile", response_model=ProfileRead)
async def get_profile(user_id: str = Depends(get_current_user_id)):
    async with driver.session() as session:
        return await _build_profile_view(session, target_id=user_id, viewer_id=user_id)


@app.get("/profile/{target_id}", response_model=ProfileRead)
async def get_profile_by_id(
    target_id: str, user_id: str = Depends(get_current_user_id)
):
    async with driver.session() as session:
        return await _build_profile_view(
            session, target_id=target_id, viewer_id=user_id
        )


# --- Accumulator Endpoints ---


FEED_CYPHER = """
MATCH (me:Profile {id: $user_id})-[:FOLLOWS*0..1]->(author:Profile)-[:POSTED]->(t:Tweet)
RETURN t.id AS id, t.seed_id AS seed_id, author.id AS author_id, t.content AS content,
       author.username AS author_username, t.created_at AS created_at,
       t.likes AS likes, t.comments AS comments
ORDER BY t.created_at DESC
"""


@app.get("/feed", response_model=list[TweetRead])
async def get_feed(user_id: str = Depends(get_current_user_id)):
    async with driver.session() as session:
        result = await session.run(FEED_CYPHER, user_id=user_id)
        records = [r async for r in result]

    return [
        TweetRead(
            id=r["id"],
            seed_id=r["seed_id"],
            author_id=r["author_id"],
            author_username=r["author_username"],
            content=r["content"],
            created_at=r["created_at"].to_native(),
            likes=r["likes"],
            comments=r["comments"],
            is_mine=(r["author_id"] == user_id),
        )
        for r in records
    ]


# --- Create Endpoints ---


CREATE_TWEET_CYPHER = """
MATCH (author:Profile {id: $author_id})
CREATE (author)-[:POSTED]->(t:Tweet {
    id: randomUUID(),
    seed_id: $seed_id,
    content: $content,
    author_username: author.username,
    created_at: datetime(),
    likes: [],
    comments: []
})
RETURN t.id AS id, t.seed_id AS seed_id, t.content AS content,
       author.username AS author_username, author.id AS author_id,
       t.created_at AS created_at
"""


@app.post("/tweet", response_model=TweetRead)
async def create_tweet(body: TweetCreate, user_id: str = Depends(get_current_user_id)):
    async with driver.session() as session:
        result = await session.run(
            CREATE_TWEET_CYPHER,
            author_id=user_id,
            seed_id=body.seed_id,
            content=body.content,
        )
        record = await result.single()

    if record is None:
        raise HTTPException(status_code=404, detail="profile not found")

    return TweetRead(
        id=record["id"],
        seed_id=record["seed_id"],
        author_id=record["author_id"],
        author_username=record["author_username"],
        content=record["content"],
        created_at=record["created_at"].to_native(),
        likes=[],
        comments=[],
        is_mine=True,
    )
