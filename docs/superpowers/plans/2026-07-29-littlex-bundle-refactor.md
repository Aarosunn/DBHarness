# littleX Bundle Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt upstream littleX node-report/bundle idiom in the served jac app (drop `is_mine`, delete view DTOs), keep `_jac_id` under lean-response, mirror `is_mine` removal in the 3 baselines, sanity-bench.

**Architecture:** In-place edit of the self-contained `app.jac` (spec §1); one-site serializer change in the JaseciFork (spec §2); mechanical field removal in baselines (spec §3). Oracle/harness verified untouched by shape change (field-selective).

**Tech Stack:** jac (fork at `~/Dev/Research/DatabaseResearch/JaseciFork`, branch `bench/all-flags`), FastAPI baselines, Mongo backend, DBHarness scripts pipeline (`harness/scripts/10..60`).

**Repos:** DBHarness = `~/Dev/Research/DatabaseResearch/DBHarness`. Fork = `~/Dev/Research/DatabaseResearch/JaseciFork`. Commits end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: Failing test for the new app shapes

**Files:**
- Create: `littleXs/jaseci/tests/test_app_bundles.jac`

Targets `main.jac` (imports app + import_data seed walkers — app.jac alone cannot create profiles). Old `test_littlex.jac` targets dead `social_graph.jac`; leave it untouched.

- [ ] **Step 1: Write the failing test**

```jac
"""Tests for the SERVED benchmark app (app.jac via main.jac) in the upstream
node-report/bundle idiom: raw Tweet nodes in the feed, ProfileBundle for
profiles, no is_mine anywhere, identity via _jac_id (lean off here, so the
full _jac_* block is present).

Run with:  jac test test_app_bundles.jac   (from littleXs/jaseci/tests)
"""

import os;
import from tempfile { mkdtemp }
import from jaclang.runtimelib.testing { JacTestClient, TestResponse }

glob SERVER = os.path.join(os.path.dirname(__file__), "..", "main.jac");

def make_client -> JacTestClient {
    return JacTestClient.from_file(SERVER, base_path=mkdtemp());
}

def login_as(client: JacTestClient, username: str, password: str) {
    client.register_user(username, password);
    client.login(username, password);
}

"""First report of the walker response (no lean in tests: data.reports[0])."""
def first_report(response: TestResponse) -> any {
    data = response.data;
    if data and "reports" in data {
        reports = list(data["reports"]);
        return reports[0] if reports else None;
    }
    return None;
}

test "create_tweet reports a raw Tweet node, no is_mine" {
    client = make_client();
    login_as(client, "alice", "secret123");
    first_report(client.post("/walker/seed_profile", json={"username": "alice"}));

    env = first_report(client.post(
        "/walker/create_tweet", json={"content": "hello world", "seed_id": "t1"}
    ));
    assert "server_total_ms" in env;
    tweet = env["tweet"];
    assert tweet["content"] == "hello world";
    assert tweet["seed_id"] == "t1";
    assert tweet["author_username"] == "alice";
    assert "is_mine" not in tweet;
    assert tweet["_jac_id"];

    client.close();
}

test "load_feed reports raw Tweet nodes incl. followed users, sorted desc" {
    client = make_client();
    client.register_user("alice", "secret123");
    client.register_user("bob", "secret123");

    client.login("bob", "secret123");
    bob_jid = first_report(
        client.post("/walker/seed_profile", json={"username": "bob"})
    );
    client.post("/walker/seed_tweet", json={
        "seed_id": "b1", "content": "bob's update",
        "created_at": "2026-06-01T10:00:00Z", "author_username": "bob"
    });

    client.login("alice", "secret123");
    first_report(client.post("/walker/seed_profile", json={"username": "alice"}));
    client.post("/walker/seed_tweet", json={
        "seed_id": "a1", "content": "alice's update",
        "created_at": "2026-06-01T11:00:00Z", "author_username": "alice"
    });
    client.post("/walker/seed_follow", json={"target_id": bob_jid});

    env = first_report(client.post("/walker/load_feed", json={}));
    feed = list(env["feed"]);
    assert {t["seed_id"] for t in feed} == {"a1", "b1"};
    assert feed[0]["seed_id"] == "a1";  # newer first
    for t in feed {
        assert "is_mine" not in t;
        assert t["_jac_id"];
    }

    client.close();
}

test "get_profile reports a ProfileBundle" {
    client = make_client();
    client.register_user("alice", "secret123");
    client.register_user("bob", "secret123");

    client.login("bob", "secret123");
    bob_jid = first_report(
        client.post("/walker/seed_profile", json={"username": "bob"})
    );

    client.login("alice", "secret123");
    first_report(client.post(
        "/walker/seed_profile", json={"username": "alice", "bio": "hi"}
    ));
    client.post("/walker/seed_tweet", json={
        "seed_id": "a1", "content": "mine",
        "created_at": "2026-06-01T11:00:00Z", "author_username": "alice"
    });
    client.post("/walker/seed_follow", json={"target_id": bob_jid});

    env = first_report(client.post("/walker/get_profile", json={}));
    bundle = env["profile"];
    assert bundle["profile"]["username"] == "alice";
    assert bundle["profile"]["bio"] == "hi";
    assert [p["username"] for p in bundle["following"]] == ["bob"];
    assert bundle["followers"] == [];
    assert len(list(bundle["tweets"])) == 1;
    assert bundle["tweets"][0]["seed_id"] == "a1";

    client.close();
}

test "get_profile_by_id reports the target's bundle" {
    client = make_client();
    client.register_user("alice", "secret123");
    client.register_user("bob", "secret123");

    client.login("bob", "secret123");
    bob_jid = first_report(
        client.post("/walker/seed_profile", json={"username": "bob"})
    );

    client.login("alice", "secret123");
    first_report(client.post("/walker/seed_profile", json={"username": "alice"}));

    env = first_report(client.post(
        "/walker/get_profile_by_id", json={"target_id": bob_jid}
    ));
    assert env["profile"]["profile"]["username"] == "bob";

    client.close();
}
```

