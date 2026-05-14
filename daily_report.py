"""每日简报 — 汇总过去 24h 动态，生成结构化日报 + 排名变化图表"""
import sys
from datetime import datetime
from config import STEAM_LISTINGS, LARK_CHAT_ID
from storage.db import get_conn, get_today_game_ids
from analyzer.llm import analyze_game, analyze_daily_summary
from notifier.lark import send_daily_report
from visualizer import generate_comparison_chart, send_chart_to_lark


def generate_report():
    print(f"[{datetime.now()}] 生成每日简报...")
    conn = get_conn()

    # 今日去重游戏数
    total_snapshots = conn.execute("""
        SELECT COUNT(DISTINCT appid) as cnt FROM snapshots
        WHERE date(snapshot_time) = date('now')
    """).fetchone()["cnt"]

    # 今日预警
    today_alerts = conn.execute("""
        SELECT * FROM alerts
        WHERE date(created_at) = date('now')
        ORDER BY severity DESC, created_at DESC
    """).fetchall()

    # 各榜单 Top 5 + 汇总数据（供 LLM 分析用）
    chart_summaries = []
    chart_data = {}
    for chart_type in STEAM_LISTINGS:
        label = STEAM_LISTINGS[chart_type]["label"]
        rows = conn.execute("""
            SELECT g.name, s.chart_rank, s.review_total, s.review_score
            FROM snapshots s
            JOIN games g ON g.appid = s.appid
            WHERE s.chart_type = ?
              AND s.id = (
                  SELECT s2.id FROM snapshots s2
                  WHERE s2.appid = s.appid AND s2.chart_type = s.chart_type
                    AND date(s2.snapshot_time) = date('now')
                  ORDER BY s2.snapshot_time DESC LIMIT 1
              )
            ORDER BY s.chart_rank ASC
            LIMIT 5
        """, (chart_type,)).fetchall()
        chart_rows = [dict(r) for r in rows]
        chart_data[label] = [{"name": r["name"], "rank": r["chart_rank"]} for r in chart_rows]
        if chart_rows:
            lines = [f"【{label} Top 5】"]
            for r in chart_rows:
                lines.append(f"  #{r['chart_rank']} {r['name']} | 评论{r['review_total']} | 好评率{r['review_score']}%")
            chart_summaries.append("\n".join(lines))

    # LLM 整体分析
    alerts_list = [dict(a) for a in today_alerts]
    insight = analyze_daily_summary(total_snapshots, alerts_list, chart_data)

    # 组装报告
    lines = [
        f"## Steam 游戏情报日报",
        f"日期: {datetime.now().strftime('%Y-%m-%d')}",
        f"今日追踪游戏: {total_snapshots} 款 | 预警: {len(today_alerts)} 条",
        "",
    ]

    if insight:
        lines.append("### 今日分析洞察")
        lines.append(insight)
        lines.append("")

    lines.extend(chart_summaries)

    if today_alerts:
        lines.append("")
        lines.append("### 今日预警")
        for a in today_alerts:
            sev = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(a["severity"], "")
            lines.append(f"- {sev} {a['message']}")

    report = "\n".join(lines)
    gids = get_today_game_ids()

    # LLM 深度分析（只分析 top 3 预警游戏）
    if today_alerts:
        top_alerts = [a for a in today_alerts if a["severity"] in ("critical", "warning")][:3]
        for a in top_alerts:
            report += f"\n\n### 深度分析: App {a['appid']}"
            info = {"appid": a["appid"], "name": f"App {a['appid']}"}
            reviews = {}
            summary = analyze_game(info, reviews)
            report += f"\n{summary}"

    # 推送到飞书（文字报告）
    send_daily_report(report, len(today_alerts), len(gids) if gids else total_snapshots)
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))

    # 生成并发送排名变化对比图表
    print(f"[{datetime.now()}] 生成排名变化图表...")
    for chart_type in STEAM_LISTINGS:
        prev_snapshots = _get_previous_snapshots(conn, chart_type)
        curr_snapshots = _get_current_snapshots(conn, chart_type)
        if prev_snapshots and curr_snapshots:
            path = generate_comparison_chart(chart_type, prev_snapshots, curr_snapshots)
            if path:
                label = STEAM_LISTINGS[chart_type]["label"]
                send_chart_to_lark(path, LARK_CHAT_ID, f"Steam [{label}] 24h Ranking Changes")
                print(f"     图表已发送: {label}")
        else:
            print(f"     [{chart_type}] 暂无足够历史数据对比（需至少2天数据）")

    conn.close()
    return report


def _get_previous_snapshots(conn, chart_type):
    """获取上一个采集日的快照（昨天或更早）"""
    rows = conn.execute("""
        SELECT appid, chart_rank FROM snapshots
        WHERE chart_type = ?
          AND date(snapshot_time) = (
              SELECT date(snapshot_time) FROM snapshots
              WHERE chart_type = ? AND date(snapshot_time) < date('now')
              ORDER BY snapshot_time DESC LIMIT 1
          )
        ORDER BY chart_rank
    """, (chart_type, chart_type)).fetchall()
    return [dict(r) for r in rows]


def _get_current_snapshots(conn, chart_type):
    """获取今日最新快照"""
    rows = conn.execute("""
        SELECT s.appid, s.chart_rank FROM snapshots s
        WHERE s.chart_type = ?
          AND s.id = (
              SELECT s2.id FROM snapshots s2
              WHERE s2.appid = s.appid AND s2.chart_type = s.chart_type
                AND date(s2.snapshot_time) = date('now')
              ORDER BY s2.snapshot_time DESC LIMIT 1
          )
        ORDER BY s.chart_rank
    """, (chart_type,)).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    generate_report()
