const { test } = require("node:test");
const assert = require("node:assert/strict");
const { WidgetClient } = require("../client.cjs");
const state = () => ({
  origin: "https://netaq.chobab.app",
  token: "secret",
  cache: {},
});
test("last data is preserved on a network failure but erased after revocation", async () => {
  const s = state();
  let status = 200;
  const client = new WidgetClient({
    state: s,
    save: async () => {},
    fetcher: async () => {
      if (status === 0) throw Error("offline");
      return new Response(
        JSON.stringify({ events: [{ title: "비공개 일정" }] }),
        { status },
      );
    },
  });
  await client.feed("day", "2026-11-16");
  status = 0;
  assert.equal((await client.feed("day", "2026-11-16")).cached, true);
  status = 401;
  assert.equal((await client.feed("day", "2026-11-16")).connected, false);
  assert.deepEqual(s.cache, {});
  assert.equal(s.token, "");
});
test("writes send explicit desired state once and never retry an uncertain response", async () => {
  let calls = 0;
  const client = new WidgetClient({
    state: state(),
    save: async () => {},
    fetcher: async (_url, options) => {
      calls++;
      assert.deepEqual(JSON.parse(options.body), {
        source: "capture",
        id: "a",
        done: true,
      });
      throw Error("response lost");
    },
  });
  await assert.rejects(client.complete("capture", "a", true));
  assert.equal(calls, 1);
});
test("rejects unknown origins and prevents token transmission to them", async () => {
  let calls = 0;
  const client = new WidgetClient({
    state: state(),
    save: async () => {},
    fetcher: async () => {
      calls++;
    },
  });
  await assert.rejects(
    client.claim("valid-code-that-is-long", "https://attacker.example"),
  );
  assert.equal(calls, 0);
});
test("failed recording leaves the stable retry id with the caller", async () => {
  const bodies = [];
  const client = new WidgetClient({
    state: state(),
    save: async () => {},
    fetcher: async (_url, options) => {
      bodies.push(JSON.parse(options.body));
      return new Response("{}", { status: bodies.length === 1 ? 503 : 200 });
    },
  });
  await assert.rejects(client.capture("stable-id", "기록"));
  await client.capture("stable-id", "기록");
  assert.equal(bodies[0].id, bodies[1].id);
});
test("an old account feed can never overwrite a newly paired account", async () => {
  const s = state();
  let respond;
  const client = new WidgetClient({
    state: s,
    save: async () => {},
    fetcher: () => new Promise((resolve) => (respond = resolve)),
  });
  const pending = client.feed("day", "2026-11-16");
  s.token = "new-account-token";
  s.cache = {};
  respond(Response.json({ events: [{ title: "old private event" }] }));
  const result = await pending;
  assert.equal(result.stale, true);
  assert.equal(result.events, undefined);
  assert.deepEqual(s.cache, {});
});
test("a delayed old-token rejection never disconnects a new account", async () => {
  const s = state();
  let respond;
  const client = new WidgetClient({
    state: s,
    save: async () => {},
    fetcher: () => new Promise((resolve) => (respond = resolve)),
  });
  const pending = client.feed("day", "2026-11-16");
  s.token = "new-account-token";
  respond(new Response("{}", { status: 401 }));
  assert.equal((await pending).stale, true);
  assert.equal(s.token, "new-account-token");
});
test("a delayed completion never changes a newly paired account cache", async () => {
  const s = state();
  let respond;
  const client = new WidgetClient({
    state: s,
    save: async () => {},
    fetcher: () => new Promise((resolve) => (respond = resolve)),
  });
  const pending = client.complete("capture", "same-id", true);
  s.token = "new";
  s.cache = { today: { captures: [{ id: "same-id", text: "new account" }] } };
  respond(Response.json({ ok: true }));
  assert.equal((await pending).stale, true);
  assert.equal(s.cache.today.captures.length, 1);
});
