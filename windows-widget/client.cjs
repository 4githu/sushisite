const ORIGINS = [
  "https://netaq.chobab.app",
  "https://calendar.chobab.app",
  "https://calender.chobab.app",
  "https://chobab.app",
];
const VIEWS = new Set(["day", "week", "month", "tasks"]);
class WidgetClient {
  constructor({ state, save, fetcher = fetch }) {
    this.state = state;
    this.save = save;
    this.fetcher = fetcher;
  }
  async call(
    path,
    body,
    method = body ? "POST" : "GET",
    token = this.state.token,
  ) {
    if (!ORIGINS.includes(this.state.origin))
      throw new Error("서비스 주소를 확인해주세요.");
    let response;
    try {
      response = await this.fetcher(
        `${this.state.origin}/api/personal/calendar/widget/${path}`,
        {
          method,
          redirect: "error",
          signal: AbortSignal.timeout(12000),
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(body ? { "Content-Type": "application/json" } : {}),
          },
          ...(body ? { body: JSON.stringify(body) } : {}),
        },
      );
    } catch {
      throw new Error("인터넷 연결을 확인하고 다시 시도해주세요.");
    }
    if (response.status === 401) {
      if (token === this.state.token) {
        this.state.token = "";
        this.state.cache = {};
        this.state.draft = null;
        await this.save();
      }
      const e = new Error("계정을 다시 연결해주세요.");
      e.auth = true;
      throw e;
    }
    if (!response.ok) {
      const value = await response.json().catch(() => null);
      throw new Error(
        typeof value?.detail === "string"
          ? value.detail
          : "요청을 처리하지 못했어요. 다시 시도해주세요.",
      );
    }
    return response.status === 204 ? {} : response.json();
  }
  async claim(code, origin) {
    if (
      !ORIGINS.includes(origin) ||
      typeof code !== "string" ||
      code.trim().length < 16 ||
      code.length > 200
    )
      throw new Error("서비스와 연결 코드를 확인해주세요.");
    const previous = this.state.origin;
    this.state.origin = origin;
    try {
      const result = await this.call(
        "claim",
        { token: code.trim(), platform: "Windows" },
        "POST",
        "",
      );
      this.state.token = result.token;
      this.state.cache = {};
      this.state.draft = null;
      await this.save();
    } catch (e) {
      this.state.origin = previous;
      throw e;
    }
    return { connected: true };
  }
  async feed(view, anchor) {
    if (!VIEWS.has(view) || !/^\d{4}-\d{2}-\d{2}$/.test(anchor))
      throw new Error("날짜를 확인해주세요.");
    if (!this.state.token) return { connected: false };
    const key = `${view}:${anchor}`,
      credential = this.state.token;
    try {
      const data = await this.call(`feed?view=${view}&anchor=${anchor}`);
      if (credential !== this.state.token)
        return { connected: !!this.state.token, stale: true };
      this.state.cache = { [key]: data };
      await this.save();
      return { ...data, connected: true, cached: false };
    } catch (e) {
      if (credential !== this.state.token && this.state.token)
        return { connected: true, stale: true };
      if (e.auth) return { connected: false, error: e.message };
      const data = this.state.cache?.[key];
      if (data)
        return { ...data, connected: true, cached: true, error: e.message };
      throw e;
    }
  }
  async complete(source, id, done) {
    const credential = this.state.token;
    if (
      !["event", "capture"].includes(source) ||
      !["string", "number"].includes(typeof id) ||
      typeof done !== "boolean"
    )
      throw new Error("할 일을 확인해주세요.");
    await this.call("task", { source, id: String(id), done });
    if (credential !== this.state.token) return { ok: true, stale: true };
    if (done) {
      for (const data of Object.values(this.state.cache || {})) {
        if (source === "capture")
          data.captures = (data.captures || []).filter(
            (item) => String(item.id) !== String(id),
          );
        else {
          data.tasks = (data.tasks || []).filter(
            (item) => String(item.id) !== String(id),
          );
          data.events = (data.events || []).filter(
            (item) => String(item.id) !== String(id),
          );
        }
      }
    } else this.state.cache = {};
    await this.save();
    return { ok: true };
  }
  async capture(id, text) {
    if (
      typeof id !== "string" ||
      id.length > 200 ||
      typeof text !== "string" ||
      !text.trim() ||
      text.length > 2000
    )
      throw new Error("기록은 1~2,000자로 입력해주세요.");
    const credential = this.state.token;
    await this.call("capture", { id, text });
    return { ok: true, stale: credential !== this.state.token };
  }
  async disconnect() {
    try {
      if (this.state.token) await this.call("device", null, "DELETE");
    } finally {
      this.state.token = "";
      this.state.cache = {};
      this.state.draft = null;
      await this.save();
    }
    return { connected: false };
  }
}
module.exports = { WidgetClient, ORIGINS };
