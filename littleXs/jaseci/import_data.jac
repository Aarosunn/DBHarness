"""Seed walkers for the DBHarness benchmark.

MULTI-ROOT: each user's data must live under THAT user's own root (followees
are foreign roots — that's what the cross-root feed exercises). Separate roots
exist ONLY in a served deployment with registered users; a CLI/library run has
exactly one root (`jid(root.shared) == jid(root)`). So a single walker cannot
create N roots — seeding is inherently PER-USER. These are `walker:priv`, so
each runs on the authenticated user's own root. An external driver registers N
users and calls these on each user's token (see the driver recipe in the report
/ commit notes). Connect ops (`++>`, `+>:Post():+>`, `+>:Follow():+>`) fire
`on_edge_created`, so GTI builds at seed time (a raw insert would be GTI-blank).
"""

import from app { Profile, Tweet, Follow, Post }

# Create the caller's Profile under their root; grant ReadPerm so followers can
# see it cross-root; report its jid so the driver can wire follows.
walker:priv seed_profile {
    has username: str = "",
        bio: str = "";

    can run with Root entry {
        p = here ++> Profile(username=self.username, bio=self.bio);
        grant(p[0], level=ReadPerm);
        report jid(p[0]);
    }
}

# Attach a Tweet to the caller's Profile using the SEED's created_at (NOT _now(),
# so the deterministic timeline survives). ReadPerm so the tweet is visible in
# followers' feeds cross-root.
walker:priv seed_tweet {
    has seed_id: str = "",
        content: str = "",
        created_at: str = "",
        author_username: str = "";

    can run with Root entry {
        visit [-->[?:Profile]];
    }

    can attach with Profile entry {
        t = here +>:Post():+> Tweet(
            seed_id=self.seed_id,
            content=self.content,
            author_username=self.author_username,
            created_at=self.created_at
        );
        grant(t[0], level=ReadPerm);
        report jid(t[0]);
    }
}

# Connect the caller's Profile -:Follow:-> a target Profile on a foreign root
# (resolved by jid). This is the cross-root edge the feed traverses.
walker:priv seed_follow {
    has target_id: str = "";

    can run with Root entry {
        visit [-->[?:Profile]];
    }

    can link with Profile entry {
        target = jobj(self.target_id);
        if isinstance(target, Profile) {
            here +>:Follow():+> target;
        }
    }
}
