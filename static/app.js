const config = window.SUPABASE_CONFIG;
const configured = config && !config.url.startsWith("PASTE_") && !config.anonKey.startsWith("PASTE_");
const notice = (message, error = false) => {
  document.querySelector("#notice").innerHTML = `<div class="flash${error ? " error" : ""}">${message}</div>`;
};

if (!configured) {
  notice("GitHub Pages is ready. Add your Supabase Project URL and publishable anon key in static/supabase-config.js.", true);
} else {
  const client = window.supabase.createClient(config.url, config.anonKey);
  let profile;
  let signUp = false;
  const authView = document.querySelector("#auth-view");
  const appView = document.querySelector("#app-view");
  const setAuthMode = () => {
    document.querySelector("#auth-title").textContent = signUp ? "Create your project account" : "Sign in to APM Change Control";
    document.querySelector("#auth-copy").textContent = signUp ? "Choose the workspace that matches your work." : "Use your registered project credentials.";
    document.querySelector("#name-field").hidden = !signUp;
    document.querySelector("#role-field").hidden = !signUp;
    document.querySelector("#auth-submit").textContent = signUp ? "Create account" : "Sign in";
    document.querySelector("#auth-toggle").textContent = signUp ? "Sign in" : "Create an account";
    document.querySelector("#auth-toggle-copy").textContent = signUp ? "if you already have an account." : "if you are new to the project.";
  };
  const format = (value) => new Date(value).toLocaleDateString();
  const escape = (value) => String(value ?? "").replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]);
  const loadRequests = async () => {
    const { data, error } = await client.from("app_change_requests").select("*").order("created_at", { ascending: false });
    if (error) return notice(error.message, true);
    document.querySelector("#count-total").textContent = data.length;
    document.querySelector("#count-new").textContent = data.filter((item) => item.status === "New").length;
    document.querySelector("#count-review").textContent = data.filter((item) => item.status === "In Review").length;
    document.querySelector("#count-approved").textContent = data.filter((item) => item.status === "Approved").length;
    document.querySelector("#record-count").textContent = `${data.length} records`;
    document.querySelector("#empty").hidden = data.length > 0;
    document.querySelector("#requests").innerHTML = data.map((item) => `<tr><td><strong>${escape(item.requirement_signal_id)}</strong></td><td>${escape(item.function_name)}</td><td>${escape(item.developer_name)}</td><td>${escape(item.tester_name)}</td><td><span class="priority ${item.priority.toLowerCase()}">${item.priority}</span></td><td><span class="status ${item.status.toLowerCase().replaceAll(" ", "-")}">${item.status}</span></td><td>${format(item.created_at)}</td><td>${profile.role === "tester" ? `<select class="status-update" data-id="${item.id}"><option ${item.status === "New" ? "selected" : ""}>New</option><option ${item.status === "In Review" ? "selected" : ""}>In Review</option><option ${item.status === "Approved" ? "selected" : ""}>Approved</option><option ${item.status === "Rejected" ? "selected" : ""}>Rejected</option></select>` : ""}</td></tr>`).join("");
    document.querySelectorAll(".status-update").forEach((input) => input.addEventListener("change", async () => {
      const { error: updateError } = await client.from("app_change_requests").update({ status: input.value, updated_at: new Date().toISOString() }).eq("id", input.dataset.id);
      if (updateError) notice(updateError.message, true); else loadRequests();
    }));
  };
  const showApp = async (user) => {
    const { data, error } = await client.from("app_profiles").select("*").eq("id", user.id).single();
    if (error) return notice("Your profile is not ready. Confirm your signup email, then sign in again.", true);
    profile = data;
    authView.hidden = true; appView.hidden = false; document.body.classList.remove("auth-page");
    document.querySelector("#identity").innerHTML = `<strong>${escape(profile.full_name)}</strong><small>${profile.role}</small>`;
    document.querySelector("#workspace-role").textContent = `${profile.role} workspace`;
    document.querySelector("#new-request").hidden = profile.role !== "developer";
    loadRequests();
  };
  document.querySelector("#auth-toggle").addEventListener("click", (event) => { event.preventDefault(); signUp = !signUp; setAuthMode(); });
  document.querySelector("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const email = document.querySelector("#email").value; const password = document.querySelector("#password").value;
    const result = signUp ? await client.auth.signUp({ email, password, options: { data: { full_name: document.querySelector("#name").value, role: document.querySelector("#role").value } } }) : await client.auth.signInWithPassword({ email, password });
    if (result.error) return notice(result.error.message, true);
    if (signUp && !result.data.session) return notice("Check your email to confirm your account, then sign in.");
    showApp(result.data.user);
  });
  document.querySelector("#forgot-password").addEventListener("click", async (event) => { event.preventDefault(); const email = document.querySelector("#email").value; if (!email) return notice("Enter your email address first.", true); const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo: window.location.href }); notice(error ? error.message : "Password reset email sent.", Boolean(error)); });
  document.querySelector("#logout").addEventListener("click", async () => { await client.auth.signOut(); window.location.reload(); });
  document.querySelector("#new-request").addEventListener("click", () => document.querySelector("#request-dialog").showModal());
  document.querySelector("#close-dialog").addEventListener("click", () => document.querySelector("#request-dialog").close());
  document.querySelector("#request-form").addEventListener("submit", async (event) => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); const { error } = await client.from("app_change_requests").insert({ ...values, developer_id: profile.id, developer_name: profile.full_name, tester_email: values.tester_email.toLowerCase() }); if (error) return notice(error.message, true); event.currentTarget.reset(); document.querySelector("#request-dialog").close(); notice("Request submitted."); loadRequests(); });
  client.auth.getSession().then(({ data }) => { if (data.session) showApp(data.session.user); });
}