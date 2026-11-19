const $ = (id) => document.getElementById(id),
  api = window.netaq;
let view = "planning",
  anchor = today(),
  busy = false,
  draftId = crypto.randomUUID(),
  feed = null, restaurant = "", settingsOpen = false, connectedState = false;
function isNewerVersion(remote, current) {
  const parse = value => typeof value === "string" && /^\d+\.\d+\.\d+$/.test(value) ? value.split(".").map(Number) : null;
  const a=parse(remote), b=parse(current); if (!a || !b) return false;
  for (let i=0;i<3;i++) if (a[i] !== b[i]) return a[i] > b[i];
  return false;
}
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
  connectedState = connected;
  $("connection").hidden = connected || settingsOpen;
  $("content").hidden = !connected || settingsOpen;
  if (!connected) {
    $("events").replaceChildren();
    $("tasks").replaceChildren();
    $("memo").textContent = "";
    $("updated").hidden = view === "recent";
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
  $("content").dataset.view = view;
  $("meal-section").hidden = view !== "meal";
  $("recent-section").hidden = view !== "recent";
  $("plan-columns").hidden = view === "meal" || view === "recent";
  $("capture-form").hidden = ["meal", "recent", "week"].includes(view);
  $("open-calendar").hidden = view === "meal" || view === "recent";
  $("clock").hidden = true;
  updateClock();
  if (view === "meal") renderMeal(data);
  if (view === "recent") renderRecent(data);
  $("events").replaceChildren();
  $("events").classList.remove("timeline"); $("events").style.height="";
  document.querySelectorAll(".all-day-event").forEach(n=>n.remove());
  $("week-scroll").hidden = view !== "week";
  $("plan-columns").hidden = ["meal", "recent", "week"].includes(view);
  if (view === "week") renderWeek(data.events || []);
  $("month").hidden = view !== "month";
  if (view === "month") renderMonth(data.events || []);
  let events = ["tasks", "meal", "recent"].includes(view) ? [] : data.events || [];
  if (view === "month" || view === "week")
    events = events.filter((e) => e.startTime?.slice(0, 10) <= anchor && (e.endTime || e.startTime)?.slice(0, 10) >= anchor);
  if (view === "planning") renderTimeline(events);
  for (const event of (view === "planning" ? [] : events.slice(0, 30))) {
    const row = el("button", undefined, "event");
    row.dataset.start = event.startTime || "";
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
  if (view === "planning") updateClock();
  if (!events.length && !["planning", "tasks", "meal", "recent"].includes(view))
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
  $("tasks-section").hidden = view === "month";
  $("memo-section").hidden = view !== "day";
  $("memo").textContent = data.note || "아직 메모가 없어요.";
  $("updated").hidden = view === "recent";
  $("updated").textContent =
    (data.updatedAt
      ? new Date(data.updatedAt).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
        }) + " 업데이트"
      : "") + (data.cached ? " · 마지막으로 받은 내용" : "");
  if (data.error) $("error").textContent = data.error;
}

