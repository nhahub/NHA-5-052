-- Control table for both ETL pipelines (data dictionary v4, Star_Schema note 2).   READY - no change needed.
-- Run ONCE in ecommerce_dw (DBeaver), right after 03_dwh/scripts/schema.sql.
-- The ETL never creates this table itself, so two runs cannot race to create it.
--
-- pipeline = 'prices_daily'        one row per daily price load (MongoDB -> fact_price_daily)
-- pipeline = 'orders_incremental'  one row per sales load (MySQL -> fact_sales)
-- A run that fails is recorded with status 'failed' and does NOT move the watermark.

CREATE TABLE IF NOT EXISTS etl_state (
    run_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline    VARCHAR(50)  NOT NULL,              -- 'prices_daily' or 'orders_incremental'
    batch_id    VARCHAR(25),                        -- snapshot date or purchase date(s) loaded, e.g. '2026-10-27'
    watermark   TIMESTAMP,                          -- prices: last snapshot date loaded; orders: highest order_purchase_ts loaded
    loaded_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    rows_in     INTEGER      NOT NULL DEFAULT 0,    -- rows read from the source
    rows_out    INTEGER      NOT NULL DEFAULT 0,    -- rows inserted into the fact table
    checksum    NUMERIC(16,2),                      -- prices: SUM(sale_price_egp); orders: SUM(line_total_egp) of the inserted rows
    status      VARCHAR(10)  NOT NULL CHECK (status IN ('success', 'failed', 'no_data')),
    message     TEXT
);

CREATE INDEX IF NOT EXISTS ix_etl_state_pipeline ON etl_state (pipeline, status, watermark);
