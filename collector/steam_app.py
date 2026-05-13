"""Steam 游戏详情 + 评论 API 调用"""
import random
import time
import requests
from config import USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX


def _random_delay():
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def get_app_details(appid):
    """获取游戏详情（developer, publisher, genres, description 等）"""
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid, "cc": "us", "l": "english"}
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        app_data = data.get(str(appid), {})
        if not app_data.get("success"):
            return None

        info = app_data["data"]
        result = {
            "appid": appid,
            "name": info.get("name", ""),
            "developer": ", ".join(info.get("developers", [])),
            "publisher": ", ".join(info.get("publishers", [])),
            "genres": ", ".join(g["description"] for g in info.get("genres", [])),
            "release_date": info.get("release_date", {}).get("date", ""),
            "description": info.get("short_description", ""),
            "price_cents": info.get("price_overview", {}).get("final", 0),
            "header_image": info.get("header_image", ""),
        }
        _random_delay()
        return result
    except Exception as e:
        print(f"[WARN] get_app_details({appid}) failed: {e}")
        return None


def get_app_reviews(appid):
    """获取游戏评论摘要（总评论数、好评率）"""
    url = f"https://store.steampowered.com/appreviews/{appid}"
    params = {"json": "1", "language": "all", "num_per_page": "20", "filter": "summary"}
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return None

        summary = data.get("query_summary", {})
        result = {
            "appid": appid,
            "review_total": summary.get("total_reviews", 0),
            "review_score": summary.get("total_positive", 0),
            "review_score_pct": 0,
            "review_desc": summary.get("review_score_desc", ""),
        }
        if result["review_total"] > 0:
            result["review_score_pct"] = round(
                result["review_score"] / result["review_total"] * 100
            )
        _random_delay()
        return result
    except Exception as e:
        print(f"[WARN] get_app_reviews({appid}) failed: {e}")
        return None


def get_concurrent_players(appid):
    """获取当前并发玩家数（Steam 官方 API）"""
    url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    params = {"appid": appid}
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("player_count", 0)
    except Exception as e:
        print(f"[WARN] get_concurrent_players({appid}) failed: {e}")
        return 0
