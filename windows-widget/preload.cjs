const { contextBridge, ipcRenderer } = require("electron");
const invoke = async (name, ...args) => {
  const result = await ipcRenderer.invoke("widget:" + name, ...args);
  if (result.error) throw new Error(result.error);
  return result.value;
};
contextBridge.exposeInMainWorld(
  "netaq",
  Object.freeze({
    state: () => invoke("state"),
    claim: (code, origin) => invoke("claim", code, origin),
    feed: (view, date) => invoke("feed", view, date),
    complete: (source, id, done) => invoke("complete", source, id, done),
    capture: (id, text) => invoke("capture", id, text),
    draft: (value) => invoke("draft", value),
    disconnect: () => invoke("disconnect"),
    settings: (value) => invoke("settings", value),
    open: (route) => invoke("open", route),
    window: (action) => invoke("window", action),
  }),
);
