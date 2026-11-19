// Isolated native-app fixture. Excluded from every distribution by build.files.
const electron = require("electron"),
  fs = require("node:fs"),
  os = require("node:os"),
  path = require("node:path");
const root = fs.mkdtempSync(path.join(os.tmpdir(), "netaq-widget-ui-"));
electron.app.setPath("userData", root);
electron.safeStorage.isAsyncEncryptionAvailable = async () => true;
electron.safeStorage.encryptStringAsync = async (value) => Buffer.from(value);
electron.safeStorage.decryptStringAsync = async (value) => ({
  result: value.toString(),
  shouldReEncrypt: false,
});
electron.app.setLoginItemSettings = () => {};
electron.shell.openExternal = async (url) => {
  global.widgetTestLinks.push(url);
};
global.widgetTestLinks = [];
global.widgetTestWrites = [];
global.widgetTestOffline = false;
global.widgetTestRevoked = false;
global.widgetTestFailCapture = false;
fs.writeFileSync(
  path.join(root, "widget.enc"),
  JSON.stringify({
    origin: "https://netaq.chobab.app",
    token: "isolated-test-token",
    cache: {},
    bounds: { width: 460, height: 700 },
    theme: "light",
  }),
);
global.fetch = async (url, options) => {
  if (global.widgetTestOffline) throw new Error("offline");
  if (global.widgetTestRevoked) return new Response("{}", { status: 401 });
  if (options.method === "POST") {
    const body = JSON.parse(options.body);
    global.widgetTestWrites.push({ path: new URL(url).pathname, body });
    if (url.endsWith("/capture") && global.widgetTestFailCapture) {
      global.widgetTestFailCapture = false;
      return new Response("{}", { status: 503 });
    }
    return Response.json({ ok: true, token: "new-test-token" });
  }
  return Response.json({
    events: [
      {
        id: 1,
        title: "생명과학 세미나",
        startTime: "2026-11-16T14:00:00+09:00",
        endTime: "2026-11-16T15:30:00+09:00",
        location: "자연과학관",
      },
    ],
    tasks: [{ id: 2, title: "자료 보내기", status: "todo", canEdit: true }],
    captures: [{ id: "c1", text: "실험 계획 정리" }],
    note: "- [x] 완료한 메모\n다음 실험 준비",
    date: "2026-11-16",
    updatedAt: "2026-11-16T01:00:00Z",
  });
};
require("../main.cjs");