function renderTimeline(events) {
  const root=$("events"), start=Date.parse(anchor+"T08:00:00+09:00"), hourHeight=44, end=start+18*3600000;
  root.classList.add("timeline"); root.style.height=(18*hourHeight)+"px";
  for(let hour=0;hour<=18;hour++){const label=el("span",String((hour+8)%24).padStart(2,"0")+":00","hour-label");label.style.top=(hour*hourHeight)+"px";root.append(label);}
  const timed=events.filter(e=>!e.isAllDay && !e.timeUnspecified).map(e=>({event:e,from:Math.max(start,Date.parse(e.startTime)),to:Math.min(end,Date.parse(e.endTime || e.startTime)+(!e.endTime?1800000:0))})).filter(e=>Number.isFinite(e.from)&&e.to>e.from).sort((a,b)=>a.from-b.from);
  let group=[],lanes=[];const place=()=>{for(const item of group)item.lanes=lanes.length;};
  for(const item of timed){if(group.length && item.from>=Math.max(...lanes)){place();group=[];lanes=[];}let lane=lanes.findIndex(t=>t<=item.from);if(lane<0)lane=lanes.length;lanes[lane]=item.to;item.lane=lane;group.push(item);}if(group.length)place();
  for(const item of timed){const row=el("button",undefined,"event timeline-event");row.style.top=((item.from-start)/3600000*hourHeight)+"px";row.style.height=Math.max(16,(item.to-item.from)/3600000*hourHeight)+"px";row.style.left=`calc(52px + (100% - 52px) * ${item.lane/item.lanes})`;row.style.width=`calc((100% - 52px) / ${item.lanes} - 3px)`;row.append(el("strong",item.event.title),el("span",time(item.event)+(item.event.location?" · "+item.event.location:"")));row.onclick=()=>open(`/personal-project/calendar?event=${encodeURIComponent(item.event.id)}&date=${anchor}`);root.append(row);}
  for(const event of events.filter(e=>e.isAllDay || e.timeUnspecified)){const row=el("button",event.title+" · "+time(event),"all-day-event");row.onclick=()=>open(`/personal-project/calendar?event=${encodeURIComponent(event.id)}&date=${anchor}`);root.before(row);}
}
function updateClock() {
  const now = new Date();
  const clock = new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul",hour:"2-digit",minute:"2-digit",hour12:false}).format(now);
  $("clock").textContent = "현재 " + clock;
  $("events").querySelector(".now-line")?.remove();
  if (view !== "planning") return;
  const start=Date.parse(anchor+"T08:00:00+09:00"), offset=(now.getTime()-start)/3600000;
  if(offset<0 || offset>18)return;
  const line=el("div", undefined, "now-line");line.setAttribute("aria-label", "현재 " + clock);line.style.top=(offset*44)+"px";$("events").append(line);
}
function renderMeal(data) {
  const select=$("restaurant"), rows=data.restaurants || [];
  select.replaceChildren(); const empty=el("option","식당 선택"); empty.value=""; select.append(empty);
  for(const item of rows){const option=el("option",item.title);option.value=item.title;select.append(option);}
  select.value=restaurant;
  const hour=Number(new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Seoul",hour:"numeric",hourCycle:"h23"}).format(new Date()));
  const period=hour<10?"breakfast":hour<15?"lunch":"dinner";
  $("meal-title").textContent=period==="breakfast"?"아침":period==="lunch"?"점심":"저녁";
  const selected=rows.find(x=>x.title===restaurant);
  $("meal-menu").textContent=data.supported===false?"학교 식단을 지원하지 않아요.":!restaurant?"식당을 선택해주세요.":selected?.[period] || "제공되는 식단이 없어요.";
}
function renderRecent(data) {
  const root=$("recent-notes");root.replaceChildren();
  for(const note of data.notes || []) {const b=el("button",note.title || "제목 없는 노트","note-row");b.onclick=()=>open("/personal-project/notes?note="+encodeURIComponent(note.id));root.append(b);}
  if(!root.children.length) root.append(el("p","최근에 저장한 노트가 없어요.","empty"));
}
$("restaurant").onchange = async () => {restaurant=$("restaurant").value;try{await api.settings({mealRestaurant:restaurant});if(feed)renderMeal(feed);}catch(e){error(e);}};

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
function renderWeek(events) {
  const header=$("week-strip"), grid=$("week-timetable"), all=$("week-all-day");
  header.replaceChildren(el("span", "", "week-axis"));grid.replaceChildren();all.replaceChildren(el("span", "종일", "week-axis"));
  const first=date(anchor);first.setDate(first.getDate()-first.getDay());
  const labels=["일","월","화","수","목","금","토"], hourHeight=44;
  grid.style.height=18*hourHeight+"px";
  for(let hour=0;hour<=18;hour++){const label=el("span",String((hour+8)%24).padStart(2,"0")+":00","week-hour");label.style.top=(hour*hourHeight)+"px";grid.append(label);}
  const columns=el("div",undefined,"week-columns");grid.append(columns);
  for(let d=0;d<7;d++){
    const day=new Date(first);day.setDate(first.getDate()+d);const value=key(day);
    const button=el("button",undefined,"week-date");button.setAttribute("aria-label",value+" 일정");button.setAttribute("aria-pressed",String(value===today()));button.append(el("span",labels[d]),el("strong",String(day.getDate())));button.onclick=()=>{anchor=value;view="planning";void refresh()};header.append(button);
    const dayStart=Date.parse(value+"T00:00:00+09:00"),start=dayStart+8*3600000,end=start+18*3600000;
    const cell=el("div",undefined,"week-column"),allCell=el("div",undefined,"week-all-cell");columns.append(cell);all.append(allCell);
    for(const event of events.filter(e=>(e.isAllDay||e.timeUnspecified)&&Date.parse(e.startTime)<dayStart+86400000&&Date.parse(e.endTime || e.startTime)>=dayStart)){
      const pill=el("button",event.title,"week-all-event");pill.onclick=()=>open(`/personal-project/calendar?event=${encodeURIComponent(event.id)}&date=${value}`);allCell.append(pill);
    }
    const timed=events.filter(e=>!e.isAllDay&&!e.timeUnspecified).map(e=>({event:e,from:Math.max(start,Date.parse(e.startTime)),to:Math.min(end,Date.parse(e.endTime || e.startTime)+(!e.endTime?1800000:0))})).filter(e=>Number.isFinite(e.from)&&e.to>e.from).sort((a,b)=>a.from-b.from);
    // Assign lanes within each overlapping group so isolated events use the full column.
    let group=[],ends=[];const place=()=>{const n=ends.length;for(const e of group)e.lanes=n;};
    for(const item of timed){if(group.length && item.from>=Math.max(...ends)){place();group=[];ends=[];}let lane=ends.findIndex(t=>t<=item.from);if(lane<0)lane=ends.length;ends[lane]=item.to;item.lane=lane;group.push(item);}if(group.length)place();
    for(const item of timed){const event=el("button",undefined,"week-event");event.style.top=((item.from-start)/3600000*hourHeight)+"px";event.style.height=Math.max(16,(item.to-item.from)/3600000*hourHeight)+"px";event.style.left=(item.lane/item.lanes*100)+"%";event.style.width=(100/item.lanes)+"%";event.append(el("strong",item.event.title));event.setAttribute("aria-label",item.event.title+" "+time(item.event));event.onclick=()=>open(`/personal-project/calendar?event=${encodeURIComponent(item.event.id)}&date=${value}`);cell.append(event);}
    const now=Date.now();if(now>=start&&now<=end){const line=el("div",undefined,"week-now-line");line.style.top=((now-start)/3600000*hourHeight)+"px";cell.append(line);}
  }
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
    const dayEvents=events.filter(e=>e.startTime?.slice(0,10)<=value&&(e.endTime||e.startTime)?.slice(0,10)>=value);
    for(const event of dayEvents.slice(0,2))button.append(el("span",event.title,"month-event"));
    if(dayEvents.length>2)button.append(el("span","+"+(dayEvents.length-2),"month-more"));
    button.setAttribute("aria-label", value + " 일정 " + dayEvents.length + "개");
    button.onclick = () => { anchor=value; if(d.getMonth()!==month) void refresh(); else render(feed); };
    root.append(button);
  }
}
async function refresh() {
  if (busy) return;
  busy = true;
  $("refresh").disabled = true;
  $("error").textContent = "";
  $("status").textContent = "새로고침 중…";
  const requestedView = view, requestedAnchor = anchor;
  try {
    const cached = await api.cached(requestedView, requestedAnchor);
    if (cached?.connected && requestedView === view && requestedAnchor === anchor) render(cached);
    const data = await api.feed(requestedView, requestedAnchor);
    if (requestedView !== view || requestedAnchor !== anchor) { setTimeout(refresh, 0); return; }
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
function showSettings(open) {
  settingsOpen=open;
  $("settings").hidden=!open;
  $("content").hidden=open || !connectedState;
  $("connection").hidden=open || connectedState;
  $("settings-toggle").setAttribute("aria-expanded",String(open));
  if(open) $("settings-back").focus();
}
$("settings-toggle").onclick = () => showSettings(!settingsOpen);
$("settings-back").onclick = () => showSettings(false);
$("minimize").onclick = () => void api.window("minimize");
let attachedToDesktop = false;
async function syncDesktopState() {
  attachedToDesktop = Boolean((await api.desktopState()).attached);
  $("desktop-add").textContent = attachedToDesktop ? "위치 조정" : "바탕화면에 추가";
}
$("desktop-add").onclick = async () => {
  try {
    await syncDesktopState();
    if (attachedToDesktop) {
      await api.float();
      attachedToDesktop = false;
      $("desktop-add").textContent = "바탕화면에 추가";
      $("status").textContent = "창을 원하는 위치로 옮긴 뒤 바탕화면에 추가를 눌러주세요.";
    } else {
      await api.desktop();
      attachedToDesktop = true;
      $("desktop-add").textContent = "위치 조정";
      $("status").textContent = "위치를 바꾸려면 위치 조정을 눌러주세요.";
    }
  } catch(e) { error(e); }
};
// The wallpaper plugin forwards wheel input as synthetic events. Chromium
// does not perform default scrolling for untrusted events, so scroll the
// nearest scrollable area explicitly while preserving ordinary native wheels.
window.addEventListener("wheel", (event) => {
  if (event.isTrusted || event.defaultPrevented) return;
  let node = event.target instanceof Element ? event.target : document.documentElement;
  while (node && node !== document.documentElement) {
    const style = getComputedStyle(node);
    if ((/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight) ||
        (/(auto|scroll)/.test(style.overflowX) && node.scrollWidth > node.clientWidth)) {
      node.scrollBy(event.deltaX, event.deltaY); event.preventDefault(); return;
    }
    node = node.parentElement;
  }
  window.scrollBy(event.deltaX, event.deltaY);
  event.preventDefault();
}, {passive:false});
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
$("check-update").onclick = async () => {
  const button=$("check-update");button.disabled=true;$("error").textContent="";$("status").textContent="업데이트 확인 중…";
  try {const result=await api.update();$("status").textContent=result.installed?"업데이트를 설치하고 있어요.":"최신 버전이에요.";}
  catch(e){error(e);$("status").textContent="";} finally {button.disabled=false;}
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
    showSettings(false);
    $("status").textContent = "이 기기의 연결을 해제했어요";
  } catch (e) {
    error(e);
    connection(false);
  }
};
window.addEventListener("focus", () => {
  void syncDesktopState().catch(() => {});
  if (!$("content").hidden) void refresh();
});
setInterval(() => {
  updateClock();
  if (view === "meal" && feed) renderMeal(feed);
  if (!document.hidden && !$("content").hidden) void refresh();
}, 60000);
void (async () => {
  try {
    const state = await api.state();
    void syncDesktopState().catch(() => {});
    $("app-version").textContent = `위젯 버전 ${state.appVersion}`;
    for (const origin of state.origins) {
      const option = el("option", origin);
      option.value = origin;
      $("origin").append(option);
    }
    $("origin").value = state.origin;
    $("top").checked = state.alwaysOnTop;
    $("startup").checked = state.startup;
    restaurant = state.mealRestaurant || "";
    $("theme").value = state.theme;
    document.documentElement.dataset.theme = state.theme;
    if (state.draft) {
      draftId = state.draft.id;
      $("capture").value = state.draft.text;
    }
    connection(state.connected);
    if (state.connected) await refresh();
    void api.version().then(v=>{if(isNewerVersion(v?.windows?.version, state.appVersion)) $("check-update").textContent="새 버전 받기";}).catch(()=>{});
  } catch (e) {
    connection(false);
    error(e);
  }
})();