- [ ] **Step 2: Run to verify it FAILS against current code**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness/littleXs/jaseci/tests
JAC_TEST_JOBS=0 jac test test_app_bundles.jac
```

Expected: FAIL — current `create_tweet` reports `TweetView` (`is_mine` present, no `_jac_id` key); `get_profile` reports flat `ProfileView` (no nested `"profile"` key). If instead it errors on client setup/seed walkers, fix the test harness usage FIRST — the failures must be shape assertions.

Note: seed grants changed 2026-07-06 (obs 1066) to `ConnectPerm` — cross-root follow works in tests.

- [ ] **Step 3: Commit the red test**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness
git add littleXs/jaseci/tests/test_app_bundles.jac
git commit --no-verify -m "test: add bundle-idiom shape tests for served app (red)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Refactor `app.jac` to bundles/node-report

**Files:**
- Modify: `littleXs/jaseci/app.jac` (full replacement below)

- [ ] **Step 1: Replace app.jac content**

```jac
"""
LittleX backend, tuned to match GTI and FP experiments
Database abstracted in the language runtime research

Upstream node-report idiom (jaseci-labs/jaseci #7548): walkers report graph
nodes and typed bundles directly — identity travels as _jac_id, no view DTOs,
no server-side is_mine (client derives it from author_username). Harness
specifics kept: seed_id, in-walker server_total_ms timing envelope, feed
dedup, get_profile_by_id, created_at desc ordering.
"""

import datetime;
import time;
import from typing { cast }

def _now -> str {
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat() + "Z";
}

# --- Edges: the relationships in the social graph ---
edge Follow {}
edge Post {}

# --- Report bundle: a node plus the edge-derived context the client needs
#     alongside it. The node travels whole - identity included. ---
obj ProfileBundle {
    has profile: Profile,
        followers: list[Profile],
        following: list[Profile],
        tweets: list[Tweet];
}

