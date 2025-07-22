CREATE TABLE IF NOT EXISTS scored_loan_applications (
    application_id TEXT PRIMARY KEY,
    message_id               TEXT           NOT NULL,
    loan_amnt                INTEGER        NOT NULL,
    term                     INTEGER        NOT NULL,
    int_rate                 DECIMAL(5,4)   NOT NULL,
    installment              DECIMAL(10,2)  NOT NULL,
    emp_length               INTEGER        NOT NULL,
    annual_inc               DECIMAL(12,2)  NOT NULL,
    dti                      DECIMAL(5,4)   NOT NULL,
    addr_state               VARCHAR(2)     NOT NULL,
    credit_to_income_ratio   DECIMAL(10,4)   NOT NULL,
    is_self_employed         BOOLEAN        NOT NULL,
    loan_month               INTEGER        NOT NULL,
    is_long_term             BOOLEAN        NOT NULL,
    risk_score               DECIMAL(7,6)   NOT NULL,
    risk_level               VARCHAR(6)     GENERATED ALWAYS AS (
                              CASE
                                WHEN risk_score >= 0.75 THEN 'HIGH'
                                WHEN risk_score >= 0.35 THEN 'MEDIUM'
                                ELSE 'LOW'
                              END
                             ) STORED,
    processing_timestamp     TIMESTAMPTZ    NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_processing_timestamp
  ON scored_loan_applications(processing_timestamp);

CREATE INDEX IF NOT EXISTS idx_processing_date
  ON scored_loan_applications ((DATE(processing_timestamp)));

CREATE INDEX IF NOT EXISTS idx_addr_state
  ON scored_loan_applications(addr_state);

CREATE INDEX IF NOT EXISTS idx_state_ts
  ON scored_loan_applications(addr_state, processing_timestamp DESC);

