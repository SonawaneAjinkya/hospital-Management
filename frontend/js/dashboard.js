const WARDS = ["General", "ICU", "Surgical", "Pediatric", "Maternity", "Emergency"];

const TABS = [
  { id: "overview", label: "Overview", roles: ["receptionist", "medical_staff", "admin"], load: loadOverview },
  { id: "patients", label: "Patients & Beds", roles: ["receptionist", "admin"], load: loadPatientsTab },
  { id: "medicines", label: "Medicines", roles: ["medical_staff", "admin"], load: loadMedicinesTab },
  { id: "beds", label: "Manage Beds", roles: ["admin"], load: loadBedsTab },
  { id: "staff", label: "Staff Scheduling", roles: ["admin"], load: null },
  { id: "forecast", label: "Bed Forecast", roles: ["admin"], load: null },
  { id: "users", label: "Users", roles: ["admin"], load: loadUsersTab },
];

function init() {
  document.getElementById("who-text").innerHTML =
    `<b>${user.full_name || user.username}</b> (${user.role})`;
  document.getElementById("logout-btn").addEventListener("click", () => {
    Session.clear();
    window.location.href = "index.html";
  });

  const tabsEl = document.getElementById("tabs");
  const visibleTabs = TABS.filter((t) => t.roles.includes(user.role));
  visibleTabs.forEach((t, i) => {
    const btn = document.createElement("button");
    btn.className = "tab-btn" + (i === 0 ? " active" : "");
    btn.textContent = t.label;
    btn.addEventListener("click", () => showTab(t.id));
    btn.dataset.tab = t.id;
    tabsEl.appendChild(btn);
  });

  if (visibleTabs[0]) showTab(visibleTabs[0].id);
  wireForms();
}

function showTab(tabId) {
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
  const panel = document.getElementById("panel-" + tabId);
  if (panel) panel.classList.add("active");

  const tab = TABS.find((t) => t.id === tabId);
  if (tab && tab.load) tab.load();
}

// ---------------------------------------------------------------
// OVERVIEW
// ---------------------------------------------------------------
async function loadOverview() {
  const statsEl = document.getElementById("occupancy-stats");
  const tableEl = document.getElementById("ward-summary-table");
  try {
    const occ = await api.get("/occupancy");
    statsEl.innerHTML = `
      <div class="stat"><div class="num">${occ.total_beds}</div><div class="label">Total Beds</div></div>
      <div class="stat occupied"><div class="num">${occ.occupied}</div><div class="label">Occupied</div></div>
      <div class="stat vacant"><div class="num">${occ.vacant}</div><div class="label">Vacant</div></div>
      <div class="stat maintenance"><div class="num">${occ.maintenance}</div><div class="label">Maintenance</div></div>
      <div class="stat"><div class="num">${occ.overall_occupancy_pct}%</div><div class="label">Occupancy</div></div>
    `;
  } catch (err) {
    statsEl.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }

  try {
    const wards = await api.get("/beds/summary");
    tableEl.innerHTML = renderWardTable(wards);
  } catch (err) {
    tableEl.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }
}