# --- Graph nodes ---
node Profile {
    has username: str = "",
        bio: str = "",
        created_at: str = "";

    def to_bundle -> ProfileBundle {
        tweets = [self-->[?:Tweet]];
        tweets.sort(key=lambda t: Tweet : t.created_at, reverse=True);
        return ProfileBundle(
            profile=self,
            followers=[self<-:Follow:<-[?:Profile]],
            following=[self->:Follow:->[?:Profile]],
            tweets=tweets
        );
    }
}

node Tweet {
    has seed_id: str = "",
        content: str = "",
        author_username: str = "",
        created_at: str = "",
        likes: list[str] = [],
        comments: list[dict[str, str]] = [];
}

# --- Profile walkers: spawn at the caller's root, act on their profile ---
walker get_profile {
    has reports: list[dict] = [],
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();
        visit [-->[?:Profile]];
    }

    can give with Profile entry {
        bundle = here.to_bundle();
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "profile": bundle};
    }
}

walker get_profile_by_id {
    has target_id: str = "",
        reports: list[dict] = [],
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();
        if self.target_id {
            target = jobj(self.target_id);
            if isinstance(target, Profile) {
                visit [target];
            }
        }
    }

    can give with Profile entry {
        bundle = here.to_bundle();
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "profile": bundle};
    }
}

# --- Accumulator walkers: fan out, gather at each node, report once at exit ---
walker load_feed {
    has feed: list[Tweet] = [],
        reports: list[dict] = [],
        seen: set = set(),
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();

        mine = [-->[?:Profile]];
        if mine {
            me = mine[0];
            visit [me-->[?:Tweet]];
            visit [me->:Follow:->[?:Profile]-->[?:Tweet]];
        }
    }

    can gather with Tweet entry {
        if jid(here) not in self.seen {
            self.seen.add(jid(here));
            self.feed.append(here);
        }
    }

    can deliver with Root exit {
        self.feed.sort(key=lambda t: Tweet : t.created_at, reverse=True);

        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "feed": self.feed};
    }
}

# --- Create walkers: navigate to the caller's profile, then attach a node ---
walker create_tweet {
    has content: str,
        seed_id: str,
        reports: list[dict] = [],
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();
        visit [-->[?:Profile]];
    }

    can make with Profile entry {
        new = cast(
            Tweet,
            here +>:Post():+> Tweet(
                seed_id=self.seed_id,
                content=self.content,
                author_username=here.username,
                created_at=_now()
            )
        );

        grant(new, level=WritePerm);
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "tweet": new};
    }
}
```

- [ ] **Step 2: Run the test — expect PASS**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness/littleXs/jaseci/tests
JAC_TEST_JOBS=0 jac test test_app_bundles.jac
```

Expected: all 4 tests PASS. If `to_bundle` ordering assert fails on equal timestamps, timestamps in the test differ by construction — investigate, don't loosen the assert.

- [ ] **Step 3: Grep for leftovers**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness
grep -n "is_mine\|TweetView\|ProfileView\|UserView\|to_view\|viewer_username" littleXs/jaseci/app.jac
```

Expected: zero hits.

- [ ] **Step 4: Commit**

```bash
git add littleXs/jaseci/app.jac
git commit --no-verify -m "refactor(jaseci): adopt upstream bundle/node-report idiom in served app

Views deleted, walkers report nodes/ProfileBundle, is_mine dropped
(client-derivable from author_username). Harness envelope/seed_id/dedup kept.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Fork — lean-response keeps `_jac_id`

**Files:**
- Modify: `JaseciFork/jac/jaclang/runtimelib/impl/serializer.impl.jac:196-205`
- Modify: `JaseciFork/jac/jaclang/scale/tests/data/test_lean_projection_compose.jac:54-62`

Work in the MAIN fork worktree on `bench/all-flags` (other sessions inactive; small serial commit).

- [ ] **Step 1: Edit the serializer stamp block**

Old (`serializer.impl.jac:196-205`):

