"""SQLite 数据库初始化与 CRUD 封装"""
import sqlite3
import os
from config import DB_PATH


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            release_date TEXT,
            developer TEXT,
            publisher TEXT,
            genres TEXT,
            price_cents INTEGER,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appid INTEGER,
            snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chart_type TEXT,
            chart_rank INTEGER,
            review_total INTEGER,
            review_score INTEGER,
            concurrent_players INTEGER,
            FOREIGN KEY (appid) REFERENCES games(appid)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appid INTEGER,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            snapshot_before INTEGER,
            snapshot_after INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appid) REFERENCES games(appid)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_appid_time
            ON snapshots(appid, snapshot_time);
        CREATE INDEX IF NOT EXISTS idx_snapshots_chart
            ON snapshots(chart_type, snapshot_time);
        CREATE INDEX IF NOT EXISTS idx_alerts_created
            ON alerts(created_at);
    """)
    conn.commit()
    conn.close()


def upsert_game(appid, name, release_date, developer, publisher, genres, price_cents):
    conn = get_conn()
    conn.execute("""
        INSERT INTO games (appid, name, release_date, developer, publisher, genres, price_cents, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(appid) DO UPDATE SET
            name=excluded.name,
            release_date=excluded.release_date,
            developer=excluded.developer,
            publisher=excluded.publisher,
            genres=excluded.genres,
            price_cents=excluded.price_cents,
            last_updated=CURRENT_TIMESTAMP
    """, (appid, name, release_date, developer, publisher, genres, price_cents))
    conn.commit()
    conn.close()


def insert_snapshot(appid, chart_type, chart_rank, review_total, review_score, concurrent_players):
    conn = get_conn()
    conn.execute("""
        INSERT INTO snapshots (appid, chart_type, chart_rank, review_total, review_score, concurrent_players)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (appid, chart_type, chart_rank, review_total, review_score, concurrent_players))
    conn.commit()
    conn.close()


def get_previous_snapshot(appid, chart_type):
    """获取同一游戏在同一榜单的上一次快照"""
    conn = get_conn()
    row = conn.execute("""
        SELECT * FROM snapshots
        WHERE appid=? AND chart_type=?
        ORDER BY snapshot_time DESC LIMIT 1
    """, (appid, chart_type)).fetchone()
    conn.close()
    return row


def get_latest_snapshots(chart_type):
    """获取某个榜单最新一批快照的所有 appid"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT appid, chart_rank, review_total, review_score, concurrent_players, snapshot_time
        FROM snapshots
        WHERE snapshot_time = (
            SELECT MAX(snapshot_time) FROM snapshots WHERE chart_type=?
        ) AND chart_type=?
    """, (chart_type, chart_type)).fetchall()
    conn.close()
    return rows


def get_chart_history(appid, chart_type, days=30):
    """获取某游戏在某榜单的历史快照"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM snapshots
        WHERE appid=? AND chart_type=?
          AND snapshot_time >= datetime('now', ? || ' days')
        ORDER BY snapshot_time ASC
    """, (appid, chart_type, f"-{days}")).fetchall()
    conn.close()
    return rows


def insert_alert(appid, alert_type, severity, message, snap_before, snap_after):
    conn = get_conn()
    conn.execute("""
        INSERT INTO alerts (appid, alert_type, severity, message, snapshot_before, snapshot_after)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (appid, alert_type, severity, message, snap_before, snap_after))
    conn.commit()
    conn.close()


def get_recent_alerts(minutes=30):
    """获取最近 N 分钟内的预警"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM alerts
        WHERE created_at >= datetime('now', ? || ' minutes')
        ORDER BY created_at DESC
    """, (f"-{minutes}",)).fetchall()
    conn.close()
    return rows


def get_today_game_ids():
    """获取今天采集过的所有 appid"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT appid FROM snapshots
        WHERE date(snapshot_time) = date('now')
    """).fetchall()
    conn.close()
    return [r["appid"] for r in rows]


def cleanup_old_snapshots(days=30):
    """清理超过 N 天的旧快照"""
    conn = get_conn()
    conn.execute("""
        DELETE FROM snapshots
        WHERE snapshot_time < datetime('now', ? || ' days')
    """, (f"-{days}",))
    conn.commit()
    conn.close()