function renderWardTable(wards) {
  if (!wards.length) return `<p class="muted">No wards yet.</p>`;
  const rows = wards
    .map(
      (w) => `<tr>
        <td>${w.ward}</td><td>${w.total}</td>
        <td><span class="badge occupied">${w.occupied} occupied</span></td>
        <td><span class="badge vacant">${w.vacant} vacant</span></td>
        <td><span class="badge maintenance">${w.maintenance} maint.</span></td>
      </tr>`
    )
    .join("");
  return `<table><thead><tr><th>Ward</th><th>Total</th><th>Occupied</th><th>Vacant</th><th>Maintenance</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ---------------------------------------------------------------
// PATIENTS
// ---------------------------------------------------------------
async function loadPatientsTab() {
  const sel = document.getElementById("admit-ward-select");
  sel.innerHTML = WARDS.map((w) => `<option>${w}</option>`).join("");

  const tableEl = document.getElementById("patients-ward-table");
  try {
    const wards = await api.get("/beds/summary");
    tableEl.innerHTML = renderWardTable(wards);
  } catch (err) {
    tableEl.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }
}

// ---------------------------------------------------------------
// MEDICINES
// ---------------------------------------------------------------
async function loadMedicinesTab() {
  const el = document.getElementById("med-alerts");
  try {
    const alerts = await api.get("/medicine_alerts");
    el.innerHTML = renderMedAlerts(alerts);
  } catch (err) {
    el.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }
}

function renderMedAlerts(alerts) {
  const section = (title, rows, cols) => {
    if (!rows.length) return `<p class="muted">${title}: none.</p>`;
    const head = cols.map((c) => `<th>${c}</th>`).join("");
    const body = rows
      .map((r) => `<tr>${cols.map((c) => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`)
      .join("");
    return `<h3 style="font-size:0.9rem;margin:16px 0 6px;">${title}</h3>
      <table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  };
  return (
    section("Low Stock", alerts.low_stock, ["name", "stock", "reorder_level"]) +
    section("Expiring Soon", alerts.expiring_soon, ["name", "expiry_date", "stock"]) +
    section("Already Expired", alerts.already_expired, ["name", "expiry_date", "stock"]) +
    section("Unusual Consumption", alerts.unusual_consumption, ["name", "total_dispensed", "avg_dispense_qty"])
  );
}

// ---------------------------------------------------------------
// BEDS (admin)
// ---------------------------------------------------------------
async function loadBedsTab() {
  const el = document.getElementById("bed-manage-table");
  try {
    const wards = await api.get("/beds/summary");
    el.innerHTML = renderBedManageTable(wards);
    wireSetTotalButtons();
  } catch (err) {
    el.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }
}

function renderBedManageTable(wards) {
  const known = new Set(wards.map((w) => w.ward));
  const extraWards = WARDS.filter((w) => !known.has(w)).map((w) => ({ ward: w, total: 0, occupied: 0, vacant: 0, maintenance: 0 }));
  const all = [...wards, ...extraWards];
  const rows = all
    .map(
      (w) => `<tr>
        <td>${w.ward}</td>
        <td>${w.total}</td>
        <td><span class="badge occupied">${w.occupied}</span></td>
        <td><span class="badge vacant">${w.vacant}</span></td>
        <td><span class="badge maintenance">${w.maintenance}</span></td>
        <td>
          <div class="row-inline">
            <input type="number" min="0" value="${w.total}" data-ward="${w.ward}" class="set-total-input" />
            <button class="secondary set-total-btn" data-ward="${w.ward}">Save</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
  return `<table>
    <thead><tr><th>Ward</th><th>Total</th><th>Occ.</th><th>Vac.</th><th>Maint.</th><th>Set total beds</th></tr></thead>
    <tbody>${rows}</tbody>
  </table><div id="set-total-msg" style="margin-top:10px;"></div>`;
}

function wireSetTotalButtons() {
  document.querySelectorAll(".set-total-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ward = btn.dataset.ward;
      const input = document.querySelector(`.set-total-input[data-ward="${ward}"]`);
      const total_beds = parseInt(input.value, 10);
      const msgEl = document.getElementById("set-total-msg");
      btn.disabled = true;
      try {
        const res = await api.post("/beds/set_total", { ward, total_beds, admin_user_id: user.user_id });
        msgEl.innerHTML = `<div class="success-box">${ward} set to ${res.total} beds (${res.occupied} occupied, ${res.vacant} vacant, ${res.maintenance} maintenance).</div>`;
        loadBedsTab();
      } catch (err) {
        msgEl.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
      } finally {
        btn.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------
// USERS (admin)
// ---------------------------------------------------------------
async function loadUsersTab() {
  const el = document.getElementById("users-table");
  try {
    const users = await api.get("/users", { admin_user_id: user.user_id });
    el.innerHTML = renderUsersTable(users);
    wireUserToggleButtons();
  } catch (err) {
    el.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
  }
}

function renderUsersTable(users) {
  if (!users.length) return `<p class="muted">No users yet.</p>`;
  const rows = users
    .map(
      (u) => `<tr>
        <td>${u.user_id}</td><td>${u.username}</td><td>${u.full_name}</td>
        <td><span class="badge ${u.role}">${u.role}</span></td>
        <td><span class="badge ${u.active ? "active-yes" : "active-no"}">${u.active ? "active" : "disabled"}</span></td>
        <td><button class="secondary toggle-active-btn" data-username="${u.username}" data-active="${u.active}">
          ${u.active ? "Disable" : "Enable"}
        </button></td>
      </tr>`
    )
    .join("");
  return `<table><thead><tr><th>ID</th><th>Username</th><th>Full name</th><th>Role</th><th>Status</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
}

function wireUserToggleButtons() {
  document.querySelectorAll(".toggle-active-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const username = btn.dataset.username;
      const nowActive = btn.dataset.active === "true";
      btn.disabled = true;
      try {
        await api.post(`/users/${username}/active`, { active: !nowActive, admin_user_id: user.user_id });
        loadUsersTab();
      } catch (err) {
        alert(fmtErr(err));
        btn.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------
// FORMS
// ---------------------------------------------------------------
function wireForms() {
  bindForm("admit-form", "admit-msg", async (fd) => {
    return api.post("/patients", {
      name: fd.get("name"),
      age: parseInt(fd.get("age"), 10),
      gender: fd.get("gender"),
      disease: fd.get("disease"),
      ward: fd.get("ward"),
      admitted_by: user.user_id,
    });
  }, (res) => `Admitted. Patient #${res.patient_id} → bed #${res.bed_id} (${res.ward}).`, loadPatientsTab);

  bindForm("discharge-form", "discharge-msg", async (fd) => {
    return api.post("/patients/discharge", {
      patient_id: parseInt(fd.get("patient_id"), 10),
      discharged_by: user.user_id,
    });
  }, (res) => `Discharged patient #${res.patient_id}, freed bed #${res.bed_id_freed}.`, loadPatientsTab);

  bindForm("restock-form", "restock-msg", async (fd) => {
    return api.post("/medicines/restock", {
      med_id: parseInt(fd.get("med_id"), 10),
      quantity: parseInt(fd.get("quantity"), 10),
      performed_by: user.user_id,
    });
  }, (res) => `New stock for med #${res.med_id}: ${res.new_stock}.`, loadMedicinesTab);

  bindForm("dispense-form", "dispense-msg", async (fd) => {
    return api.post("/medicines/dispense", {
      med_id: parseInt(fd.get("med_id"), 10),
      quantity: parseInt(fd.get("quantity"), 10),
      performed_by: user.user_id,
    });
  }, (res) => `Dispensed. Remaining stock for med #${res.med_id}: ${res.new_stock}.`, loadMedicinesTab);

  bindForm("add-med-form", "add-med-msg", async (fd) => {
    return api.post("/medicines", {
      name: fd.get("name"),
      category: fd.get("category"),
      stock: parseInt(fd.get("stock"), 10),
      reorder_level: parseInt(fd.get("reorder_level"), 10),
      expiry_date: fd.get("expiry_date"),
      unit_price: parseFloat(fd.get("unit_price")),
    });
  }, (res) => `Added medicine #${res.med_id} (${res.name}), stock ${res.stock}.`, loadMedicinesTab);

  bindForm("add-bed-form", "add-bed-msg", async (fd) => {
    return api.post("/beds", { ward: fd.get("ward"), status: fd.get("status"), admin_user_id: user.user_id });
  }, (res) => `Added bed #${res.bed_id} to ${res.ward} (${res.status}).`, loadBedsTab);

  bindForm("remove-bed-form", "remove-bed-msg", async (fd) => {
    return api.del(`/beds/${parseInt(fd.get("bed_id"), 10)}`, { admin_user_id: user.user_id });
  }, (res) => `Removed bed #${res.bed_id} from ${res.ward}.`, loadBedsTab);

  bindForm("create-user-form", "create-user-msg", async (fd) => {
    return api.post("/users", {
      username: fd.get("username"),
      password: fd.get("password"),
      full_name: fd.get("full_name"),
      role: fd.get("role"),
      admin_user_id: user.user_id,
    });
  }, (res) => `Created user "${res.username}" (${res.role}).`, loadUsersTab);

  document.getElementById("load-schedule-btn").addEventListener("click", async () => {
    const out = document.getElementById("schedule-output");
    out.innerHTML = `<div class="loading">Generating…</div>`;
    try {
      const res = await api.get("/schedule_staff");
      const rows = res.assignments
        .map((a) => `<tr>${Object.values(a).map((v) => `<td>${v}</td>`).join("")}</tr>`)
        .join("");
      const head = res.assignments[0] ? Object.keys(res.assignments[0]).map((k) => `<th>${k}</th>`).join("") : "";
      out.innerHTML = `
        <p class="muted">Required staff: ${res.total_staff_required} · Available: ${res.total_staff_available}</p>
        <table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
    } catch (err) {
      out.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
    }
  });

  document.getElementById("load-forecast-btn").addEventListener("click", async () => {
    const out = document.getElementById("forecast-output");
    const days = parseInt(document.getElementById("forecast-days").value, 10) || 7;
    out.innerHTML = `<div class="loading">Forecasting…</div>`;
    try {
      const res = await api.get("/predict_beds", { days });
      const rows = res.map((r) => `<tr><td>${r.date}</td><td>${r.predicted_admissions}</td></tr>`).join("");
      out.innerHTML = `<table><thead><tr><th>Date</th><th>Predicted Admissions</th></tr></thead><tbody>${rows}</tbody></table>`;
    } catch (err) {
      out.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
    }
  });
}

// Run last, now that TABS and every function above it are fully defined.
const user = Session.requireLogin();
if (user) init();

function bindForm(formId, msgId, submitFn, successMsgFn, refreshFn) {
  const form = document.getElementById(formId);
  const msgEl = document.getElementById(msgId);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msgEl.innerHTML = "";
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    try {
      const res = await submitFn(new FormData(form));
      msgEl.innerHTML = `<div class="success-box">${successMsgFn(res)}</div>`;
      form.reset();
      if (refreshFn) refreshFn();
    } catch (err) {
      msgEl.innerHTML = `<div class="error-box">${fmtErr(err)}</div>`;
    } finally {
      btn.disabled = false;
    }
  });
}
