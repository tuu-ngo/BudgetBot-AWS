-- =============================================================================
-- BudgetBot — PostgreSQL Schema Initialization
-- =============================================================================
-- Run this script to create all tables, types, and indexes.
-- Usage: psql -d budgetbot -f init_db.sql
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Enum type for transaction categories
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_enum') THEN
        CREATE TYPE category_enum AS ENUM (
            'Food',
            'Transport',
            'Shopping',
            'Entertainment',
            'Bills',
            'Health',
            'Education',
            'Travel',
            'Income',
            'Transfer',
            'Other'
        );
    END IF;
END
$$;

-- =============================================================================
-- Table 1: User
-- =============================================================================
CREATE TABLE IF NOT EXISTS "user" (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account     VARCHAR(255) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    budget      INTEGER DEFAULT 0
);

-- =============================================================================
-- Table 2: File
-- =============================================================================
CREATE TABLE IF NOT EXISTS file (
    file_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    file_name   VARCHAR(255) NOT NULL,
    time_upload TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_user ON file(user_id);

-- =============================================================================
-- Table 3: Transaction
-- =============================================================================
CREATE TABLE IF NOT EXISTS transaction (
    transaction_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id         UUID NOT NULL REFERENCES file(file_id) ON DELETE CASCADE,
    time            TIMESTAMP WITH TIME ZONE NOT NULL,
    description     VARCHAR(500),
    amount          BIGINT NOT NULL,
    confident       INTEGER DEFAULT 0,
    category        category_enum NOT NULL DEFAULT 'Other'
);

CREATE INDEX IF NOT EXISTS idx_transaction_file ON transaction(file_id);
CREATE INDEX IF NOT EXISTS idx_transaction_time ON transaction(time);

-- =============================================================================
-- Table 4: Chat History
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
