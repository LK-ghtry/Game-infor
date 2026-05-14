"""对比可视化 — 生成榜单排名变化图表，推送到飞书"""
import os
import json
import subprocess
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import datetime
from config import STEAM_LISTINGS

LARK_CLI = r"E:\npm-global\lark-cli.cmd"
CHART_DIR = r"E:\CC\game agent\charts"


def _setup_chinese_font():
    """尝试设置中文字体"""
    for fname in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"]:
        for f in fm.fontManager.ttflist:
            if fname in f.name:
                plt.rcParams["font.sans-serif"] = [f.name]
                plt.rcParams["axes.unicode_minus"] = False
                return
    plt.rcParams["font.sans-serif"] = ["sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False


def generate_comparison_chart(chart_key, prev_snapshots, curr_snapshots):
    """生成单榜单排名变化对比图，返回图片路径"""
    os.makedirs(CHART_DIR, exist_ok=True)
    _setup_chinese_font()

    label = STEAM_LISTINGS.get(chart_key, {}).get("label", chart_key)

    # 构建排名变化数据
    prev_map = {s["appid"]: s["chart_rank"] for s in prev_snapshots}
    curr_map = {s["appid"]: s["chart_rank"] for s in curr_snapshots}

    # 找出排名变化最大的 Top 10
    changes = []
    for appid, curr_rank in curr_map.items():
        prev_rank = prev_map.get(appid)
        if prev_rank:
            delta = prev_rank - curr_rank  # 正=上升
            if abs(delta) > 0:
                # 获取游戏名
                from storage.db import get_conn
                conn = get_conn()
                row = conn.execute("SELECT name FROM games WHERE appid=?", (appid,)).fetchone()
                conn.close()
                name = row["name"] if row else str(appid)
                changes.append((name, delta, curr_rank))
    changes.sort(key=lambda x: abs(x[1]), reverse=True)
    top_changes = changes[:10]

    if not top_changes:
        return None

    # 取游戏名+排名，按 delta 绝对值排序（最上面是变化最大的）
    items = [(c[0][:20], c[1], c[2]) for c in top_changes]  # (name, delta, rank)
    items.sort(key=lambda x: abs(x[1]), reverse=True)

    names = [it[0] for it in items]
    deltas = [it[1] for it in items]
    curr_ranks = [it[2] for it in items]

    fig, ax = plt.subplots(figsize=(12, 7))
    colors = ["#27ae60" if d > 0 else "#e74c3c" for d in deltas]
    bars = ax.barh(names, deltas, color=colors, edgecolor="white", height=0.6)

    ax.set_xlabel("Rank Change (positive = 上升)", fontsize=10)
    ax.set_title(f"Steam [{label}] 24h Ranking Changes — {datetime.now().strftime('%Y-%m-%d')}", fontsize=12)
    ax.axvline(x=0, color="gray", linewidth=0.8)

    # 用 bar_label 在条形末端标注变化量
    for bar, d, rank in zip(bars, deltas, curr_ranks):
        direction = "↑" if d > 0 else "↓"
        w = bar.get_width()
        offset = 0.3 if w >= 0 else -0.3
        ha = "left" if w >= 0 else "right"
        ax.text(w + offset, bar.get_y() + bar.get_height() / 2,
                f"{direction}{abs(d)}",
                va="center", ha=ha, fontsize=8, color="#333", fontweight="bold")

    # 在最右侧统一标注排名，用细线连接避免重叠
    right_edge = max(deltas) + max(abs(min(deltas)), max(deltas)) * 0.35 + 1
    for bar, d, rank in zip(bars, deltas, curr_ranks):
        y = bar.get_y() + bar.get_height() / 2
        ax.plot([bar.get_width(), right_edge], [y, y],
                color="#ccc", linewidth=0.4, linestyle="--")
        ax.text(right_edge + 0.2, y, f"#{rank}",
                va="center", ha="left", fontsize=7, color="#888")

    plt.tight_layout(pad=1.5)
    fname = f"{chart_key}_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
    fpath = os.path.join(CHART_DIR, fname)
    plt.savefig(fpath, dpi=120, bbox_inches="tight")
    plt.close()
    return fpath


def send_chart_to_lark(image_path, chat_id, title):
    """发送图表图片到飞书群"""
    chart_dir = os.path.dirname(image_path)
    fname = os.path.basename(image_path)
    try:
        result = subprocess.run(
            [LARK_CLI, "im", "+messages-send",
             "--chat-id", chat_id,
             "--image", f"./{fname}",
             "--as", "bot"],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            cwd=chart_dir,
        )
        if result.returncode == 0:
            print(f"[LARK OK] chart sent: {title}")
            return True
        print(f"[LARK ERROR] chart: {result.stderr}")
        return False
    except Exception as e:
        print(f"[LARK ERROR] chart: {e}")
        return False


def generate_and_send_all_charts(chat_id, prev_data, curr_data):
    """生成所有榜单对比图并推送到飞书"""
    results = []
    for chart_key in STEAM_LISTINGS:
        prev = prev_data.get(chart_key, [])
        curr = curr_data.get(chart_key, [])
        if prev and curr:
            path = generate_comparison_chart(chart_key, prev, curr)
            if path:
                send_chart_to_lark(path, chat_id, STEAM_LISTINGS[chart_key]["label"])
                results.append(path)
    return results
