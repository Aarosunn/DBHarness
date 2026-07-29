# littleX Bundle Refactor — Design Spec

Date: 2026-07-29. Scope approved by Aaron; remaining choices delegated.
Verified against code by an adversarial review agent (all file:line citations below confirmed).

## Goal

Adopt the upstream littleX idiom (jaseci-labs/jaseci #7548 `d00a086c5`: report graph
nodes and typed bundles instead of view-model DTOs, drop server-side `is_mine`) in the
DBHarness jac app, keep harness-specific machinery, mirror the contract change in the
three baselines, then sanity-bench.

Not goals: jaseci-rel (pg-rel) changes, root-centric remodel, real-numbers benchmark,
extra upstream walkers (channels/trending/likes/follow).

## 1. Jac app refactor — `littleXs/jaseci/app.jac` (in-place edit)

**Delete:** `UserView`, `ProfileView`, `TweetView`, `Profile.to_user_view`,
`Profile.to_profile_view`, `Tweet.to_view`, all `viewer_username` threading
(existed only to compute `is_mine`).

**Add:**

```jac
obj ProfileBundle {
    has profile: Profile,
        followers: list[Profile],
        following: list[Profile],
        tweets: list[Tweet];
}
```

`Profile` gains:

```jac
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
```

Lambda syntax note: this fork uses `lambda t: Tweet : t.created_at`
(app.jac:167, serializer.impl.jac:521), NOT upstream's block-lambda form.

**Walkers (same 4 names/routes, envelope + timing kept):**
- `get_profile`, `get_profile_by_id`: report `{"server_total_ms": ..., "profile": here.to_bundle()}`
- `load_feed`: `feed: list[Tweet]`; gather appends `here` (jid-dedup `seen` set KEPT);
  deliver sorts by `created_at` desc, reports `{"server_total_ms": ..., "feed": self.feed}`
- `create_tweet`: unchanged graph logic; reports `{"server_total_ms": ..., "tweet": new}`

**Kept harness specifics:** `seed_id` on Tweet, in-walker `t0`/`server_total_ms`
timing, report envelopes, feed dedup, `get_profile_by_id` (jobj lookup), sort by
`created_at` desc, the 4-walker subset, grants, `_now`, edges. `main.jac` untouched.

**Untouched:** `social_graph.jac` (dead duplicate of the old idiom, not imported by
main.jac — explicitly skipped).

## 2. Fork change — `JAC_API_LEAN_RESPONSE` keeps `_jac_id`

Node-report identity = `_jac_id` on the wire; lean currently omits it.

Single site: `serializer.impl.jac:197` — the `_jac_*` block is stamped under
`if api_mode and not lean_response_enabled()`. Change: stamp `_jac_id`
unconditionally under `api_mode`; gate only `_jac_type`/`_jac_archetype` on lean.

Breaks one fork test (must update in same commit):
`scale/tests/data/test_lean_projection_compose.jac:56-60` asserts lean drops ALL
`_jac_*` keys — invert to: `_jac_id` present, `_jac_type`/`_jac_archetype` absent.

## 3. Baselines — delete `is_mine` only

Emit-only, verified no other consumers. Lines:
- `littleXs/postgres/app.py`: 105 (model field), 170, 183, 256, 311
- `littleXs/sqlalchemy/app.py`: 149, 211, 286, 328
- `littleXs/neo4j/app.py`: 88, 137, 148, 226, 286

No field additions, no shape changes. Baselines keep their idiomatic flat shapes
and extra fields (`id`, `author_id`, profile-level `created_at`) — the oracle is
field-selective and ignores extras. Footnote for any future response-BYTE
comparison: wire field sets are not identical across engines.

## 4. Tests

- `littleXs/jaseci/tests/test_littlex.jac`: rewrite for new shapes — `is_mine`
  assert (line 95) becomes client-side logic (`tweet["author_username"] == viewer`);
  view-shape asserts become bundle/node-shape asserts (identity via `_jac_id`).
- Fork: `test_lean_projection_compose.jac` per section 2.
- Existing lean/serializer suites re-run as regression gate.

## 5. Sanity bench (NOT real numbers)

Busy machine, Mongo backend, relative spread only, compared loosely vs remembered
ballpark. Criteria: (a) oracle passes on all engines; (b) jac's relative position
vs PG/SQLA/neo4j in the same window is in the old ballpark. No absolute claims.

Recipe:
- Seed phase: `JAC_TOPOLOGY_INDEX=1`, `READ_ONLY` OFF (writes must work; GTI blobs
  build at connect hooks).
- Serve phase: `JAC_TOPOLOGY_INDEX=1 JAC_CROSS_ROOT_RESOLVE=1 JAC_BATCH_L3=1
  JAC_READ_ONLY=1 JAC_GTI_CACHE=1 JAC_COMPILED_SERIALIZER=1
  JAC_PROJECTION='Tweet:content,created_at,author_username,likes,comments,seed_id;Profile:username,bio'
  JAC_ORDER_PUSHDOWN=1 JAC_MEM_POOL=1 JAC_LAZY_HYDRATION=1 JAC_GC_FREEZE=1
  JAC_API_LEAN_RESPONSE=1 JAC_ACCESS_LOG=0 JAC_REPORT_ECHO=0`
- `JAC_READ_AUTOCOMMIT` skipped (inert on Mongo).

## Verified constraints & accepted warts (review-agent findings)

1. **Projection is fetch-path + `read_only`-gated** (`resolver.impl.jac:141-160`;
   filter applied per-object via `_projected_fields`, serializer.impl.jac:22,43;
   stamped only by `deserialize_projected`, :834). The "extra node fields off the
   wire" guarantee requires `JAC_READ_ONLY=1` and path-resolved nodes — holds for
   this app (all Profile/Tweet touches are last-hop path resolves). Bench MUST run
   read_only on (it already does).
2. `create_tweet`'s fresh Tweet is never projected; its full field set equals the
   projection list → wire identical. No action.
3. **ProfileBundle gets a synthetic random `_jac_id`** per instance (ObjectAnchor
   cached_property, archetype.jac:183-186). Accepted noise; clients ignore
   bundle-level `_jac_id` (upstream has the same property).
4. Projected anchors carry `edges=[]`/`hash=0` (serializer.impl.jac:828-829):
   `to_bundle` traversal from a projected Profile works via the GTI path only —
   pre-existing property, covered by the root_id fix (e3ab93df2), not a regression.
5. Compiled serializer composes: plan bypassed when `projected is not None`
   (serializer.impl.jac:26-28); ProfileBundle (a dataclass obj) gets a field plan;
   both flags on = correct (exercised by the compose test).
6. Oracle (`harness/oracle.py`) compares `seed_id` sets + `created_at` order only;
   `run.py` reads envelope keys `feed`/`profile`/`tweet` — both match the new
   shapes untouched. Lean single-report unwrap (server.impl.jac:360-369) applies to
   dict reports; `seed_jac.py`'s bare-string report is not unwrapped (dict-only) —
   seeding unaffected.

## Success criteria

1. `jac test` green on refactored app tests + fork serializer/lean suites.
2. Oracle passes all 4 engines with new shapes.
3. Sanity spread within ballpark of remembered relative positions.
4. Zero `is_mine` remaining anywhere served; zero view classes in app.jac.
