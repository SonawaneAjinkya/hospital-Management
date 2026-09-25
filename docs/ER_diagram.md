# Entity-Relationship Diagram

```mermaid
erDiagram
    PATIENTS ||--o{ ADMISSIONS : has
    BEDS ||--o{ ADMISSIONS : hosts
    STAFF ||--o{ STAFF_SHIFTS : works
    MEDICINES ||--o{ MEDICINE_TRANSACTIONS : logs

    PATIENTS {
        int patient_id PK
        string name
        int age
        string gender
        string disease
        date admission_date
        date discharge_date
    }

    BEDS {
        int bed_id PK
        string ward
        string status
        int patient_id FK
    }

    ADMISSIONS {
        int admission_id PK
        int patient_id FK
        int bed_id FK
        date admission_date
        date discharge_date
    }

    STAFF {
        int staff_id PK
        string name
        string role
        string department
        time shift_start
        time shift_end
    }

    STAFF_SHIFTS {
        int shift_id PK
        int staff_id FK
        date shift_date
        time shift_start
        time shift_end
        string ward
    }

    MEDICINES {
        int med_id PK
        string name
        string category
        int stock
        int reorder_level
        date expiry_date
        float unit_price
    }

    MEDICINE_TRANSACTIONS {
        int txn_id PK
        int med_id FK
        string txn_type
        int quantity
        date txn_date
    }
```

**Why `ADMISSIONS` exists separately from `PATIENTS`/`BEDS`:** a patient
can (in theory) be re-admitted, and a bed's occupancy history needs to be
queryable over time — not just "who's in it right now." `PATIENTS.admission_date`
/`discharge_date` covers the simple case; `ADMISSIONS` is the full history table
the analytics (occupancy trends, length-of-stay) actually query against.
