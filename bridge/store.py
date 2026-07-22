"""SQLite 本地状态：包裹处理进度（幂等核心）+ 失败记录。"""
import sqlite3
import time

# 包裹状态机
NEW = "NEW"                          # 已发现，待选渠道
CHANNEL_ASSIGNED = "CHANNEL_ASSIGNED"  # 已指派仓库/渠道
ORDERED = "ORDERED"                  # 已物流下单（已推送 WMS）
WMS_SHIPPED = "WMS_SHIPPED"          # WMS 已出库（待回传赛狐）
CLOSED = "CLOSED"                    # 已称重发货，闭环完成
FAILED = "FAILED"                    # 需人工介入
STALE = "STALE"                      # 已不在 to_process 的陈旧 NEW，不再每轮刷日志

SCHEMA = """
CREATE TABLE IF NOT EXISTS package (
    package_sn   TEXT PRIMARY KEY,
    shop_id      TEXT,
    order_id     TEXT,
    country      TEXT,
    state        TEXT NOT NULL,
    channel_name TEXT,
    track_no     TEXT,
    weight_g     INTEGER,
    fail_reason  TEXT,
    retry_count  INTEGER DEFAULT 0,
    created_at   INTEGER,
    updated_at   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_package_state ON package(state);
"""


class Store:
    def __init__(self, path="bridge.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert_new(self, package_sn, shop_id, order_id, country):
        """新包裹入库；已存在则忽略（幂等）。返回是否新增。"""
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO package
               (package_sn, shop_id, order_id, country, state, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (package_sn, shop_id, order_id, country, NEW,
             int(time.time()), int(time.time())),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def set_state(self, package_sn, state, **fields):
        sets = ", ".join(f"{k}=?" for k in fields)
        sql = f"UPDATE package SET state=?, updated_at=?{', ' + sets if sets else ''} WHERE package_sn=?"
        self.conn.execute(
            sql, (state, int(time.time()), *fields.values(), package_sn)
        )
        self.conn.commit()

    def mark_failed(self, package_sn, reason):
        self.conn.execute(
            """UPDATE package SET state=?, fail_reason=?, retry_count=retry_count+1,
               updated_at=? WHERE package_sn=?""",
            (FAILED, str(reason)[:500], int(time.time()), package_sn),
        )
        self.conn.commit()

    def revive_to_new(self, package_sn, shop_id=None, order_id=None, country=None):
        """FAILED/STALE → NEW，清空 fail_reason，供人工补渠道后重跑。"""
        now = int(time.time())
        fields = {"state": NEW, "fail_reason": None, "updated_at": now}
        if shop_id is not None:
            fields["shop_id"] = shop_id
        if order_id is not None:
            fields["order_id"] = order_id
        if country is not None:
            fields["country"] = country
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(
            f"UPDATE package SET {sets} WHERE package_sn=?",
            (*fields.values(), package_sn),
        )
        self.conn.commit()

    def mark_stale(self, package_sn, reason="不在 to_process"):
        self.conn.execute(
            """UPDATE package SET state=?, fail_reason=?, updated_at=?
               WHERE package_sn=? AND state=?""",
            (STALE, str(reason)[:500], int(time.time()), package_sn, NEW),
        )
        self.conn.commit()

    def by_state(self, state):
        return self.conn.execute(
            "SELECT * FROM package WHERE state=?", (state,)
        ).fetchall()

    def get(self, package_sn):
        return self.conn.execute(
            "SELECT * FROM package WHERE package_sn=?", (package_sn,)
        ).fetchone()
