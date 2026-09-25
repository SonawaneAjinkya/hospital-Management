// Shared API client for the Hospital Management frontend.
// Talks to the FastAPI backend (api/main.py). Change API_BASE if you run
// the API somewhere other than localhost:8000.
const API_BASE = "http://localhost:8000";

async function apiRequest(path, { method = "GET", body = null, params = null } = {}) {
  let url = API_BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== null && v !== undefined)
    ).toString();
    if (qs) url += "?" + qs;
  }

  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, opts);
  } catch (err) {
    throw new Error(
      "Couldn't reach the API at " + API_BASE + ". Is the FastAPI server running? (" + err.message + ")"
    );
  }

  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* empty body */
  }

  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

const api = {
  get: (path, params) => apiRequest(path, { method: "GET", params }),
  post: (path, body) => apiRequest(path, { method: "POST", body }),
  del: (path, body) => apiRequest(path, { method: "DELETE", body }),
};

// ---- current-user (session) helpers ----
const Session = {
  save(user) {
    localStorage.setItem("hms_user", JSON.stringify(user));
  },
  get() {
    const raw = localStorage.getItem("hms_user");
    return raw ? JSON.parse(raw) : null;
  },
  clear() {
    localStorage.removeItem("hms_user");
  },
  requireLogin() {
    const user = Session.get();
    if (!user) {
      window.location.href = "index.html";
      return null;
    }
    return user;
  },
};

function fmtErr(err) {
  return err && err.message ? err.message : String(err);
}
