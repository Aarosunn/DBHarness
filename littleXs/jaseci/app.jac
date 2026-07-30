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

# Leaf-materialized feed (requires JAC_LEAF_MATERIALIZE=Tweet): expression
# reads return tweets as plain projected dicts -- no Tweet objects are built.
# Mongo sorts each stream (JAC_ORDER_PUSHDOWN) and dedup keys on _jac_id;
# the walker only merges the two dict streams.
walker load_feed_leaf {
    has reports: list[dict] = [],
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();

        feed: list = [];
        mine = [-->[?:Profile]];
        if mine {
            me = mine[0];
            seen: set = set();
            for t in [me-->[?:Tweet]] + [me->:Follow:->[?:Profile]-->[?:Tweet]] {
                tid = t['_jac_id'];
                if tid not in seen {
                    seen.add(tid);
                    feed.append(t);
                }
            }
            feed.sort(key=lambda d: dict : d['created_at'], reverse=True);
        }

        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "feed": feed};
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
