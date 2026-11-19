const {
  app,
  BrowserWindow,
  ipcMain,
  safeStorage,
  shell,
  screen,
  protocol,
  net,
} = require("electron");
const path = require("node:path");
const fs = require("node:fs/promises");
const { pathToFileURL } = require("node:url");
const { WidgetClient, ORIGINS } = require("./client.cjs");
protocol.registerSchemesAsPrivileged([
  {
    scheme: "netaq-widget",
    privileges: { standard: true, secure: true, supportFetchAPI: true },
  },
]);
let win,
  state = {
    origin: ORIGINS[0],
    token: "",
    cache: {},
    bounds: { width: 460, height: 620 },
    alwaysOnTop: false,
    startup: false,
    theme: "system",
  },
  client;
let saving = Promise.resolve();
async function encrypt(value) {
  return safeStorage.encryptStringAsync
    ? await safeStorage.encryptStringAsync(value)
    : safeStorage.encryptString(value);
}
async function decrypt(value) {
  return safeStorage.decryptStringAsync
    ? (await safeStorage.decryptStringAsync(value)).result
    : safeStorage.decryptString(value);
}
async function save() {
  const snapshot = JSON.stringify(state);
  saving = saving
    .catch(() => {})
    .then(async () => {
      const file = path.join(app.getPath("userData"), "widget.enc");
      const bytes = await encrypt(snapshot);
      await fs.writeFile(file + ".tmp", bytes, { mode: 0o600 });
      await fs.rename(file + ".tmp", file);
    });
  return saving;
}
function result(fn) {
  return async (event, ...args) => {
    if (
      event.sender !== win.webContents ||
      !event.senderFrame?.url.startsWith("netaq-widget://app/")
    )
      return { error: "잘못된 요청입니다." };
    try {
      return { value: await fn(...args) };
    } catch (e) {
      return { error: e.message || "처리하지 못했어요." };
    }
  };
}
async function main() {
  if (!app.requestSingleInstanceLock()) {
    app.quit();
    return;
  }
  await app.whenReady();
  const canEncrypt = safeStorage.isAsyncEncryptionAvailable
    ? await safeStorage.isAsyncEncryptionAvailable()
    : safeStorage.isEncryptionAvailable();
  if (!canEncrypt) {
    require("electron").dialog.showErrorBox(
      "NETAQ Widget",
      "보안 저장소를 사용할 수 없어요. Windows 계정에 다시 로그인한 후 실행해주세요.",
    );
    app.quit();
    return;
  }
  const root = path.join(__dirname, "ui");
  protocol.handle("netaq-widget", (request) => {
    const url = new URL(request.url);
    const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
    if (url.hostname !== "app" || !file.startsWith(root + path.sep))
      return new Response("", { status: 404 });
    return net.fetch(pathToFileURL(file).toString());
  });
  try {
    state = {
      ...state,
      ...JSON.parse(
        await decrypt(
          await fs.readFile(path.join(app.getPath("userData"), "widget.enc")),
        ),
      ),
    };
  } catch {}
  if (!ORIGINS.includes(state.origin)) {
    state.origin = ORIGINS[0];
    state.token = "";
    state.cache = {};
  }
  client = new WidgetClient({ state, save });
  const b = state.bounds || {};
  const options = {
    width: Math.max(340, Math.min(b.width || 460, 1200)),
    height: Math.max(360, Math.min(b.height || 620, 1200)),
  };
  if (
    Number.isFinite(b.x) &&
    Number.isFinite(b.y) &&
    screen
      .getAllDisplays()
      .some(
        (d) =>
          b.x >= d.workArea.x &&
          b.x < d.workArea.x + d.workArea.width - 80 &&
          b.y >= d.workArea.y &&
          b.y < d.workArea.y + d.workArea.height - 80,
      )
  ) {
    options.x = b.x;
    options.y = b.y;
  }
  win = new BrowserWindow({
    ...options,
    minWidth: 340,
    minHeight: 360,
    title: "NETAQ Widget",
    frame: false,
    backgroundColor: "#ffffff",
    show: false,
    alwaysOnTop: !!state.alwaysOnTop,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event) => event.preventDefault());
  win.webContents.session.setPermissionRequestHandler(
    (_wc, _permission, callback) => callback(false),
  );
  let timer;
  for (const event of ["resize", "move"])
    win.on(event, () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.bounds = win.getBounds();
        void save();
      }, 500);
    });
  win.on("close", () => {
    clearTimeout(timer);
    state.bounds = win.getBounds();
  });
  let quitting = false;
  app.on("before-quit", (event) => {
    if (quitting) return;
    event.preventDefault();
    save().finally(() => {
      quitting = true;
      app.quit();
    });
  });
  ipcMain.handle(
    "widget:state",
    result(() => ({
      connected: !!state.token,
      origin: state.origin,
      alwaysOnTop: state.alwaysOnTop,
      startup: state.startup,
      theme: state.theme,
      draft: state.draft || null,
      origins: ORIGINS,
    })),
  );
  ipcMain.handle(
    "widget:claim",
    result((code, origin) => client.claim(code, origin)),
  );
  ipcMain.handle(
    "widget:feed",
    result((view, anchor) => client.feed(view, anchor)),
  );
  ipcMain.handle(
    "widget:complete",
    result((source, id, done) => client.complete(source, id, done)),
  );
  ipcMain.handle(
    "widget:capture",
    result((id, text) => client.capture(id, text)),
  );
  ipcMain.handle(
    "widget:draft",
    result(async (draft) => {
      if (
        draft !== null &&
        (!draft ||
          typeof draft.text !== "string" ||
          draft.text.length > 2000 ||
          typeof draft.id !== "string")
      )
        throw new Error("기록을 확인해주세요.");
      state.draft = draft;
      await save();
      return true;
    }),
  );
  ipcMain.handle(
    "widget:disconnect",
    result(() => client.disconnect()),
  );
  ipcMain.handle(
    "widget:settings",
    result(async (value) => {
      if (typeof value?.alwaysOnTop === "boolean") {
        state.alwaysOnTop = value.alwaysOnTop;
        win.setAlwaysOnTop(value.alwaysOnTop);
      }
      if (typeof value?.startup === "boolean") {
        state.startup = value.startup;
        app.setLoginItemSettings({ openAtLogin: value.startup });
      }
      if (["system", "light", "dark"].includes(value?.theme))
        state.theme = value.theme;
      await save();
      return true;
    }),
  );
  ipcMain.handle(
    "widget:open",
    result(async (route) => {
      if (
        typeof route !== "string" ||
        !route.startsWith("/personal-project/calendar") ||
        route.includes("\\") ||
        /[\r\n]/.test(route)
      )
        throw new Error("잘못된 주소입니다.");
      const url = new URL(route, state.origin);
      if (url.origin !== state.origin) throw new Error("잘못된 주소입니다.");
      await shell.openExternal(url.href);
      return true;
    }),
  );
  ipcMain.handle(
    "widget:window",
    result(async (action) => {
      if (action === "minimize") win.minimize();
      else if (action === "close") {
        await save();
        win.close();
      }
      return true;
    }),
  );
  app.on("second-instance", () => {
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
  });
  await win.loadURL("netaq-widget://app/index.html");
  win.show();
}
app.on("window-all-closed", () => app.quit());
main().catch((error) => {
  require("electron").dialog.showErrorBox("NETAQ Widget", error.message);
  app.quit();
});