```jac
        result = Serializer._type_info(val, include_type);
        if api_mode and not lean_response_enabled() {
            result |= {
                '_jac_type': type(val).__name__,
                '_jac_id': val.__jac__.id.hex if val?.__jac__ else None,
                '_jac_archetype': 'node'
                    if isinstance(val, NodeArchetype)
                    else 'walker' if isinstance(val, WalkerArchetype) else 'archetype'
            };
        }
```

New:

```jac
        result = Serializer._type_info(val, include_type);
        if api_mode {
            # _jac_id is the node's wire identity (node-report idiom) — kept
            # even under lean; lean drops only the type/archetype metadata.
            result |= {'_jac_id': val.__jac__.id.hex if val?.__jac__ else None};
            if not lean_response_enabled() {
                result |= {
                    '_jac_type': type(val).__name__,
                    '_jac_archetype': 'node'
                        if isinstance(val, NodeArchetype)
                        else 'walker' if isinstance(val, WalkerArchetype) else 'archetype'
                };
            }
        }
```

- [ ] **Step 2: Update the compose test's expectations**

Old (`test_lean_projection_compose.jac:54-62`):

```jac
        item = body["feed"][0];
        assert item == {"name": "ann"} , (
            f"only the projected field must survive, no leaked defaults: {item}"
        );
        for key in item.keys() {
            assert not key.startswith("_jac_") , (
                f"lean must drop _jac_* fields, found {key}: {item}"
            );
        }
```

New:

```jac
        item = body["feed"][0];
        assert set(item.keys()) == {"name", "_jac_id"} , (
            f"projected field + _jac_id identity must survive, nothing else: {item}"
        );
        assert item["name"] == "ann";
        assert item["_jac_id"] , "lean keeps _jac_id (node-report identity)";
        assert "_jac_type" not in item and "_jac_archetype" not in item , (
            f"lean must still drop type/archetype metadata: {item}"
        );
```

Also update the file docstring line 8: `and the lean envelope-unwrap + `_jac_*` stripping still apply on top.` → `and the lean envelope-unwrap still applies; lean keeps _jac_id but drops _jac_type/_jac_archetype.`

- [ ] **Step 3: Run fork gates**

```bash
cd ~/Dev/Research/DatabaseResearch/JaseciFork/jac
JAC_TEST_JOBS=0 jac test jaclang/scale/tests/data/test_lean_response.jac
JAC_TEST_JOBS=0 jac test jaclang/scale/tests/data/test_lean_projection_compose.jac  # needs local PG (jactest_rel)
JAC_TEST_JOBS=0 jac test jaclang/tests/runtimelib/test_compiled_serializer.jac
```

Expected: all green. If any `test_lean_response.jac` case asserts `_jac_id` ABSENT under lean, update that assertion the same way as the compose test (presence now expected).
If compose test errors on missing Postgres `jactest_rel`, start the harness PG (`harness/scripts/10-dbs.sh`) or create the db, then re-run — do not skip it silently.

- [ ] **Step 4: Commit (jac-format hook may rewrite — re-stage and re-commit if hook reports modifications, then re-run Step 3 gates)**

```bash
cd ~/Dev/Research/DatabaseResearch/JaseciFork
git add jac/jaclang/runtimelib/impl/serializer.impl.jac \
        jac/jaclang/scale/tests/data/test_lean_projection_compose.jac
git commit -m "feat(lean): keep _jac_id under JAC_API_LEAN_RESPONSE

Node-report idiom makes _jac_id the wire identity; lean now drops only
_jac_type/_jac_archetype metadata.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Baselines — delete `is_mine`

**Files:**
- Modify: `littleXs/postgres/app.py` (lines 105, 170, 183, 256, 311)
- Modify: `littleXs/sqlalchemy/app.py` (lines 149, 211, 286, 328)
- Modify: `littleXs/neo4j/app.py` (lines 88, 137, 148, 226, 286)

- [ ] **Step 1: Remove field + all emit sites**

Per file (line numbers pre-edit; patterns exact):
- Response-model field: delete the line `is_mine: bool = False` (postgres:105, sqlalchemy:149, neo4j:88).
- Compute lines: delete `is_mine = viewer_id == target_id` (postgres:170, neo4j:137).
- Constructor kwargs: delete the `is_mine=...` argument lines (postgres:183, 256, 311; sqlalchemy:211, 286, 328; neo4j:148, 226, 286). Watch trailing commas on the preceding line.

- [ ] **Step 2: Verify clean + syntax**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness/littleXs
grep -rn "is_mine" postgres/app.py sqlalchemy/app.py neo4j/app.py ; echo "grep-exit=$?"
python3 -m py_compile postgres/app.py sqlalchemy/app.py neo4j/app.py && echo OK
```

