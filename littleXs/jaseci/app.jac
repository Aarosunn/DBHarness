"""
LittleX backend, tuned to match GTI and FP experiments
Database abstracted in the language runtime research
"""

import datetime;
import from typing { cast }

def _now -> str {
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat() + "Z";
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

    def to_profile_view -> ProfileView {
        followers = [p.to_user_view() for p in [self<-:Follow:<-[?:Profile]]];
        following = [p.to_user_view() for p in [self->:Follow:->[?:Profile]]];
        tweets = [t.to_view() for t in [self-->[?:Tweet]]];
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

    def to_view -> TweetView {
        mine = [root-->[?:Profile]];
        is_mine: bool = len(mine) > 0 and self.author_username == mine[0].username;
        return TweetView(
            id=jid(self),
            seed_id=self.seed_id,
            content=self.content,
            author_username=self.author_username,
            created_at=self.created_at,
            likes=self.likes,
            comments=self.comments,
            is_mine=is_mine
        );
    }
}
# --- Profile walkers: spawn at the caller's root, act on their profile ---
walker get_profile {
    has reports: list[ProfileView] = [];

    can run with Root entry {
        visit [-->[?:Profile]];
    }

    can give with Profile entry {
        report here.to_profile_view();
    }
}

walker get_profile_by_id {
    has target_id: str = "",
        reports: list[ProfileView] = [];

    can run with Root entry {
        if self.target_id {
            target = jobj(self.target_id);
            if isinstance(target, Profile) {
                visit [target];
            }
        }
    }

    can give with Profile entry {
        report here.to_profile_view();
    }
}

# --- Acucumulator walkers: fan out, gather at each node, report once at exit ---
walker load_feed {
    has feed: list[TweetView] = [],
        reports: list[list[TweetView]] = [];

    can run with Root entry {
        mine = [-->[?:Profile]];
        if mine {
            me = mine[0];
            visit [me-->[?:Tweet]];
            visit [me->:Follow:->[?:Profile]-->[?:Tweet]];
        }
    }

    can gather with Tweet entry {
        self.feed.append(here.to_view());
    }

    can deliver with Root exit {
        self.feed.sort(key=lambda t: TweetView : t.created_at, reverse=True);
        report self.feed;
    }
}

# --- Create walkers: navigate to the caller's profile, then attach a node ---
walker create_tweet {
    has content: str,
        seed_id: str;

    can run with Root entry {
        visit [-->[?:Profile]];
    }

    can make with Profile entry {
        new = cast(
            Tweet,
            here +>:Post():+> Tweet(
                seed_id=self.seed_id, content=self.content,
                author_username=here.username, created_at=_now()
            )
        );

        grant(new, level=WritePerm);
        report new.to_view();
    }
}
