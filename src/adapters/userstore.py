"""PostgreSQL adapter for all BudgetBot data.

Schema (5 tables):
    user          — account + budget
    file          — uploaded statement files (with status field)
    transaction   — parsed rows with category, confidence, review_status
    chat_history  — chat turns
    budget_cap    — per-user, per-category spending caps

Interface (grouped by table):
    User:         create_user, get_user_by_id, get_user_by_account, update_user, delete_user
    File:         create_file, get_file, list_files, update_file_status, delete_file
    Transaction:  add_transaction, list_transactions, list_review_queue,
                  update_transaction_category, summary
    Chat:         add_chat_history, get_chat_history, delete_chat_history
    Budget cap:   set_budget_cap, get_budget_caps, delete_budget_cap
"""

import uuid
from datetime import datetime, timezone


VALID_CATEGORIES = [
    "Food", "Transport", "Shopping", "Utilities", "Entertainment",
    "Health", "Subscriptions", "Bills", "Income", "Transfer", "Other",
]

VALID_FILE_STATUSES   = ("pending", "processing", "done", "error")
VALID_REVIEW_STATUSES = ("ok", "review")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_uuid(user_id: str) -> str:
    """Ensure user_id is a valid UUID string; derive one if it's a plain string."""
    try:
        return str(uuid.UUID(user_id))
    except (ValueError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(user_id)))


