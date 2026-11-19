const $ = (id) => document.getElementById(id),
  api = window.netaq;
let view = "day",
  anchor = today(),
  busy = false,
  draftId = crypto.randomUUID(),
  feed = null;
function today() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}`;
}
function date(value) {
  return new Date(value + "T12:00:00");
}
function key(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function error(e) {
  $("error").textContent = e?.message || String(e);
}
function open(route) {
  void api.open(route).catch(error);
}
function connection(connected) {
  $("connection").hidden = connected;
  $("content").hidden = !connected;
  if (!connected) {
    $("events").replaceChildren();
    $("tasks").replaceChildren();
    $("memo").textContent = "";
    $("updated").textContent = "";
    $("capture").value = "";
    draftId = crypto.randomUUID();
    feed = null;
  }
}
function time(e) {
  if (e.taskUnplanned) return "날짜 미정";
  if (e.isAllDay) return "종일";
  const fmt = (x) =>
    new Date(x).toLocaleTimeString("ko-KR", {
      timeZone: "Asia/Seoul",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  return fmt(e.startTime) + (e.endTime ? "–" + fmt(e.endTime) : "");
}
function render(data) {
  feed = data;
  connection(true);
  $("date-title").textContent = date(anchor).toLocaleDateString(
    "ko-KR",
    view === "month"
      ? { year: "numeric", month: "long" }
      : { month: "long", day: "numeric", weekday: "long" },
  );
  for (const button of document.querySelectorAll("[data-view]"))
    button.setAttribute("aria-pressed", String(button.dataset.view === view));
  $("events").replaceChildren();
  $("month").hidden = view !== "month";
  if (view === "month") renderMonth(data.events || []);
  let events = view === "tasks" ? [] : data.events || [];
  if (view === "month")
    events = events.filter((e) => e.startTime?.slice(0, 10) === anchor);
  for (const event of events.slice(0, view === "week" ? 30 : 8)) {
    const row = el("button", undefined, "event");
    row.append(el("strong", event.title));
    row.append(
      el(
        "span",
        (view === "week"
          ? new Date(event.startTime).toLocaleDateString("ko-KR", {
              timeZone: "Asia/Seoul",
              month: "numeric",
              day: "numeric",
            }) + " · "
          : "") +
          time(event) +
          (event.location ? " · " + event.location : ""),
      ),
    );
    row.onclick = () =>
      open(
        `/personal-project/calendar?event=${encodeURIComponent(event.id)}&date=${anchor}`,
      );
    $("events").append(row);
  }
  if (!events.length && view !== "tasks")
    $("events").append(
      el(
        "p",
        view === "month"
          ? "날짜를 눌러 일정을 확인하세요."
          : "예정된 일정이 없어요.",
        "empty",
      ),
    );
  $("tasks").replaceChildren();
  const tasks = view === "tasks" ? data.events || [] : data.tasks || [];
  for (const task of tasks.slice(0, 20))
    renderTask(
      "event",
      task.id,
      task.title,
      task.canEdit === false ||
        task.completionSource === "external" ||
        (task.taskAvailableFrom &&
          Date.parse(task.taskAvailableFrom) > Date.now()),
    );
  for (const task of (data.captures || []).slice(0, 20))
    renderTask("capture", task.id, task.text, false);
  if (!tasks.length && !(data.captures || []).length)
    $("tasks").append(el("p", "남은 할 일이 없어요.", "empty"));
  $("tasks-section").hidden = view === "week" || view === "month";
  $("memo-section").hidden = view !== "day";
  $("memo").textContent = data.note || "아직 메모가 없어요.";
  $("updated").textContent =
    (data.updatedAt
      ? new Date(data.updatedAt).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
        }) + " 업데이트"
      : "") + (data.cached ? " · 마지막으로 받은 내용" : "");
  if (data.error) $("error").textContent = data.error;
}
function renderTask(source, id, title, disabled) {
  const row = el("div", undefined, "task"),
    check = el("input"),
    label = el("label", title);
  check.type = "checkbox";
  check.id = `task-${source}-${id}`;
  check.setAttribute("aria-label", title + " 완료");
  check.disabled = !!disabled;
  label.htmlFor = check.id;
  row.append(check, label);
  check.onchange = async () => {
    check.disabled = true;
    $("error").textContent = "";
    try {
      const result = await api.complete(source, id, check.checked);
      if (result.stale) return;
      row.classList.toggle("done", check.checked);
      $("status").textContent = "완료 상태를 저장했어요";
    } catch (e) {
      check.checked = !check.checked;
      error(e);
    } finally {
      check.disabled = !!disabled;
    }
  };
  $("tasks").append(row);
}
function renderMonth(events) {
  const root = $("month");
  root.replaceChildren();
  for (const n of ["일", "월", "화", "수", "목", "금", "토"])
    root.append(el("span", n));
  const first = date(anchor);
  first.setDate(1);
  const month = first.getMonth();
  first.setDate(first.getDate() - first.getDay());
  for (let i = 0; i < 42; i++) {
    const d = new Date(first);
    d.setDate(first.getDate() + i);
    const value = key(d),
      button = el("button", String(d.getDate()));
    button.classList.toggle("outside", d.getMonth() !== month);
    button.classList.toggle("selected", value === anchor);
    button.classList.toggle(
      "dot",
      events.some(
        (e) =>
          e.startTime?.slice(0, 10) <= value &&
          (e.endTime || e.startTime)?.slice(0, 10) >= value,
      ),
    );
    button.setAttribute("aria-label", value + " 일정");
    button.onclick = () => {
      anchor = value;
      view = "day";
      void refresh();
    };
    root.append(button);
  }
}
async function refresh() {
  if (busy) return;
  busy = true;
  $("refresh").disabled = true;
  $("error").textContent = "";
  $("status").textContent = "새로고침 중…";
  try {
    const data = await api.feed(view, anchor);
    if (data.stale) {
      setTimeout(refresh, 0);
      return;
    }
    if (!data.connected) {
      connection(false);
      if (data.error) $("error").textContent = data.error;
    } else render(data);
    $("status").textContent = "";
  } catch (e) {
    error(e);
    $("status").textContent = "";
  } finally {
    busy = false;
    $("refresh").disabled = false;
  }
}
for (const button of document.querySelectorAll("[data-view]"))
  button.onclick = () => {
    view = button.dataset.view;
    void refresh();
  };
for (const [id, delta] of [
  ["previous", -1],
  ["next", 1],
])
  $(id).onclick = () => {
    const d = date(anchor);
    if (view === "month") {
      d.setDate(1);
      d.setMonth(d.getMonth() + delta);
    } else d.setDate(d.getDate() + delta * (view === "week" ? 7 : 1));
    anchor = key(d);
    void refresh();
  };
$("today").onclick = () => {
  anchor = today();
  void refresh();
};
$("refresh").onclick = refresh;
$("pair-page").onclick = () => open("/personal-project/calendar/widgets");
$("open-calendar").onclick = () =>
  open("/personal-project/calendar?date=" + anchor);
$("open-note").onclick = () =>
  open("/personal-project/calendar/today?date=" + anchor + "#daily-note");
$("settings-toggle").onclick = () => {
  $("settings").hidden = !$("settings").hidden;
};
$("minimize").onclick = () => void api.window("minimize");
$("close").onclick = () => void api.window("close");
for (const [id, setting] of [
  ["top", "alwaysOnTop"],
  ["startup", "startup"],
])
  $(id).onchange = async () => {
    const value = $(id).checked;
    try {
      await api.settings({ [setting]: value });
      $("status").textContent = "설정을 저장했어요";
    } catch (e) {
      $(id).checked = !value;
      error(e);
    }
  };
$("theme").onchange = async () => {
  try {
    await api.settings({ theme: $("theme").value });
    document.documentElement.dataset.theme = $("theme").value;
  } catch (e) {
    error(e);
  }
};
$("connect-form").onsubmit = async (event) => {
  event.preventDefault();
  $("connect").disabled = true;
  $("error").textContent = "";
  try {
    await api.claim($("code").value, $("origin").value);
    $("code").value = "";
    await refresh();
  } catch (e) {
    error(e);
  } finally {
    $("connect").disabled = false;
  }
};
$("capture").oninput = () => {
  void api
    .draft(
      $("capture").value ? { id: draftId, text: $("capture").value } : null,
    )
    .catch(error);
};
$("capture-form").onsubmit = async (event) => {
  event.preventDefault();
  if (!$("capture").value.trim()) return;
  $("capture-save").disabled = true;
  $("capture").disabled = true;
  $("error").textContent = "";
  try {
    const result = await api.capture(draftId, $("capture").value);
    if (result.stale) return;
    $("capture").value = "";
    draftId = crypto.randomUUID();
    await api.draft(null);
    $("status").textContent = "정리함에 기록했어요";
  } catch (e) {
    error(e);
  } finally {
    $("capture-save").disabled = false;
    $("capture").disabled = false;
  }
};
$("disconnect").onclick = async () => {
  if (
    $("capture").value &&
    !confirm("입력 중인 기록을 지우고 연결을 해제할까요?")
  )
    return;
  try {
    await api.disconnect();
    $("capture").value = "";
    connection(false);
    $("settings").hidden = true;
    $("status").textContent = "이 기기의 연결을 해제했어요";
  } catch (e) {
    error(e);
    connection(false);
  }
};
window.addEventListener("focus", () => {
  if (!$("content").hidden) void refresh();
});
setInterval(() => {
  if (!document.hidden && !$("content").hidden) void refresh();
}, 60000);
void (async () => {
  try {
    const state = await api.state();
    for (const origin of state.origins) {
      const option = el("option", origin);
      option.value = origin;
      $("origin").append(option);
    }
    $("origin").value = state.origin;
    $("top").checked = state.alwaysOnTop;
    $("startup").checked = state.startup;
    $("theme").value = state.theme;
    document.documentElement.dataset.theme = state.theme;
    if (state.draft) {
      draftId = state.draft.id;
      $("capture").value = state.draft.text;
    }
    connection(state.connected);
    if (state.connected) await refresh();
  } catch (e) {
    connection(false);
    error(e);
  }
})();
