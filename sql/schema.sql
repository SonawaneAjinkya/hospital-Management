-- ============================================
-- Hospital Management Analytics System
-- Database Schema (SQLite/PostgreSQL compatible)
-- ============================================

DROP TABLE IF EXISTS admissions;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS beds;
DROP TABLE IF EXISTS staff;
DROP TABLE IF EXISTS staff_shifts;
DROP TABLE IF EXISTS medicines;
DROP TABLE IF EXISTS medicine_transactions;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------
-- PATIENTS
-- ---------------------------------------------
CREATE TABLE patients (
    patient_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    age             INTEGER CHECK (age >= 0 AND age <= 120),
    gender          TEXT CHECK (gender IN ('M', 'F', 'Other')),
    disease         TEXT,
    admission_date  DATE,
    discharge_date  DATE
);

-- ---------------------------------------------
-- BEDS
-- ---------------------------------------------
CREATE TABLE beds (
    bed_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ward            TEXT NOT NULL,          -- e.g. ICU, General, Pediatric, Maternity
    status          TEXT CHECK (status IN ('occupied', 'vacant', 'maintenance')) DEFAULT 'vacant',
    patient_id      INTEGER,                -- NULL if vacant
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- ---------------------------------------------
-- ADMISSIONS (bridge table: links patients <-> beds over time)
-- ---------------------------------------------
CREATE TABLE admissions (
    admission_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL,
    bed_id          INTEGER NOT NULL,
    admission_date  DATE NOT NULL,
    discharge_date  DATE,                   -- NULL = still admitted
    admitted_by     INTEGER,                -- users.user_id who processed the admission
    discharged_by   INTEGER,                -- users.user_id who processed the discharge
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (bed_id) REFERENCES beds(bed_id)
);

-- ---------------------------------------------
-- STAFF
-- ---------------------------------------------
CREATE TABLE staff (
    staff_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    role            TEXT CHECK (role IN ('Doctor', 'Nurse', 'Technician', 'Admin', 'Support')),
    department      TEXT,
    shift_start     TIME,
    shift_end       TIME
);

-- ---------------------------------------------
-- STAFF_SHIFTS (actual shift log, separate from default schedule)
-- ---------------------------------------------
CREATE TABLE staff_shifts (
    shift_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        INTEGER NOT NULL,
    shift_date      DATE NOT NULL,
    shift_start     TIME NOT NULL,
    shift_end       TIME NOT NULL,
    ward            TEXT,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
);

-- ---------------------------------------------
-- MEDICINES
-- ---------------------------------------------
CREATE TABLE medicines (
    med_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT,
    stock           INTEGER DEFAULT 0,
    reorder_level   INTEGER DEFAULT 20,
    expiry_date     DATE,
    unit_price      REAL
);

-- ---------------------------------------------
-- MEDICINE_TRANSACTIONS (stock in/out log, needed for real trend analysis)
-- ---------------------------------------------
CREATE TABLE medicine_transactions (
    txn_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    med_id          INTEGER NOT NULL,
    txn_type        TEXT CHECK (txn_type IN ('restock', 'dispense', 'discard_expired')),
    quantity        INTEGER NOT NULL,
    txn_date        DATE NOT NULL,
    performed_by    INTEGER,                -- users.user_id who logged this transaction
    FOREIGN KEY (med_id) REFERENCES medicines(med_id)
);

-- ---------------------------------------------
-- USERS (role-based access: receptionist / medical_staff / admin)
-- ---------------------------------------------
CREATE TABLE users (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    salt            TEXT NOT NULL,
    role            TEXT CHECK (role IN ('receptionist', 'medical_staff', 'admin')) NOT NULL,
    full_name       TEXT,
    active          INTEGER DEFAULT 1,     -- 0 = disabled login
    created_at      DATE DEFAULT (DATE('now'))
);

-- ---------------------------------------------
-- INDEXES (for query performance at real-world scale)
-- ---------------------------------------------
CREATE INDEX idx_patients_admission ON patients(admission_date);
CREATE INDEX idx_admissions_dates ON admissions(admission_date, discharge_date);
CREATE INDEX idx_beds_status ON beds(status);
CREATE INDEX idx_medicines_expiry ON medicines(expiry_date);
CREATE INDEX idx_shifts_date ON staff_shifts(shift_date);
CREATE INDEX idx_users_username ON users(username);
