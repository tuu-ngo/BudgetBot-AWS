"""PostgreSQL transaction store adapter.

Schema: 4 tables — user, file, transaction, chat_history.
All primary keys are UUIDs generated server-side by PostgreSQL (gen_random_uuid).

Interface:
    -- User CRUD --
    create_user(account, password, budget=0) -> dict
    get_user_by_id(user_id) -> dict | None
    get_user_by_account(account) -> dict | None
    update_user(user_id, **fields) -> dict | None
    delete_user(user_id) -> bool

    -- File CRUD --
    create_file(user_id, file_name) -> dict
    get_file(file_id) -> dict | None
    list_files(user_id) -> list[dict]
    delete_file(file_id) -> bool

    -- Transaction CRUD --
    add_transaction(file_id, txn) -> dict
    list_transactions(user_id, month=None) -> list[dict]
    summary(user_id, month=None) -> {category: {"total": int, "count": int}}

    -- Chat History CRUD --
    add_chat_history(user_id, input_text, output_text) -> dict
    get_chat_history(user_id, limit=50) -> list[dict]
    delete_chat_history(chat_history_id) -> bool
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Valid category values (must match the category_enum type in PostgreSQL)
VALID_CATEGORIES = [
    "Food", "Transport", "Shopping", "Entertainment",
    "Bills", "Health", "Education", "Travel",
    "Income", "Transfer", "Other",
]


class PostgresUserStore:
    """PostgreSQL adapter for all BudgetBot data (user, file, transaction, chat_history)."""

    def __init__(self, url: str):
        try:
            import psycopg2
        except ImportError:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
        if not url:
            raise ValueError("USERSTORE_POSTGRES_URL must be set for Postgres backend")
        self.conn = psycopg2.connect(url)
        self.conn.autocommit = True
        self._init_schema()

    # -------------------------------------------------------------------------
    # Schema initialization
    # -------------------------------------------------------------------------

    def _init_schema(self):
        with self.conn.cursor() as cur:
            # Create enum type (idempotent)
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'category_enum') THEN
                        CREATE TYPE category_enum AS ENUM (
                            'Food', 'Transport', 'Shopping', 'Entertainment',
                            'Bills', 'Health', 'Education', 'Travel',
                            'Income', 'Transfer', 'Other'
                        );
                    END IF;
                END
                $$;
            """)

            # Table: user
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "user" (
                    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account     VARCHAR(255) NOT NULL UNIQUE,
                    password    VARCHAR(255) NOT NULL,
                    budget      INTEGER DEFAULT 0
                );
            """)

            # Table: file
            cur.execute("""
                CREATE TABLE IF NOT EXISTS file (
                    file_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id     UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
                    file_name   VARCHAR(255) NOT NULL,
                    time_upload TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_file_user ON file(user_id);
            """)

            # Table: transaction
            cur.execute("""
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
            """)

            # Table: chat_history
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

            # Seed default user if not exists
            cur.execute("""
                INSERT INTO "user" (user_id, account, password, budget)
                VALUES ('00000000-0000-0000-0000-000000000001', 'test-user-001', 'default_password', 1000)
                ON CONFLICT DO NOTHING;
            """)

    # =========================================================================
    # User CRUD
    # =========================================================================

    def _resolve_and_ensure_user(self, user_id: str) -> str:
        import uuid
        try:
            val = str(uuid.UUID(user_id))
        except ValueError:
            val = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "user" (user_id, account, password, budget) '
                'VALUES (%s, %s, %s, 0) '
                'ON CONFLICT (user_id) DO NOTHING',
                (val, f"user_{val}", "dummy_password")
            )
        return val

    def create_user(self, account: str, password: str, budget: int = 0) -> dict:
        """Create a new user. Returns the created user dict with user_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                'INSERT INTO "user" (account, password, budget) '
                "VALUES (%s, %s, %s) RETURNING user_id, account, budget",
                (account, password, budget),
            )
            row = cur.fetchone()
            return {"user_id": str(row[0]), "account": row[1], "budget": row[2]}

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Fetch a user by UUID. Returns None if not found."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, account, password, budget FROM "user" WHERE user_id = %s',
                (user_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id": str(row[0]),
                "account": row[1],
                "password": row[2],
                "budget": row[3],
            }

    def get_user_by_account(self, account: str) -> dict | None:
        """Fetch a user by account name. Returns None if not found."""
        with self.conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, account, password, budget FROM "user" WHERE account = %s',
                (account,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id": str(row[0]),
                "account": row[1],
                "password": row[2],
                "budget": row[3],
            }

    def update_user(self, user_id: str, **fields) -> dict | None:
        """Update user fields (account, password, budget). Returns updated user or None."""
        user_id = self._resolve_and_ensure_user(user_id)
        allowed = {"account", "password", "budget"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_user_by_id(user_id)

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [user_id]

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
        """Delete a user (cascades to file, transaction, chat_history). Returns True if deleted."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM "user" WHERE user_id = %s', (user_id,))
            return cur.rowcount > 0

    # =========================================================================
    # File CRUD
    # =========================================================================

    def create_file(self, user_id: str, file_name: str) -> dict:
        """Record a file upload. Returns dict with file_id, user_id, file_name, time_upload."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO file (user_id, file_name) "
                "VALUES (%s, %s) RETURNING file_id, user_id, file_name, time_upload",
                (user_id, file_name),
            )
            row = cur.fetchone()
            return {
                "file_id": str(row[0]),
                "user_id": str(row[1]),
                "file_name": row[2],
                "time_upload": row[3].isoformat() if row[3] else None,
            }

    def get_file(self, file_id: str) -> dict | None:
        """Fetch a file record by file_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT file_id, user_id, file_name, time_upload FROM file WHERE file_id = %s",
                (file_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "file_id": str(row[0]),
                "user_id": str(row[1]),
                "file_name": row[2],
                "time_upload": row[3].isoformat() if row[3] else None,
            }

    def list_files(self, user_id: str) -> list:
        """List all files uploaded by a user, newest first."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT file_id, user_id, file_name, time_upload "
                "FROM file WHERE user_id = %s ORDER BY time_upload DESC",
                (user_id,),
            )
            return [
                {
                    "file_id": str(r[0]),
                    "user_id": str(r[1]),
                    "file_name": r[2],
                    "time_upload": r[3].isoformat() if r[3] else None,
                }
                for r in cur.fetchall()
            ]

    def delete_file(self, file_id: str) -> bool:
        """Delete a file record (cascades to transactions). Returns True if deleted."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM file WHERE file_id = %s", (file_id,))
            return cur.rowcount > 0

    # =========================================================================
    # Transaction CRUD
    # =========================================================================

    def add_transaction(self, file_id: str, txn: dict) -> dict:
        """Insert a single transaction linked to a file_id.

        txn keys: time (str/datetime), description (str), amount (int),
                  confident (int/str), category (str — must be a valid category_enum value).
        Returns the inserted row as dict.
        """
        category = txn.get("category", "Other")
        if category not in VALID_CATEGORIES:
            category = "Other"

        # Map confidence string ("high", "medium", "low") to integer (100, 50, 20)
        raw_conf = txn.get("confident", 0)
        if isinstance(raw_conf, str):
            raw_conf_lower = raw_conf.strip().lower()
            if raw_conf_lower == "high":
                confident_val = 100
            elif raw_conf_lower == "medium":
                confident_val = 50
            elif raw_conf_lower == "low":
                confident_val = 20
            else:
                try:
                    confident_val = int(raw_conf_lower)
                except ValueError:
                    confident_val = 0
        else:
            try:
                confident_val = int(raw_conf)
            except (ValueError, TypeError):
                confident_val = 0

        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transaction (file_id, time, description, amount, confident, category) "
                "VALUES (%s, %s, %s, %s, %s, %s::category_enum) "
                "RETURNING transaction_id, file_id, time, description, amount, confident, category",
                (
                    file_id,
                    txn["time"],
                    txn.get("description", ""),
                    int(txn["amount"]),
                    confident_val,
                    category,
                ),
            )
            row = cur.fetchone()
            return {
                "transaction_id": str(row[0]),
                "file_id": str(row[1]),
                "time": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                "description": row[3],
                "amount": row[4],
                "confident": row[5],
                "category": row[6],
            }

    def list_transactions(self, user_id: str, month: str | None = None) -> list:
        """List transactions for a user (via file → transaction join).

        Optional month filter in 'YYYY-MM' format.
        """
        user_id = self._resolve_and_ensure_user(user_id)
        sql = (
            "SELECT t.transaction_id, t.file_id, t.time, t.description, "
            "       t.amount, t.confident, t.category "
            "FROM transaction t "
            "JOIN file f ON t.file_id = f.file_id "
            "WHERE f.user_id = %s"
        )
        params: list = [user_id]
        if month:
            sql += " AND to_char(t.time, 'YYYY-MM') = %s"
            params.append(month)
        sql += " ORDER BY t.time DESC"

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [
                {
                    "transaction_id": str(r[0]),
                    "file_id": str(r[1]),
                    "time": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                    "description": r[3],
                    "amount": r[4],
                    "confident": r[5],
                    "category": r[6],
                }
                for r in cur.fetchall()
            ]

    def summary(self, user_id: str, month: str | None = None) -> dict:
        """Aggregate transactions by category for a user.

        Returns {category: {"total": int, "count": int}}.
        """
        user_id = self._resolve_and_ensure_user(user_id)
        sql = (
            "SELECT t.category, SUM(t.amount), COUNT(*) "
            "FROM transaction t "
            "JOIN file f ON t.file_id = f.file_id "
            "WHERE f.user_id = %s"
        )
        params: list = [user_id]
        if month:
            sql += " AND to_char(t.time, 'YYYY-MM') = %s"
            params.append(month)
        sql += " GROUP BY t.category"

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return {
                r[0]: {"total": int(r[1]), "count": int(r[2])}
                for r in cur.fetchall()
            }

    # =========================================================================
    # Chat History CRUD
    # =========================================================================

    def add_chat_history(self, user_id: str, input_text: str, output_text: str) -> dict:
        """Save a chat exchange. Returns the created record."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history (user_id, input, output) "
                "VALUES (%s, %s, %s) RETURNING chat_history_id, user_id, input, output, time",
                (user_id, input_text, output_text),
            )
            row = cur.fetchone()
            return {
                "chat_history_id": str(row[0]),
                "user_id": str(row[1]),
                "input": row[2],
                "output": row[3],
                "time": row[4].isoformat() if row[4] else None,
            }

    def get_chat_history(self, user_id: str, limit: int = 50) -> list:
        """Retrieve chat history for a user, newest first."""
        user_id = self._resolve_and_ensure_user(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT chat_history_id, user_id, input, output, time "
                "FROM chat_history WHERE user_id = %s "
                "ORDER BY time DESC LIMIT %s",
                (user_id, limit),
            )
            return [
                {
                    "chat_history_id": str(r[0]),
                    "user_id": str(r[1]),
                    "input": r[2],
                    "output": r[3],
                    "time": r[4].isoformat() if r[4] else None,
                }
                for r in cur.fetchall()
            ]

    def delete_chat_history(self, chat_history_id: str) -> bool:
        """Delete a single chat history record."""
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_history WHERE chat_history_id = %s",
                (chat_history_id,),
            )
            return cur.rowcount > 0
