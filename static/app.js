const { createClient } = supabase;
const client = createClient(
  "https://lzukvxxpukvdxguascav.supabase.co",
  "sb_publishable_phg0GoZ76kfbQbutCBJxWQ_Hkco9CKM"
);

const state = { user: null, profile: null, requests: [], notice: "", error: "" };
const app = document.querySelector("#app");
const statuses = ["New", "In Review", "Approved", "Rejected"];
const priorities = ["Low", "Medium", "High", "Critical"];

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function notice() {
  if (!state.notice && !state.error) return "";
  const message = state.error || state.notice;
  return `<p class="notice ${state.error ? "error" : ""}">${escapeHtml(message)}</p>`;
}

function date(value) {
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function go(route) {
  location.hash = route;
}

async function loadData() {
  let { data: profile, error: profileError } = await client.from("profiles").select("id, name, role, email").maybeSingle();
  if (profileError && profileError.code !== "PGRST116") throw profileError;
  if (!profile) {
    const { data, error } = await client.from("profiles").insert({
      id: state.user.id,
      name: state.user.user_metadata.name,
      email: state.user.email,
      role: state.user.user_metadata.role,
    }).select("id, name, role, email").single();
    if (error) throw error;
    profile = data;
  }
  state.profile = profile;
  const { data, error } = await client.from("change_requests").select("*").order("created_at", { ascending: false });
  if (error) throw error;
  state.requests = data;
}

function shell(content) {
  app.innerHTML = `<header class="topbar"><a class="brand" href="#dashboard"><span class="brand-mark">A</span><span>APM <b>Change Control</b></span></a><nav><span class="identity"><strong>${escapeHtml(state.profile.name)}</strong><small>${escapeHtml(state.profile.role)}</small></span><button class="nav-button" data-route="account" type="button">Password</button><button class="nav-button" data-action="logout" type="button">Sign out</button></nav></header>${content}`;
}

function renderAuth() {
  app.innerHTML = `<main class="auth-shell"><section class="auth-context"><div class="auth-brand"><span class="brand-mark">A</span> APM Change Control</div><div><p class="eyebrow">Engineering change control</p><h1>Every signal change,<br>clearly handed over.</h1><p>One shared register for developer requests and tester decisions.</p></div><div class="context-line"><span></span> Requirements &nbsp; Signals &nbsp; Validation</div></section><section class="auth-panel"><div class="auth-form">${notice()}<div id="auth-form"></div></div></section></main>`;
  renderLogin();
}

function renderLogin() {
  document.querySelector("#auth-form").innerHTML = `<p class="eyebrow">Welcome back</p><h2>Sign in to APM Change Control</h2><p class="muted">Use your registered project credentials.</p><form class="form-stack" data-form="login"><label>Email address<input type="email" name="email" required autofocus placeholder="name@company.com"></label><label>Password<input type="password" name="password" required placeholder="Enter your password"></label><button class="button primary wide" type="submit">Sign in</button></form><p class="auth-switch">New to APM Change Control? <a href="#register">Create an account</a></p>`;
}

function renderRegister() {
  app.innerHTML = `<main class="auth-shell"><section class="auth-context"><div class="auth-brand"><span class="brand-mark">A</span> APM Change Control</div><div><p class="eyebrow">Engineering change control</p><h1>Every signal change,<br>clearly handed over.</h1><p>One shared register for developer requests and tester decisions.</p></div></section><section class="auth-panel"><div class="auth-form">${notice()}<p class="eyebrow">New account</p><h2>Join the project</h2><p class="muted">Choose the role that matches your work.</p><form class="form-stack" data-form="register"><label>Full name<input name="name" required placeholder="Your full name"></label><label>Work email<input type="email" name="email" required placeholder="name@company.com"></label><label>Role<select name="role" required><option value="developer">Developer</option><option value="tester">Tester</option></select></label><label>Password<input type="password" name="password" minlength="8" required placeholder="At least 8 characters"></label><button class="button primary wide" type="submit">Create account</button></form><p class="auth-switch"><a href="#login">Back to sign in</a></p></div></section></main>`;
}

function renderDashboard() {
  const counts = Object.fromEntries(statuses.map((status) => [status, state.requests.filter((item) => item.status === status).length]));
  const rows = state.requests.map((item) => `<tr><td><div class="request-id"><span>#</span><strong>${escapeHtml(item.requirement_signal_id)}</strong></div></td><td><div class="function-cell"><strong>${escapeHtml(item.function_name)}</strong><small>${escapeHtml(item.reason)}</small></div></td><td>${escapeHtml(item.developer_name)}</td><td>${escapeHtml(item.tester_name)}</td><td><span class="priority ${item.priority.toLowerCase()}">${item.priority}</span></td><td><span class="status ${item.status.toLowerCase().replace(" ", "-")}"><i></i>${item.status}</span></td><td>${date(item.created_at)}</td><td><button class="row-link" data-route="request/${item.id}" aria-label="Open request" type="button">&rarr;</button></td></tr>`).join("");
  shell(`<main class="page"><div class="page-heading dashboard-heading"><div><p class="eyebrow">${escapeHtml(state.profile.role)} workspace</p><h1>Change control overview</h1><p class="muted">Monitor all organization requirement and signal changes from submission through validation.</p></div>${state.profile.role === "developer" ? '<button class="button primary" data-route="new" type="button">+ New request</button>' : ""}</div>${notice()}<section class="metrics"><div class="metric primary-metric"><span class="metric-icon">#</span><div><small>Total requests</small><strong>${state.requests.length}</strong><em>All tracked changes</em></div></div><div class="metric"><span class="metric-icon new-icon">N</span><div><small>Awaiting review</small><strong>${counts.New}</strong><em>New submissions</em></div></div><div class="metric"><span class="metric-icon review-icon">R</span><div><small>In review</small><strong>${counts["In Review"]}</strong><em>Testing in progress</em></div></div><div class="metric"><span class="metric-icon approved-icon">+</span><div><small>Approved</small><strong>${counts.Approved}</strong><em>Validated changes</em></div></div></section><section class="table-section"><div class="section-title"><div><p class="eyebrow">Live register</p><h2>Recent change requests</h2></div><span class="record-count">${state.requests.length} records</span></div>${rows ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Function</th><th>Developer</th><th>Tester</th><th>Priority</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty"><h3>No requests yet</h3><p>Create the first shared change request.</p></div>'}</section></main>`);
}

async function requestForm(item = null) {
  const { data: testers, error } = await client.from("profiles").select("id, name, email").eq("role", "tester").order("name");
  if (error) throw error;
  const testerOptions = testers.map((tester) => `<option value="${tester.id}" ${item?.tester_id === tester.id ? "selected" : ""}>${escapeHtml(tester.name)} (${escapeHtml(tester.email)})</option>`).join("");
  shell(`<main class="page narrow"><button class="back nav-button" data-route="dashboard" type="button">&larr; Back to requests</button><div class="page-heading"><div><p class="eyebrow">Developer submission</p><h1>${item ? "Edit change request" : "New change request"}</h1><p class="muted">Record the change and assign the responsible tester.</p></div></div>${notice()}<form class="request-form" data-form="request" data-id="${item?.id || ""}"><section><div class="section-number">01</div><div class="form-content"><h2>Change reference</h2><div class="field-grid"><label>Requirement / Signal ID<input name="requirement_signal_id" required value="${escapeHtml(item?.requirement_signal_id)}"></label><label>Function name<input name="function_name" required value="${escapeHtml(item?.function_name)}"></label></div><div class="comparison-inputs"><label class="value-field previous">Previous requirement / signal<textarea name="previous_value" rows="6" required>${escapeHtml(item?.previous_value)}</textarea></label><div class="compare-arrow">&rarr;</div><label class="value-field updated">New updated requirement / signal<textarea name="new_value" rows="6" required>${escapeHtml(item?.new_value)}</textarea></label></div></div></section><section><div class="section-number">02</div><div class="form-content"><h2>Tester assignment</h2><label>Tester<select name="tester_id" required><option value="">Select tester</option>${testerOptions}</select></label></div></section><section><div class="section-number">03</div><div class="form-content"><h2>Change context</h2><label>Reason for change<textarea name="reason" rows="5" required>${escapeHtml(item?.reason)}</textarea></label><label>Priority<select name="priority">${priorities.map((priority) => `<option ${item?.priority === priority || (!item && priority === "Medium") ? "selected" : ""}>${priority}</option>`).join("")}</select></label></div></section><div class="form-actions"><button class="button secondary" data-route="dashboard" type="button">Cancel</button><button class="button primary" type="submit">${item ? "Save changes" : "Submit request"}</button></div></form></main>`);
}

function renderDetail(item) {
  const isOwner = state.profile.role === "developer" && item.developer_id === state.user.id;
  const isTester = state.profile.role === "tester" && item.tester_id === state.user.id;
  const outlook = `https://outlook.office.com/mail/deeplink/compose?to=${encodeURIComponent(item.tester_email)}&subject=${encodeURIComponent(`[${item.priority}] APM Change Control request ${item.requirement_signal_id}`)}&body=${encodeURIComponent(`Hello ${item.tester_name},\n\n${item.developer_name} submitted a change for testing.\n\nOpen request: ${location.href}`)}`;
  shell(`<main class="page narrow"><button class="back nav-button" data-route="dashboard" type="button">&larr; Back to requests</button><div class="detail-heading"><div><div class="detail-meta"><span class="priority ${item.priority.toLowerCase()}">${item.priority}</span><span class="status">${item.status}</span></div><h1>${escapeHtml(item.requirement_signal_id)}</h1><p>${escapeHtml(item.function_name)}</p></div><div class="detail-actions">${isOwner ? `<button class="button secondary" data-route="edit/${item.id}" type="button">Edit request</button><button class="button danger" data-action="delete" data-id="${item.id}" type="button">Delete</button>` : ""}<a class="button outlook" href="${outlook}" target="_blank" rel="noopener">Open in Outlook</a></div></div>${notice()}<div class="detail-layout"><section class="detail-main"><div><p class="eyebrow">Change comparison</p><div class="comparison-view"><article class="comparison-card previous"><header><span>-</span><div><small>Previous</small><strong>Current definition</strong></div></header><pre>${escapeHtml(item.previous_value)}</pre></article><article class="comparison-card updated"><header><span>+</span><div><small>Updated</small><strong>Proposed definition</strong></div></header><pre>${escapeHtml(item.new_value)}</pre></article></div><div class="reason-block"><p class="eyebrow">Reason for change</p><p class="reason">${escapeHtml(item.reason)}</p></div></div>${isTester ? `<form class="review-form" data-form="status" data-id="${item.id}"><label>Testing decision<select name="status">${statuses.map((status) => `<option ${item.status === status ? "selected" : ""}>${status}</option>`).join("")}</select></label><button class="button primary" type="submit">Update status</button></form>` : ""}</section><aside class="detail-side"><h2>Handoff details</h2><dl><dt>Developer</dt><dd>${escapeHtml(item.developer_name)}</dd><dt>Tester</dt><dd>${escapeHtml(item.tester_name)}<small>${escapeHtml(item.tester_email)}</small></dd><dt>Created</dt><dd>${date(item.created_at)}</dd></dl></aside></div></main>`);
}

function renderAccount() {
  shell(`<main class="page narrow"><button class="back nav-button" data-route="dashboard" type="button">&larr; Back to dashboard</button><section class="detail-main account-form"><div><p class="eyebrow">Account security</p><h1>Set a new password</h1><p class="muted">Your new password must contain at least eight characters.</p></div>${notice()}<form class="form-stack" data-form="password"><label>New password<input type="password" name="password" minlength="8" required autofocus></label><button class="button primary" type="submit">Update password</button></form></section></main>`);
}

async function render() {
  if (!state.user) return location.hash === "#register" ? renderRegister() : renderAuth();
  try { await loadData(); } catch (error) {
    await client.auth.signOut();
    state.user = null;
    state.error = error.message;
    return location.hash === "#register" ? renderRegister() : renderAuth();
  }
  const route = location.hash.replace(/^#/, "") || "dashboard";
  if (route === "new") return requestForm();
  if (route.startsWith("edit/")) return requestForm(state.requests.find((item) => item.id === route.slice(5)));
  if (route.startsWith("request/")) return renderDetail(state.requests.find((item) => item.id === route.slice(8)) || state.requests[0]);
  if (route === "account") return renderAccount();
  renderDashboard();
}

async function submitForm(event) {
  event.preventDefault();
  const form = event.target;
  const values = Object.fromEntries(new FormData(form));
  state.error = "";
  try {
    if (form.dataset.form === "login") {
      const { error } = await client.auth.signInWithPassword(values);
      if (error) throw error;
      state.notice = "Signed in.";
    } else if (form.dataset.form === "register") {
      const { error } = await client.auth.signUp({ email: values.email, password: values.password, options: { data: { name: values.name, role: values.role } } });
      if (error) throw error;
      state.notice = "Account created. Check your email to confirm it, then sign in.";
      go("login");
    } else if (form.dataset.form === "request") {
      const payload = form.dataset.id ? { ...values, request_id: form.dataset.id } : values;
      const { error } = await client.rpc(form.dataset.id ? "update_change_request" : "create_change_request", payload);
      if (error) throw error;
      state.notice = form.dataset.id ? "Request updated." : "Request created.";
      go("dashboard");
    } else if (form.dataset.form === "status") {
      const { error } = await client.rpc("set_request_status", { request_id: form.dataset.id, next_status: values.status });
      if (error) throw error;
      state.notice = "Request status updated.";
      go(`request/${form.dataset.id}`);
    } else if (form.dataset.form === "password") {
      const { error } = await client.auth.updateUser({ password: values.password });
      if (error) throw error;
      state.notice = "Password updated.";
      go("dashboard");
    }
  } catch (error) { state.error = error.message; }
  await render();
}

document.addEventListener("click", async (event) => {
  const route = event.target.closest("[data-route]");
  if (route) { go(route.dataset.route); return; }
  const action = event.target.closest("[data-action]");
  if (!action) return;
  if (action.dataset.action === "logout") await client.auth.signOut();
  if (action.dataset.action === "delete" && confirm("Delete this request? This cannot be undone.")) {
    const { error } = await client.rpc("delete_change_request", { request_id: action.dataset.id });
    if (error) state.error = error.message; else state.notice = "Request deleted.";
    go("dashboard");
  }
  await render();
});
document.addEventListener("submit", submitForm);
window.addEventListener("hashchange", render);
client.auth.onAuthStateChange((_event, session) => { state.user = session?.user || null; render(); });
client.auth.getSession().then(({ data }) => { state.user = data.session?.user || null; render(); });