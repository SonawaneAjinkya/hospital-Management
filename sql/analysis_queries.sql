-- ============================================
-- Hospital Analytics — Core Query Library
-- ============================================

-- 1. Current bed occupancy rate (overall)
SELECT
    ROUND(100.0 * SUM(CASE WHEN status = 'occupied' THEN 1 ELSE 0 END) / COUNT(*), 2) AS occupancy_rate_pct,
    SUM(CASE WHEN status = 'occupied' THEN 1 ELSE 0 END) AS occupied,
    SUM(CASE WHEN status = 'vacant' THEN 1 ELSE 0 END) AS vacant,
    SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance,
    COUNT(*) AS total_beds
FROM beds;

-- 2. Occupancy rate by ward
SELECT
    ward,
    COUNT(*) AS total_beds,
    SUM(CASE WHEN status = 'occupied' THEN 1 ELSE 0 END) AS occupied,
    ROUND(100.0 * SUM(CASE WHEN status = 'occupied' THEN 1 ELSE 0 END) / COUNT(*), 2) AS occupancy_rate_pct
FROM beds
GROUP BY ward
ORDER BY occupancy_rate_pct DESC;

-- 3. Medicines expiring within the next 30 days (reorder/discard alert)
SELECT med_id, name, stock, expiry_date,
       JULIANDAY(expiry_date) - JULIANDAY('now') AS days_to_expiry
FROM medicines
WHERE JULIANDAY(expiry_date) - JULIANDAY('now') BETWEEN 0 AND 30
ORDER BY expiry_date ASC;

-- 4. Already-expired stock still on shelves (compliance risk)
SELECT med_id, name, stock, expiry_date
FROM medicines
WHERE expiry_date < DATE('now')
ORDER BY expiry_date ASC;

-- 5. Medicines below reorder level (low-stock alert)
SELECT med_id, name, stock, reorder_level
FROM medicines
WHERE stock <= reorder_level
ORDER BY stock ASC;

-- 6. Daily admissions trend (last 30 days)
SELECT admission_date, COUNT(*) AS admissions
FROM admissions
WHERE admission_date >= DATE('now', '-30 days')
GROUP BY admission_date
ORDER BY admission_date;

-- 7. Average length of stay by disease
SELECT disease,
       ROUND(AVG(JULIANDAY(discharge_date) - JULIANDAY(admission_date)), 1) AS avg_stay_days,
       COUNT(*) AS patient_count
FROM patients
WHERE discharge_date IS NOT NULL
GROUP BY disease
ORDER BY avg_stay_days DESC;

-- 8. Staff-to-patient ratio per ward per day (last 7 days)
SELECT s.shift_date, s.ward, COUNT(DISTINCT s.staff_id) AS staff_on_duty
FROM staff_shifts s
WHERE s.shift_date >= DATE('now', '-7 days')
GROUP BY s.shift_date, s.ward
ORDER BY s.shift_date, s.ward;

-- 9. Top 5 most dispensed medicines (last 30 days)
SELECT m.name, SUM(t.quantity) AS total_dispensed
FROM medicine_transactions t
JOIN medicines m ON t.med_id = m.med_id
WHERE t.txn_type = 'dispense' AND t.txn_date >= DATE('now', '-30 days')
GROUP BY m.name
ORDER BY total_dispensed DESC
LIMIT 5;

-- 10. Currently admitted patients with bed & ward info
SELECT p.patient_id, p.name, p.disease, b.ward, b.bed_id, p.admission_date
FROM patients p
JOIN admissions a ON p.patient_id = a.patient_id
JOIN beds b ON a.bed_id = b.bed_id
WHERE a.discharge_date IS NULL
ORDER BY p.admission_date;
