-- =============================================================================
-- BudgetBot — PostgreSQL Schema Initialization
-- =============================================================================
-- Idempotent: safe to re-run. Uses IF NOT EXISTS and DO $$ blocks.
-- Usage: psql -d budgetbot -f init_db.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Enum: transaction categories
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_enum') THEN
        CREATE TYPE category_enum AS ENUM (
            'Food', 'Transport', 'Shopping', 'Utilities', 'Entertainment',
            'Health', 'Subscriptions', 'Bills', 'Income', 'Transfer', 'Other'
        );
    ELSE
        -- Add any missing values (idempotent for existing DBs)
        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Subscriptions'; EXCEPTION WHEN duplicate_object THEN NULL; END;
        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Utilities';     EXCEPTION WHEN duplicate_object THEN NULL; END;
        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Bills';         EXCEPTION WHEN duplicate_object THEN NULL; END;
    END IF;
END
$$;

-- =============================================================================
-- Table 1: user
-- =============================================================================
CREATE TABLE IF NOT EXISTS "user" (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account     VARCHAR(255) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    budget      INTEGER DEFAULT 0
);

-- Seed default test user
INSERT INTO "user" (user_id, account, password, budget)
VALUES ('00000000-0000-0000-0000-000000000001', 'test-user-001', 'default_password', 1000)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Table 2: file
-- =============================================================================
CREATE TABLE IF NOT EXISTS file (
    file_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    file_name       VARCHAR(255) NOT NULL,
    time_upload     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'done'
    -- values: 'pending' (waiting SQS parse) | 'processing' | 'done' | 'error'
);

CREATE INDEX IF NOT EXISTS idx_file_user ON file(user_id);

-- =============================================================================
-- Table 3: transaction
-- =============================================================================
CREATE TABLE IF NOT EXISTS transaction (
    transaction_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id         UUID NOT NULL REFERENCES file(file_id) ON DELETE CASCADE,
    time            TIMESTAMP WITH TIME ZONE NOT NULL,
    description     VARCHAR(500),
    amount          BIGINT NOT NULL,
    confident       NUMERIC(4,2) DEFAULT 0.00,  -- 0.00–1.00
    category        category_enum NOT NULL DEFAULT 'Other',
    review_status   VARCHAR(20) DEFAULT 'ok'
    -- values: 'ok' | 'review' (confidence < threshold, needs human check)
);

CREATE INDEX IF NOT EXISTS idx_transaction_file   ON transaction(file_id);
CREATE INDEX IF NOT EXISTS idx_transaction_time   ON transaction(time);
CREATE INDEX IF NOT EXISTS idx_transaction_review ON transaction(review_status);

-- =============================================================================
-- Table 4: chat_history
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_history (
    chat_history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    input           VARCHAR(2000),
    output          VARCHAR(5000),
    time            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_time ON chat_history(user_id, time);

-- =============================================================================
-- Table 5: budget_cap  (per-user, per-category spending cap)
-- =============================================================================
CREATE TABLE IF NOT EXISTS budget_cap (
    cap_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    category        category_enum NOT NULL,
    cap_amount      BIGINT NOT NULL,           -- absolute value, e.g. 2000000 VND
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, category)
);

CREATE INDEX IF NOT EXISTS idx_budget_cap_user ON budget_cap(user_id);
