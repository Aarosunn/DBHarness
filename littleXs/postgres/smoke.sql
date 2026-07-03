-- smoke.sql: minimal fixture for manual testing against the postgres engine.
-- Schema is created by app.py on startup; run this after that, e.g.:
--   psql "$DATABASE_URL" -f smoke.sql

INSERT INTO profiles (username, bio) VALUES
    ('alice', 'building things'),
    ('bob', 'coffee and code'),
    ('carol', 'graph nerd');

-- bob follows alice; carol follows alice and bob
INSERT INTO follows (follower_id, followee_id)
SELECT b.id, a.id FROM profiles a, profiles b
WHERE a.username = 'alice' AND b.username = 'bob';

INSERT INTO follows (follower_id, followee_id)
SELECT c.id, a.id FROM profiles a, profiles c
WHERE a.username = 'alice' AND c.username = 'carol';

INSERT INTO follows (follower_id, followee_id)
SELECT c.id, b.id FROM profiles b, profiles c
WHERE b.username = 'bob' AND c.username = 'carol';

-- explicit, staggered timestamps (not DEFAULT now()) so ORDER BY created_at DESC
-- is actually verifiable instead of three near-identical inserts
INSERT INTO tweets (seed_id, author_id, content, created_at)
SELECT 'smoke_tweet_1', id, 'hello from alice', TIMESTAMPTZ '2026-01-01 12:00:00+00'
FROM profiles WHERE username = 'alice';

INSERT INTO tweets (seed_id, author_id, content, created_at)
SELECT 'smoke_tweet_2', id, 'bob says hi', TIMESTAMPTZ '2026-01-01 12:01:00+00'
FROM profiles WHERE username = 'bob';

INSERT INTO tweets (seed_id, author_id, content, created_at)
SELECT 'smoke_tweet_3', id, 'carol here', TIMESTAMPTZ '2026-01-01 12:02:00+00'
FROM profiles WHERE username = 'carol';

-- expected results once loaded (get each id via: SELECT id, username FROM profiles;)
--
-- GET /profile?user_id=<alice.id>
--   followers: [bob, carol]   following: []           tweets: ["hello from alice"]
-- GET /profile?user_id=<bob.id>
--   followers: [carol]        following: [alice]      tweets: ["bob says hi"]
-- GET /profile?user_id=<carol.id>
--   followers: []             following: [alice, bob] tweets: ["carol here"]
--
-- GET /feed?user_id=<alice.id> -> ["hello from alice"]                         (alice follows no one)
-- GET /feed?user_id=<bob.id>   -> ["bob says hi", "hello from alice"]          (bob + alice, newest first)
-- GET /feed?user_id=<carol.id> -> ["carol here", "bob says hi", "hello from alice"]  (carol + bob + alice, newest first)
--
-- POST /tweet?user_id=<alice.id> {"content": "test", "seed_id": "smoke_tweet_4"}
--   -> 200, is_mine: true, author_username: "alice"
-- GET /profile/<bob.id>?user_id=<alice.id>
--   -> is_mine: false on bob's tweet (alice viewing bob's profile)
