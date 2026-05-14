"""趋势检测规则引擎 — 对比快照，触发预警"""
from config import RANK_SPIKE_THRESHOLD, REVIEW_GROWTH_THRESHOLD, SCORE_DROP_THRESHOLD
from storage.db import get_previous_snapshot, insert_alert, get_latest_snapshots


def analyze_listing(chart_key, current_games):
    """对某个榜单的当前采集结果进行趋势分析，返回触发预警列表"""
    alerts = []
    chart_label = _chart_label(chart_key)

    for game in current_games:
        appid = game["appid"]
        prev = get_previous_snapshot(appid, chart_key)

        if prev is None:
            # 首次出现 — 检查是否今天已经有快照（同一轮采集可能重复）
            alerts.append({
                "appid": appid,
                "game_name": game["name"],
                "alert_type": "new_chart_entry",
                "severity": "info",
                "message": f"[{chart_label}] 新上榜 #{game['chart_rank']}: {game['name']}",
            })
            continue

        # 排名飙升
        old_rank = prev["chart_rank"]
        new_rank = game["chart_rank"]
        rank_delta = old_rank - new_rank  # 正数表示上升
        if rank_delta >= RANK_SPIKE_THRESHOLD:
            alerts.append({
                "appid": appid,
                "game_name": game["name"],
                "alert_type": "rank_spike",
                "severity": "warning",
                "message": f"[{chart_label}] 排名飙升 #{old_rank}→#{new_rank} (+{rank_delta}): {game['name']}",
            })

        # 评论增长
        old_reviews = prev["review_total"] or 0
        new_reviews = game.get("review_total", 0)
        if old_reviews > 50 and new_reviews > 0:
            growth = (new_reviews - old_reviews) / old_reviews
            if growth >= REVIEW_GROWTH_THRESHOLD:
                alerts.append({
                    "appid": appid,
                    "game_name": game["name"],
                    "alert_type": "review_spike",
                    "severity": "critical",
                    "message": f"[{chart_label}] 评论暴涨 {old_reviews}→{new_reviews} (+{growth*100:.0f}%): {game['name']}",
                })

        # 评分暴跌
        old_score = prev["review_score"] or 0
        new_score = game.get("review_score", 0)
        if old_score > 30 and new_score > 0:
            drop = old_score - new_score
            if drop >= SCORE_DROP_THRESHOLD:
                alerts.append({
                    "appid": appid,
                    "game_name": game["name"],
                    "alert_type": "score_drop",
                    "severity": "warning",
                    "message": f"[{chart_label}] 好评率暴跌 {old_score}%→{new_score}% (-{drop}pp): {game['name']}",
                })

    # 检测消失的游戏（上轮在榜，本轮不在）
    _check_dropouts(chart_key, current_games, alerts, chart_label)

    return alerts


def _check_dropouts(chart_key, current_games, alerts, chart_label):
    """检测从榜单消失的游戏"""
    prev_snapshots = get_latest_snapshots(chart_key)
    current_ids = {g["appid"] for g in current_games}
    prev_ids = {s["appid"] for s in prev_snapshots}

    dropped = prev_ids - current_ids
    if len(dropped) > 10:
        return  # 可能是榜单整体刷新，不是个别游戏消失

    for appid in dropped:
        prev_snap = next((s for s in prev_snapshots if s["appid"] == appid), None)
        if prev_snap and prev_snap["chart_rank"] <= 50:
            alerts.append({
                "appid": appid,
                "game_name": f"App {appid}",
                "alert_type": "dropped_out",
                "severity": "info",
                "message": f"[{chart_label}] 跌出榜单 (曾排名 #{prev_snap['chart_rank']}): App {appid}",
            })


def persist_alerts(alerts):
    """将预警持久化到数据库，去重（同一 appid + alert_type 10 分钟内不重复）"""
    from storage.db import get_conn
    conn = get_conn()

    saved = []
    for a in alerts:
        existing = conn.execute("""
            SELECT id FROM alerts
            WHERE appid=? AND alert_type=?
              AND created_at >= datetime('now', '-10 minutes')
        """, (a["appid"], a["alert_type"])).fetchone()
        if existing:
            continue

        insert_alert(
            a["appid"], a["alert_type"], a["severity"],
            a["message"], None, None
        )
        saved.append(a)
    conn.close()
    return saved


def _chart_label(chart_key):
    labels = {
        "global_top_sellers": "全球热销",
        "popular_new": "热门新品",
        "wishlist": "愿望单",
    }
    return labels.get(chart_key, chart_key)
