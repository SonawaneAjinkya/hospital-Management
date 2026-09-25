// If already logged in, skip straight to the dashboard.
if (Session.get()) {
  window.location.href = "dashboard.html";
}

const form = document.getElementById("login-form");
const msg = document.getElementById("msg");
const btn = document.getElementById("login-btn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  msg.innerHTML = "";
  btn.disabled = true;
  btn.textContent = "Signing in…";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const user = await api.post("/login", { username, password });
    Session.save(user);
    window.location.href = "dashboard.html";
  } catch (err) {
    msg.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});
