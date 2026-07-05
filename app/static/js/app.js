/* Stance Triage — Clinical AI Platform */

const state = {
  config: null,
  health: null,
  cases: [],
  filteredCases: [],
  history: [],
  stats: null,
  selectedCaseId: "",
  selectedIndex: -1,
  manualCounter: 0,
  clerk: null,
  lastResult: null,
};

const $ = (id) => document.getElementById(id);
const chat = $("chat");
const caseList = $("caseList");
const historyList = $("historyList");
const messageBox = $("message");
const sendBtn = $("send");
const caseSearch = $("caseSearch");

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.add("hidden"), 2800);
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("stance-theme", theme);
  $("themeBtn").textContent = theme === "dark" ? "Dark" : "Light";
}

function initTheme() {
  const saved = localStorage.getItem("stance-theme") || "dark";
  applyTheme(saved);
  $("themeBtn").onclick = () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.config?.auth_mode === "clerk" && state.clerk?.session) {
    const token = await state.clerk.session.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return fetch(path, { ...options, headers });
}

function isClerkEnabled() {
  return state.config?.auth_mode === "clerk" && state.config?.clerk_configured;
}

function isSignedIn() {
  return !isClerkEnabled() || Boolean(state.clerk?.user);
}

function updateAuthGate() {
  const requiresAuth = isClerkEnabled();
  const signedIn = isSignedIn();
  sendBtn.disabled = requiresAuth && !signedIn;
  messageBox.disabled = requiresAuth && !signedIn;
  if (requiresAuth && !signedIn) {
    messageBox.placeholder = "Sign in to run triage and access your history…";
  } else {
    messageBox.placeholder = "Describe symptoms or select a dataset case from the sidebar…";
  }
}

function renderAuthState() {
  const signedOut = $("authSignedOut");
  const signedIn = $("authSignedIn");
  const openAccess = $("authOpenAccess");
  if (!isClerkEnabled()) {
    signedOut.hidden = true;
    signedIn.hidden = true;
    openAccess.hidden = false;
    if (state.config?.auth_mode === "clerk") {
      openAccess.textContent = "auth misconfigured";
      openAccess.className = "pill warn";
    } else {
      openAccess.textContent = state.config?.auth_mode === "none" ? "open access" : state.config?.auth_mode || "open access";
      openAccess.className = "pill";
    }
    updateAuthGate();
    return;
  }
  openAccess.className = "pill";
  openAccess.hidden = true;
  const authed = Boolean(state.clerk?.user);
  signedOut.hidden = authed;
  signedIn.hidden = !authed;
  if (authed) {
    const user = state.clerk.user;
    $("authUserLabel").textContent = user.primaryEmailAddress?.emailAddress || user.username || "Signed in";
  }
  updateAuthGate();
}

async function refreshProtectedData() {
  if (!isSignedIn()) {
    state.history = [];
    state.stats = null;
    renderHistory();
    renderStats();
    return;
  }
  await loadHistory();
  await loadStats();
}

async function initClerk() {
  renderAuthState();
  if (!isClerkEnabled()) return;

  await new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js";
    script.async = true;
    script.crossOrigin = "anonymous";
    script.dataset.clerkPublishableKey = state.config.clerk_publishable_key;
    script.onload = resolve;
    script.onerror = () => reject(new Error("Failed to load Clerk"));
    document.head.appendChild(script);
  });

  state.clerk = window.Clerk;
  await state.clerk.load({
    signInUrl: "/",
    signUpUrl: "/",
    afterSignInUrl: "/",
    afterSignUpUrl: "/",
  });

  $("signInBtn").onclick = () => state.clerk.openSignIn();
  $("signUpBtn").onclick = () => state.clerk.openSignUp();

  if (state.clerk.user) {
    state.clerk.mountUserButton($("userButtonMount"), {
      appearance: { variables: { colorPrimary: "#6366f1" } },
    });
  }

  state.clerk.addListener(({ user, session }) => {
    if (user && !document.querySelector("#userButtonMount button")) {
      $("userButtonMount").innerHTML = "";
      state.clerk.mountUserButton($("userButtonMount"), {
        appearance: { variables: { colorPrimary: "#6366f1" } },
      });
    }
    if (!user) $("userButtonMount").innerHTML = "";
    renderAuthState();
    refreshProtectedData().catch(console.error);
  });

  renderAuthState();
  await refreshProtectedData();
}