class PostgresUserStore:

    def __init__(self, url: str):
        try:
            import psycopg2
        except ImportError:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
        if not url:
            raise ValueError("USERSTORE_POSTGRES_URL must be set")
        self.conn = psycopg2.connect(url)
        self.conn.autocommit = True
        self._init_schema()

    # =========================================================================
    # Schema bootstrap (idempotent)
    # =========================================================================

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_enum') THEN
                        CREATE TYPE category_enum AS ENUM (
                            'Food','Transport','Shopping','Utilities','Entertainment',
                            'Health','Subscriptions','Bills','Income','Transfer','Other'
                        );
                    ELSE
                        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Subscriptions'; EXCEPTION WHEN duplicate_object THEN NULL; END;
                        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Utilities';     EXCEPTION WHEN duplicate_object THEN NULL; END;
                        BEGIN ALTER TYPE category_enum ADD VALUE IF NOT EXISTS 'Bills';         EXCEPTION WHEN duplicate_object THEN NULL; END;
                    END IF;
                END $$;
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS "user" (
                    user_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account  VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    budget   INTEGER DEFAULT 0
                );
                INSERT INTO "user" (user_id, account, password, budget)
                VALUES ('00000000-0000-0000-0000-000000000001','test-user-001','default_password',1000)
                ON CONFLICT DO NOTHING;
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS file (
                    file_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id     UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
                    file_name   VARCHAR(255) NOT NULL,
                    time_upload TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    status      VARCHAR(20) DEFAULT 'done'
                );
                CREATE INDEX IF NOT EXISTS idx_file_user ON file(user_id);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS transaction (
                    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    file_id        UUID NOT NULL REFERENCES file(file_id) ON DELETE CASCADE,
                    time           TIMESTAMP WITH TIME ZONE NOT NULL,
                    description    VARCHAR(500),
                    amount         BIGINT NOT NULL,
                    confident      NUMERIC(4,2) DEFAULT 0.00,
                    category       category_enum NOT NULL DEFAULT 'Other',
                    review_status  VARCHAR(20) DEFAULT 'ok'
                );
            """)

            # Migrations — must run BEFORE indexes that depend on new columns
            cur.execute("""
                ALTER TABLE file        ADD COLUMN IF NOT EXISTS status        VARCHAR(20) DEFAULT 'done';
                ALTER TABLE transaction ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'ok';
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_file   ON transaction(file_id);
                CREATE INDEX IF NOT EXISTS idx_transaction_time   ON transaction(time);
                CREATE INDEX IF NOT EXISTS idx_transaction_review ON transaction(review_status);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    chat_history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id         UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
                    input           VARCHAR(2000),
                    output          VARCHAR(5000),
                    time            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_chat_history_time ON chat_history(user_id, time);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS budget_cap (
                    cap_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id    UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
                    category   category_enum NOT NULL,
                    cap_amount BIGINT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, category)
                );
                CREATE INDEX IF NOT EXISTS idx_budget_cap_user ON budget_cap(user_id);
            """)


    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _ensure_user(self, user_id: str) -> str:
        val = _to_uuid(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "user" (user_id, account, password, budget) '
                'VALUES (%s, %s, %s, 0) ON CONFLICT (user_id) DO NOTHING',
                (val, f"user_{val[:8]}", "dummy_password"),
            )
        return val

    @staticmethod
    def _row_to_txn(r) -> dict:
        return {
            "transaction_id": str(r[0]),
            "file_id":        str(r[1]),
            "time":           r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            "description":    r[3],
            "amount":         r[4],
            "confident":      float(r[5]) if r[5] is not None else 0.0,
            "category":       r[6],
            "review_status":  r[7],
        }

    # =========================================================================
    # User CRUD
    # =========================================================================

    def create_user(self, account: str, password: str, budget: int = 0) -> dict:
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "user" (account, password, budget) '
                "VALUES (%s, %s, %s) RETURNING user_id, account, budget",
                (account, password, budget),
            )
            row = cur.fetchone()
            return {"user_id": str(row[0]), "account": row[1], "budget": row[2]}

    def get_user_by_id(self, user_id: str) -> dict | None:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, account, password, budget FROM "user" WHERE user_id = %s',
                (uid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"user_id": str(row[0]), "account": row[1], "password": row[2], "budget": row[3]}

    def get_user_by_account(self, account: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, account, password, budget FROM "user" WHERE account = %s',
                (account,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"user_id": str(row[0]), "account": row[1], "password": row[2], "budget": row[3]}

    def update_user(self, user_id: str, **fields) -> dict | None:
        uid = self._ensure_user(user_id)
        allowed = {"account", "password", "budget"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_user_by_id(uid)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [uid]
        with self.conn.cursor() as cur:
            cur.execute(
                f'UPDATE "user" SET {set_clause} WHERE user_id = %s '
                "RETURNING user_id, account, budget",
                values,
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"user_id": str(row[0]), "account": row[1], "budget": row[2]}

    def delete_user(self, user_id: str) -> bool:
        uid = _to_uuid(user_id)
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM "user" WHERE user_id = %s', (uid,))
            return cur.rowcount > 0

    # =========================================================================
    # File CRUD
    # =========================================================================

    def create_file(self, user_id: str, file_name: str, status: str = "done") -> dict:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO file (user_id, file_name, status) "
                "VALUES (%s, %s, %s) RETURNING file_id, user_id, file_name, time_upload, status",
                (uid, file_name, status),
            )
            row = cur.fetchone()
            return {
                "file_id":     str(row[0]),
                "user_id":     str(row[1]),
                "file_name":   row[2],
                "time_upload": row[3].isoformat() if row[3] else None,
                "status":      row[4],
            }

    def get_file(self, file_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT file_id, user_id, file_name, time_upload, status "
                "FROM file WHERE file_id = %s",
                (file_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "file_id":     str(row[0]),
                "user_id":     str(row[1]),
                "file_name":   row[2],
                "time_upload": row[3].isoformat() if row[3] else None,
                "status":      row[4],
            }

    def update_file_status(self, file_id: str, status: str) -> bool:
        if status not in VALID_FILE_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file SET status = %s WHERE file_id = %s", (status, file_id))
            return cur.rowcount > 0

    def list_files(self, user_id: str) -> list:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT file_id, user_id, file_name, time_upload, status "
                "FROM file WHERE user_id = %s ORDER BY time_upload DESC",
                (uid,),
            )
            return [
                {
                    "file_id":     str(r[0]),
                    "user_id":     str(r[1]),
                    "file_name":   r[2],
                    "time_upload": r[3].isoformat() if r[3] else None,
                    "status":      r[4],
                }
                for r in cur.fetchall()
            ]

    def delete_file(self, file_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM file WHERE file_id = %s", (file_id,))
            return cur.rowcount > 0

    # =========================================================================
    # Transaction CRUD
    # =========================================================================

    def add_transaction(self, file_id: str, txn: dict, review_threshold: float = 0.60) -> dict:
        """Insert one transaction. Sets review_status='review' if confidence < threshold."""
        category = txn.get("category", "Other")
        if category not in VALID_CATEGORIES:
            category = "Other"

        raw_conf = txn.get("confident", 0.0)
        try:
            confidence = float(raw_conf)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        review_status = "review" if confidence < review_threshold else "ok"

        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transaction "
                "  (file_id, time, description, amount, confident, category, review_status) "
                "VALUES (%s, %s, %s, %s, %s, %s::category_enum, %s) "
                "RETURNING transaction_id, file_id, time, description, amount, confident, category, review_status",
                (
                    file_id,
                    txn["time"],
                    txn.get("description", ""),
                    int(txn["amount"]),
                    confidence,
                    category,
                    review_status,
                ),
            )
            return self._row_to_txn(cur.fetchone())

    def list_transactions(self, user_id: str, month: str | None = None,
                          review_status: str | None = None) -> list:
        uid = self._ensure_user(user_id)
        sql = (
            "SELECT t.transaction_id, t.file_id, t.time, t.description, "
            "       t.amount, t.confident, t.category, t.review_status "
            "FROM transaction t JOIN file f ON t.file_id = f.file_id "
            "WHERE f.user_id = %s"
        )
        params: list = [uid]
        if month:
            sql += " AND to_char(t.time, 'YYYY-MM') = %s"
            params.append(month)
        if review_status in VALID_REVIEW_STATUSES:
            sql += " AND t.review_status = %s"
            params.append(review_status)
        sql += " ORDER BY t.time DESC"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._row_to_txn(r) for r in cur.fetchall()]

    def list_review_queue(self, user_id: str) -> list:
        """Return only transactions that need human review (confidence < threshold)."""
        return self.list_transactions(user_id, review_status="review")

    def update_transaction_category(self, transaction_id: str,
                                    category: str) -> dict | None:
        """User manually corrects a category; clears review_status → 'ok'."""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category!r}")
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE transaction "
                "SET category = %s::category_enum, review_status = 'ok' "
                "WHERE transaction_id = %s "
                "RETURNING transaction_id, file_id, time, description, amount, confident, category, review_status",
                (category, transaction_id),
            )
            row = cur.fetchone()
            return self._row_to_txn(row) if row else None

    def summary(self, user_id: str, month: str | None = None) -> dict:
        """Aggregate spending by category. Returns {category: {total, count}}."""
        uid = self._ensure_user(user_id)
        sql = (
            "SELECT t.category, SUM(t.amount), COUNT(*) "
            "FROM transaction t JOIN file f ON t.file_id = f.file_id "
            "WHERE f.user_id = %s"
        )
        params: list = [uid]
        if month:
            sql += " AND to_char(t.time, 'YYYY-MM') = %s"
            params.append(month)
        sql += " GROUP BY t.category"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return {r[0]: {"total": int(r[1]), "count": int(r[2])} for r in cur.fetchall()}

    def spending_this_month(self, user_id: str) -> dict:
        """Convenience: summary for the current calendar month (absolute values, expenses only)."""
        from datetime import date
        month = date.today().strftime("%Y-%m")
        raw = self.summary(user_id, month=month)
        return {cat: abs(v["total"]) for cat, v in raw.items() if v["total"] < 0}

    # =========================================================================
    # Chat history
    # =========================================================================

    def add_chat_history(self, user_id: str, input_text: str, output_text: str) -> dict:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history (user_id, input, output) "
                "VALUES (%s, %s, %s) "
                "RETURNING chat_history_id, user_id, input, output, time",
                (uid, input_text, output_text),
            )
            row = cur.fetchone()
            return {
                "chat_history_id": str(row[0]),
                "user_id":         str(row[1]),
                "input":           row[2],
                "output":          row[3],
                "time":            row[4].isoformat() if row[4] else None,
            }

    def get_chat_history(self, user_id: str, limit: int = 50) -> list:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT chat_history_id, user_id, input, output, time "
                "FROM chat_history WHERE user_id = %s "
                "ORDER BY time DESC LIMIT %s",
                (uid, limit),
            )
            return [
                {
                    "chat_history_id": str(r[0]),
                    "user_id":         str(r[1]),
                    "input":           r[2],
                    "output":          r[3],
                    "time":            r[4].isoformat() if r[4] else None,
                }
                for r in cur.fetchall()
            ]

    def delete_chat_history(self, chat_history_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history WHERE chat_history_id = %s", (chat_history_id,))
            return cur.rowcount > 0

    # =========================================================================
    # Budget caps
    # =========================================================================

    def set_budget_cap(self, user_id: str, category: str, cap_amount: int) -> dict:
        """Create or update a budget cap for a category (upsert)."""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {category!r}")
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO budget_cap (user_id, category, cap_amount) "
                "VALUES (%s, %s::category_enum, %s) "
                "ON CONFLICT (user_id, category) DO UPDATE SET cap_amount = EXCLUDED.cap_amount "
                "RETURNING cap_id, user_id, category, cap_amount",
                (uid, category, cap_amount),
            )
            row = cur.fetchone()
            return {
                "cap_id":     str(row[0]),
                "user_id":    str(row[1]),
                "category":   row[2],
                "cap_amount": row[3],
            }

    def get_budget_caps(self, user_id: str) -> list:
        uid = self._ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT cap_id, user_id, category, cap_amount "
                "FROM budget_cap WHERE user_id = %s ORDER BY category",
                (uid,),
            )
            return [
                {"cap_id": str(r[0]), "user_id": str(r[1]),
                 "category": r[2], "cap_amount": r[3]}
                for r in cur.fetchall()
            ]

    def delete_budget_cap(self, user_id: str, category: str) -> bool:
        uid = _to_uuid(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM budget_cap WHERE user_id = %s AND category = %s::category_enum",
                (uid, category),
            )
            return cur.rowcount > 0
