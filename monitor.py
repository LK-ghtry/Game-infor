"""主入口 — 单次监控运行：采集 → 存储 → 分析 → 通知"""
import sys
from datetime import datetime

from config import TOP_DETAIL_N
from storage.db import init_db, upsert_game, insert_snapshot, cleanup_old_snapshots
from collector.steam_listing import fetch_all_listings
from collector.steam_app import get_app_reviews
from analyzer.trend import analyze_listing, persist_alerts
from notifier.lark import send_alert


def log(msg):
    print(msg, flush=True)


def run():
    log(f"[{datetime.now()}] === Steam 监控开始 ===")
    init_db()

    # 1. 采集所有榜单
    log("[1/4] 采集 Steam 榜单...")
    all_listings = fetch_all_listings()
    total_games = sum(len(v) for v in all_listings.values())
    log(f"      获取到 {total_games} 款游戏")

    all_alerts = []

    # 2. 遍历每个榜单进行存储和分析
    for chart_key, games in all_listings.items():
        log(f"[2/4] 处理 '{chart_key}' ({len(games)} 款)...")
        enriched_games = []

        for i, game in enumerate(games):
            appid = game["appid"]

            # 仅 Top N 获取详细 API 数据（并发玩家 API 在国内无法访问，跳过）
            if i < TOP_DETAIL_N:
                reviews = get_app_reviews(appid) or {}
            else:
                reviews = {}

            # 存储游戏基础信息
            upsert_game(
                appid, game["name"], game.get("release_date", ""),
                "", "", game.get("tags", ""), game.get("price_cents", 0)
            )

            # 存储快照
            insert_snapshot(
                appid, chart_key, game["chart_rank"],
                reviews.get("review_total", 0),
                reviews.get("review_score_pct", 0),
                0  # concurrent_players — api.steampowered.com 在国内被墙
            )

            enriched_games.append({
                **game,
                "review_total": reviews.get("review_total", 0),
                "review_score": reviews.get("review_score_pct", 0),
                "concurrent_players": 0,
            })

        # 趋势分析
        chart_alerts = analyze_listing(chart_key, enriched_games)
        log(f"      检测到 {len(chart_alerts)} 条趋势预警")
        all_alerts.extend(chart_alerts)

    # 3. 持久化 + 推送预警
    log(f"[3/4] 持久化 {len(all_alerts)} 条预警...")
    new_alerts = persist_alerts(all_alerts)
    log(f"      去重后剩余 {len(new_alerts)} 条新预警")

    for alert in new_alerts:
        alert["time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        send_alert(alert)

    # 4. 清理旧数据
    log("[4/4] 清理过期快照...")
    cleanup_old_snapshots(days=30)

    log(f"[{datetime.now()}] === Steam 监控完成 ===, 预警 {len(new_alerts)} 条")
    return len(new_alerts)


if __name__ == "__main__":
    n = run()
    sys.exit(0 if n >= 0 else 1)
