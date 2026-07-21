"""
LittleX backend, tuned to match GTI and FP experiments
Database abstracted in the language runtime research
"""

import datetime;
import os;
import time;
import from typing { cast }

def _now -> str {
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat() + "Z";
}

# EXPERIMENT (pairs with backend JAC_ORDER_PUSHDOWN): trust PG's ORDER BY and
# skip the python-side feed sort. NOTE: feed = two visit streams (own tweets,
# followee tweets), each PG-ordered; skipping the sort concatenates two sorted
# runs, so the global order contract differs -- perf probe only, not parity.
def _skip_feed_sort -> bool {
    return os.environ.get("JAC_SKIP_FEED_SORT") == "1";
}

# --- View models: the typed contract returned to the client ---
obj UserView {
    has id: str,
        username: str,
        bio: str = "";
}

obj ProfileView {
    has id: str,
        username: str,
        bio: str,
        followers: list[UserView],
        following: list[UserView],
        tweets: list[TweetView];
}

obj TweetView {
    has id: str,
        seed_id: str,
        content: str,
        author_username: str,
        created_at: str,
        likes: list[str],
        comments: list[dict[str, str]],
        is_mine: bool = False;
}

# --- Edges: the relationships in the social graph ---
edge Follow {}
edge Post {}


# --- Graph nodes: data, plus the methods that present it as a view.
#     A node knows how to describe itself; walkers decide when to ask. ---
node Profile {
    has username: str = "",
        bio: str = "",
        created_at: str = "";

    def to_user_view -> UserView {
        return UserView(id=jid(self), username=self.username, bio=self.bio);
    }

    def to_profile_view(viewer_username: str) -> ProfileView {
        followers = [p.to_user_view() for p in [self<-:Follow:<-[?:Profile]]];
        following = [p.to_user_view() for p in [self->:Follow:->[?:Profile]]];
        tweets = [t.to_view(viewer_username) for t in [self-->[?:Tweet]]];
        tweets.sort(key=lambda t: TweetView : t.created_at, reverse=True);
        return ProfileView(
            id=jid(self),
            username=self.username,
            bio=self.bio,
            followers=followers,
            following=following,
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

    def to_view(viewer_username: str) -> TweetView {
        return TweetView(
            id=jid(self),
            seed_id=self.seed_id,
            content=self.content,
            author_username=self.author_username,
            created_at=self.created_at,
            likes=self.likes,
            comments=self.comments,
            is_mine=(self.author_username == viewer_username)
        );
    }
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
        profile = here.to_profile_view(here.username);
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "profile": profile};
    }
}

walker get_profile_by_id {
    has target_id: str = "",
        viewer_username: str = "",
        reports: list[dict] = [],
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();

        mine = [-->[?:Profile]];
        if mine {
            self.viewer_username = mine[0].username;
        }
        if self.target_id {
            target = jobj(self.target_id);
            if isinstance(target, Profile) {
                visit [target];
            }
        }
    }

    can give with Profile entry {
        profile = here.to_profile_view(self.viewer_username);
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "profile": profile};
    }
}

# --- Acucumulator walkers: fan out, gather at each node, report once at exit ---
walker load_feed {
    has feed: list[TweetView] = [],
        reports: list[dict] = [],
        viewer_username: str = "",
        seen: set = set(),
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();

        mine = [-->[?:Profile]];
        if mine {
            me = mine[0];
            self.viewer_username = me.username;
            visit [me-->[?:Tweet]];
            visit [me->:Follow:->[?:Profile]-->[?:Tweet]];
        }
    }

    can gather with Tweet entry {
        if jid(here) not in self.seen {
            self.seen.add(jid(here));
            self.feed.append(here.to_view(self.viewer_username));
        }
    }

    can deliver with Root exit {
        if not _skip_feed_sort() {
            self.feed.sort(key=lambda t: TweetView : t.created_at, reverse=True);
        }

        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "feed": self.feed};
    }
}

# feed_page: top-20 newest tweets. Correct ONLY with
# JAC_ORDER_PUSHDOWN=Tweet:created_at:desc (the runtime flag supplies the
# ordering the language cannot yet express). Per-stream top-20 union contains
# the global top-20, so the merge below is exact parity with baselines' LIMIT 20.
walker load_feed_page {
    has feed: list[TweetView] = [],
        reports: list[dict] = [],
        viewer_username: str = "",
        seen: set = set(),
        t0: float = 0.0;

    can run with Root entry {
        self.t0 = time.perf_counter();

        mine = [-->[?:Profile]];
        if mine {
            me = mine[0];
            self.viewer_username = me.username;
            visit [me-->[?:Tweet]][:20];
            visit [me->:Follow:->[?:Profile]-->[?:Tweet]][:20];
        }
    }

    can gather with Tweet entry {
        if jid(here) not in self.seen {
            self.seen.add(jid(here));
            self.feed.append(here.to_view(self.viewer_username));
        }
    }

    can deliver with Root exit {
        self.feed.sort(key=lambda t: TweetView : t.created_at, reverse=True);
        self.feed = self.feed[:20];
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
        tweet = new.to_view(here.username);
        server_total_ms = (time.perf_counter() - self.t0) * 1000;
        report {"server_total_ms": server_total_ms, "tweet": tweet};
    }
}
