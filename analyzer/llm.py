"""LLM 深度分析 — 调用 Claude API 生成游戏趋势摘要"""
import requests
import json
import os


def _get_api_config():
    return {
        "base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"),
        "api_key": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "model": os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]"),
    }


def analyze_game(game_info, reviews_summary):
    """对一款游戏进行深度分析，返回中文摘要（100 字以内）"""
    cfg = _get_api_config()
    if not cfg["api_key"]:
        return "[LLM 未配置 API Key]"

    prompt = f"""你是一位资深游戏行业分析师。请用中文简要分析以下游戏为什么正在获得关注（100 字以内）。

游戏名称: {game_info.get('name', 'Unknown')}
类型: {game_info.get('genres', '未知')}
开发商: {game_info.get('developer', '未知')}
简介: {game_info.get('description', '无')}
标签: {game_info.get('tags', '')}
好评率: {reviews_summary.get('review_score_pct', '?')}%
总评论数: {reviews_summary.get('review_total', 0)}

请从以下角度简述：
1. 这款游戏的核心吸引点
2. 目标受众画像
3. 可能的爆发原因
"""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
    }

    body = {
        "model": cfg["model"],
        "max_tokens": 1024,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(
            f"{cfg['base_url']}/messages",
            headers=headers,
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        # 提取所有 text 类型的 block（跳过 thinking 类型）
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if texts:
            return "".join(texts)
        return "[LLM 返回为空]"
    except Exception as e:
        return f"[LLM 分析失败: {e}]"


def analyze_daily_summary(snapshot_count, alerts, chart_data):
    """对当日 Steam 市场数据进行整体分析，返回 150 字以内的中文洞察"""
    cfg = _get_api_config()
    if not cfg["api_key"]:
        return ""

    alert_lines = "\n".join([f"- [{a['severity']}] {a['message']}" for a in alerts[:10]]) or "无预警"

    charts_text = ""
    for label, games in chart_data.items():
        top = ", ".join([f"#{g['rank']} {g['name']}" for g in games[:5]])
        charts_text += f"\n{label}: {top}"

    prompt = f"""你是 Steam 游戏市场分析师。根据以下当日数据，用中文写一段 150 字以内的市场洞察。

今日追踪游戏: {snapshot_count} 款
今日预警: {len(alerts)} 条

预警列表:
{alert_lines}

各榜单 Top 5:
{charts_text}

请分析：
1. 今日 Steam 市场的整体动向和值得关注的趋势
2. 哪些游戏/品类表现突出或异常
3. 对开发者和发行商有何启示

要求：简洁精炼，有洞察而非罗列，150 字以内。"""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
    }

    body = {
        "model": cfg["model"],
        "max_tokens": 2048,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(
            f"{cfg['base_url']}/messages",
            headers=headers,
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        if texts:
            return "".join(texts)
        return ""
    except Exception as e:
        print(f"[LLM 日报分析失败: {e}]")
        return ""


def analyze_trending_list(games_with_details):
    """批量分析多款游戏，每款返回摘要"""
    results = {}
    for g in games_with_details:
        info = g.get("info", {})
        reviews = g.get("reviews", {})
        if info and reviews:
            results[g["appid"]] = analyze_game(info, reviews)
    return results