async function loadConfig() {
  state.health = await (await fetch("/health")).json();
  state.config = await (await fetch("/config")).json();
  const dbClass = state.health.database_connected ? "ok" : "warn";
  $("statusPills").innerHTML = `
    <span class="pill">LLM · ${state.health.llm_provider}</span>
    <span class="pill">Search · ${state.health.search_provider}</span>
    <span class="pill ${dbClass}">DB · ${state.health.database}${state.health.database_connected ? " ✓" : ""}</span>
    <span class="pill">Auth · ${state.health.auth_mode}</span>`;
  await initClerk();
}

async function loadCases() {
  try {
    const res = await fetch("/cases");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.cases = data.cases || [];
    state.filteredCases = [...state.cases];
    $("caseCountBadge").textContent = state.cases.length;
    renderCases();
    updateCasePosition();
    if (state.cases.length) toast(`Loaded all ${state.cases.length} dataset cases`);
  } catch (err) {
    toast("Could not load cases — check network and refresh");
    $("caseCountBadge").textContent = "!";
    console.error("loadCases failed", err);
  }
}

function renderCases() {
  caseList.innerHTML = "";
  const q = caseSearch.value.toLowerCase();
  state.filteredCases = state.cases.filter(
    (c) => !q || c.patient_id.includes(q) || c.message.toLowerCase().includes(q)
  );
  state.filteredCases.forEach((c, idx) => {
    const item = el("div", `list-item${state.selectedCaseId === c.patient_id ? " active" : ""}`);
    item.dataset.index = String(idx);
    item.appendChild(el("div", "id", c.patient_id));
    item.appendChild(el("div", "preview", c.message));
    item.onclick = () => selectCase(c, idx);
    caseList.appendChild(item);
  });
  $("caseCountBadge").textContent = state.filteredCases.length === state.cases.length
    ? state.cases.length
    : `${state.filteredCases.length}/${state.cases.length}`;
}

function updateCasePosition() {
  const idx = state.filteredCases.findIndex((c) => c.patient_id === state.selectedCaseId);
  state.selectedIndex = idx;
  if (idx >= 0) {
    $("casePosition").textContent = `${idx + 1} / ${state.filteredCases.length}`;
  } else {
    $("casePosition").textContent = `— / ${state.filteredCases.length || state.cases.length}`;
  }
}

