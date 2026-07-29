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
    assert feed[0]["seed_id"] == "a1";
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