Expected: grep-exit=1 (no hits), `OK`.

- [ ] **Step 3: Commit**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness
git add littleXs/postgres/app.py littleXs/sqlalchemy/app.py littleXs/neo4j/app.py
git commit --no-verify -m "refactor(baselines): drop is_mine from responses (contract parity with node-report jac app)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Sanity bench (relative spread only)

**Files:** none created (CSVs land per harness defaults).

- [ ] **Step 1: DBs + servers with the all-flags recipe**

```bash
cd ~/Dev/Research/DatabaseResearch/DBHarness/harness
./scripts/10-dbs.sh
# Serve env (seed-safe: READ_ONLY deliberately NOT set yet)
export JAC_TOPOLOGY_INDEX=1 JAC_CROSS_ROOT_RESOLVE=1 JAC_BATCH_L3=1 \
  JAC_GTI_CACHE=1 JAC_COMPILED_SERIALIZER=1 \
  JAC_PROJECTION='Tweet:content,created_at,author_username,likes,comments,seed_id;Profile:username,bio' \
  JAC_ORDER_PUSHDOWN=1 JAC_MEM_POOL=1 JAC_LAZY_HYDRATION=1 JAC_GC_FREEZE=1 \
  JAC_API_LEAN_RESPONSE=1 JAC_ACCESS_LOG=0 JAC_REPORT_ECHO=0
./scripts/20-servers.sh
```

- [ ] **Step 2: Seed + tokens (writes ON)**

```bash
./scripts/30-seed.sh
./scripts/40-tokens.sh
```

- [ ] **Step 3: Flip READ_ONLY on for the read workloads — restart jac server**

```bash
export JAC_READ_ONLY=1
# restart only the jac server so it picks up READ_ONLY
# (20-servers.sh knows the launch command; kill the jac serve pid, rerun for jac)
./scripts/20-servers.sh   # idempotent per-engine start; verify jac PID changed
```

- [ ] **Step 4: Oracle — the actual point of this bench**

```bash
./scripts/50-oracle.sh
```

Expected: PASS all engines. FAIL = the refactor broke a shape/content — STOP and fix before latency.

- [ ] **Step 5: Bench + eyeball spread**

```bash
./scripts/60-bench.sh   # or: uv run python run.py --workloads feed,profile --requests 200 --warmup 20
```

Compare relative ordering/ratios to remembered ballpark (quiet 07-17: pg 10.4 / sqla 26.2 / jac 45.6-warmed / neo4j 52.6-fair — busy machine, ballpark ONLY, no absolute claims). Flag if jac's relative position vs SQLA/neo4j moved >±30%.

- [ ] **Step 6: Record outcome**

Append a dated note (config, oracle result, relative spread, "sanity only — busy machine") to the CSV dir or session notes; no commit needed unless harness scripts changed.

---

## Self-review notes

- Spec coverage: §1→Task 2, §2→Task 3, §3→Task 4, §4→Tasks 1+3, §5→Task 5. Covered.
- `social_graph.jac` + `test_littlex.jac`: explicitly untouched dead pair (spec §1/§4).
- jaseci-rel: explicitly out of scope.
- Type consistency: `ProfileBundle` fields match between Task 1 asserts and Task 2 code; envelope keys `server_total_ms`/`profile`/`feed`/`tweet` consistent across tasks and match `run.py` readers.