function selectCase(c, idx) {
  state.selectedCaseId = c.patient_id;
  state.selectedIndex = idx ?? state.filteredCases.findIndex((x) => x.patient_id === c.patient_id);
  messageBox.value = c.message;
  renderCases();
  updateCasePosition();
  messageBox.focus();
  const active = caseList.querySelector(".list-item.active");
  if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function navigateCase(delta) {
  if (!state.filteredCases.length) return;
  let idx = state.selectedIndex >= 0 ? state.selectedIndex + delta : (delta > 0 ? 0 : state.filteredCases.length - 1);
  if (idx < 0) idx = state.filteredCases.length - 1;
  if (idx >= state.filteredCases.length) idx = 0;
  selectCase(state.filteredCases[idx], idx);
}

async function loadHistory() {
  try {
    const res = await api("/history?limit=50");
    if (!res.ok) return;
    const data = await res.json();
    state.history = data.records || [];
    renderHistory();
  } catch { /* optional */ }
}

function renderHistory() {
  historyList.innerHTML = "";
  if (!state.history.length) {
    historyList.appendChild(el("div", "preview", "No triage runs recorded yet."));
    return;
  }
  state.history.forEach((r) => {
    const item = el("div", "list-item");
    const meta = el("div", "meta");
    meta.appendChild(el("span", `dot ${r.urgency_level}`));
    meta.appendChild(document.createTextNode(`${r.patient_id} · ${r.confidence}% · ${new Date(r.created_at).toLocaleString()}`));
    item.appendChild(el("div", "id", r.patient_id));
    item.appendChild(el("div", "preview", r.triage_decision));
    item.appendChild(meta);
    item.onclick = () => {
      state.selectedCaseId = r.patient_id;
      messageBox.value = r.message;
      showTab("cases");
      toast(`Loaded ${r.patient_id} from history`);
    };
    historyList.appendChild(item);
  });
}

async function loadStats() {
  try {
    const res = await api("/stats");
    if (!res.ok) return;
    state.stats = await res.json();
    renderStats();
  } catch { /* optional */ }
}

function renderStats() {
  const container = $("statsPanel");
  if (!state.stats) {
    container.innerHTML = `<p style="color:var(--muted);font-size:12px">Run triage to populate dashboard metrics.</p>`;
    return;
  }
  const by = state.stats.by_urgency || {};
  const total = state.stats.total || 0;
  const levels = ["emergency", "high", "moderate", "low"];
  const colors = { emergency: "#ef4444", high: "#f97316", moderate: "#eab308", low: "#22c55e" };
  container.innerHTML = `
    <div class="stat-grid">
      <div class="stat"><div class="label">Total runs</div><div class="value">${total}</div></div>
      <div class="stat"><div class="label">Cases loaded</div><div class="value">${state.cases.length}</div></div>
    </div>`;
  levels.forEach((level) => {
    const count = by[level] || 0;
    const pct = total ? Math.round((count / total) * 100) : 0;
    container.innerHTML += `
      <div class="urgency-bar">
        <div class="label"><span>${level}</span><span>${count}</span></div>
        <div class="bar"><i style="width:${pct}%;background:${colors[level]}"></i></div>
      </div>`;
  });
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("casesPanel").hidden = name !== "cases";
  $("historyPanel").hidden = name !== "history";
}

function clearHero() {
  chat.querySelector(".hero")?.remove();
}

function showHero() {
  if (chat.querySelector(".hero") || chat.querySelector(".card")) return;
  const hero = el("div", "hero");
  hero.innerHTML = `
    <h2>Clinical symptom triage</h2>
    <p>Select a case from the sidebar or enter symptoms directly. Each request is evaluated through a structured LangGraph pipeline with deterministic safety rules.</p>
    <div class="chips">
      <span class="chip" data-case="case_001">Chest pain</span>
      <span class="chip" data-case="case_002">Thunderclap headache</span>
      <span class="chip" data-case="case_025">Fish bone obstruction</span>
      <span class="chip" data-case="case_088">Ambiguous tremor</span>
    </div>`;
  hero.querySelectorAll(".chip").forEach((chip) => {
    chip.onclick = () => {
      const c = state.cases.find((x) => x.patient_id === chip.dataset.case);
      if (c) selectCase(c);
    };
  });
  chat.appendChild(hero);
}

function renderResult(payload, debug) {
  const triage = debug ? payload.triage : payload;
  const card = el("div", "card");
  const row = el("div", "row");
  row.appendChild(el("span", `badge b-${triage.urgency_level}`, triage.urgency_level));
  const bar = el("span", "confbar");
  const fill = el("i");
  fill.style.width = `${triage.confidence}%`;
  bar.appendChild(fill);
  row.appendChild(el("span", "conf", `confidence ${triage.confidence}/100`));
  row.appendChild(bar);
  card.appendChild(row);
  card.appendChild(el("div", "decision", triage.triage_decision));
  card.appendChild(el("div", "reasoning", triage.reasoning));
  if (triage.red_flags?.length) {
    const flags = el("div", "flags");
    triage.red_flags.forEach((f) => flags.appendChild(el("span", "flag", f)));
    card.appendChild(flags);
  }
  card.appendChild(el("div", "action", triage.recommended_action));
  const sources = el("div", "sources");
  if (triage.sources?.length) {
    triage.sources.forEach((u) => {
      const a = el("a", "", u);
      a.href = u;
      a.target = "_blank";
      sources.appendChild(a);
    });
  } else {
    sources.appendChild(el("div", "nosource", "No verified external source found."));
  }
  card.appendChild(sources);
  card.appendChild(el("div", "disc", triage.disclaimers.join(" ")));
  card.appendChild(el("div", "meta", `request ${triage.request_id} · recorded`));
  if (debug && payload.execution_trace) {
    const details = el("details", "trace");
    details.appendChild(el("summary", "", `execution trace · ${payload.execution_trace.length} nodes · ${payload.search_decision_reason || "n/a"}`));
    const table = el("table");
    table.innerHTML = "<tr><th>node</th><th>status</th><th>ms</th><th>retries</th><th>result</th></tr>";
    payload.execution_trace.forEach((t) => {
      const tr = el("tr");
      [t.node_name, t.status, t.latency_ms.toFixed(1), t.retry_count, t.result_summary].forEach((v) => tr.appendChild(el("td", "", String(v))));
      table.appendChild(tr);
    });
    details.appendChild(table);
    card.appendChild(details);
  }
  return card;
}

async function send() {
  const message = messageBox.value.trim();
  if (!message) return;
  if (isClerkEnabled() && !isSignedIn()) {
    toast("Sign in to run triage");
    state.clerk?.openSignIn();
    return;
  }
  const patientId = state.selectedCaseId || `manual_${String(++state.manualCounter).padStart(3, "0")}`;
  const debug = $("debugMode").checked;
  clearHero();
  const bubble = el("div", "msg-user");
  bubble.appendChild(el("span", "pid", patientId));
  bubble.appendChild(document.createTextNode(message));
  chat.appendChild(bubble);
  const thinking = el("div", "thinking", "Running 11-node LangGraph pipeline");
  chat.appendChild(thinking);
  chat.scrollTop = chat.scrollHeight;
  sendBtn.disabled = true;
  try {
    const res = await api(debug ? "/debug" : "/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, message }),
    });
    thinking.remove();
    if (!res.ok) {
      if (res.status === 401 && isClerkEnabled()) {
        toast("Session expired — sign in again");
        state.clerk?.openSignIn();
      }
      chat.appendChild(el("div", "err", `HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`));
    } else {
      const data = await res.json();
      state.lastResult = data;
      $("copyLast").disabled = false;
      chat.appendChild(renderResult(data, debug));
      await loadHistory();
      await loadStats();
      toast("Triage complete · result recorded");
    }
  } catch (err) {
    thinking.remove();
    chat.appendChild(el("div", "err", `Request failed: ${err}`));
  }
  sendBtn.disabled = false;
  chat.scrollTop = chat.scrollHeight;
}

function initGuide() {
  const modal = $("guideModal");
  $("guideBtn").onclick = () => modal.classList.remove("hidden");
  $("closeGuide").onclick = () => modal.classList.add("hidden");
  modal.querySelector(".modal-backdrop").onclick = () => modal.classList.add("hidden");
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    showTab(tab.dataset.tab);
    if (tab.dataset.tab === "history") loadHistory();
  };
});

caseSearch.oninput = () => { renderCases(); updateCasePosition(); };
$("prevCase").onclick = () => navigateCase(-1);
$("nextCase").onclick = () => navigateCase(1);
sendBtn.onclick = send;
$("clearChat").onclick = () => { chat.innerHTML = ""; showHero(); state.lastResult = null; $("copyLast").disabled = true; };
$("copyLast").onclick = () => {
  if (!state.lastResult) return;
  const json = JSON.stringify(state.lastResult.triage || state.lastResult, null, 2);
  navigator.clipboard.writeText(json).then(() => toast("JSON copied to clipboard"));
};
messageBox.onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
};

(async function boot() {
  initTheme();
  initGuide();
  showHero();
  await loadConfig();
  await loadCases();
  if (isSignedIn()) {
    await loadHistory();
    await loadStats();
  }
})();
