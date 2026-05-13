"""Steam 榜单抓取 — 解析搜索页 HTML 提取游戏列表"""
import random
import time
import requests
from bs4 import BeautifulSoup
from config import STEAM_LISTINGS, TOP_N, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, USER_AGENTS


def _get_session():
    session = requests.Session()
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": "birthtime=0; lastagecheckage=1-January-1990; mature_content=1; wants_mature_content=1",
    })
    return session


def _random_delay():
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def _random_ua():
    return random.choice(USER_AGENTS)


def fetch_listing(chart_key):
    """抓取单个 Steam 榜单，返回游戏列表 [{appid, name, price_cents, ...}]"""
    config = STEAM_LISTINGS[chart_key]
    session = _get_session()
    session.headers["User-Agent"] = _random_ua()

    resp = session.get(config["url"], timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    games = []
    rows = soup.select("#search_resultsRows > a")

    for rank, row in enumerate(rows[:TOP_N], start=1):
        appid = row.get("data-ds-appid")
        if not appid:
            continue

        appid = int(appid)

        name_el = row.select_one(".title")
        name = name_el.text.strip() if name_el else "Unknown"

        # 价格
        price_cents = 0
        discount_el = row.select_one(".discount_final_price")
        if discount_el:
            price_text = discount_el.text.strip().replace("$", "").replace(",", "")
            try:
                price_cents = int(float(price_text) * 100)
            except ValueError:
                pass
        else:
            normal_el = row.select_one(".discount_original_price")
            if not normal_el:
                normal_el = row.select_one(".col.search_price")
            if normal_el:
                price_text = normal_el.text.strip()
                if "Free" in price_text or price_text == "":
                    price_cents = 0
                else:
                    price_text = price_text.replace("$", "").replace(",", "")
                    try:
                        price_cents = int(float(price_text) * 100)
                    except ValueError:
                        pass

        # 标签 / 类型
        tags = []
        tag_els = row.select(".col.search_name .tag_name, .tab_item_top_tags .top_tag")
        if not tag_els:
            tag_els = row.select(".top_tag")
        for t in tag_els:
            tag_text = t.text.strip()
            if tag_text:
                tags.append(tag_text)

        # 发售日期
        release_date = ""
        date_el = row.select_one(".col.search_released")
        if date_el:
            release_date = date_el.text.strip()

        # 缩略图
        thumb = ""
        img_el = row.select_one(".col.search_capsule img")
        if img_el:
            thumb = img_el.get("src", "")

        games.append({
            "appid": appid,
            "name": name,
            "price_cents": price_cents,
            "tags": ",".join(tags),
            "release_date": release_date,
            "thumb": thumb,
            "chart_rank": rank,
        })

    _random_delay()
    return games


def fetch_all_listings():
    """抓取所有配置的榜单，返回 {chart_key: [games]}"""
    results = {}
    for chart_key in STEAM_LISTINGS:
        try:
            results[chart_key] = fetch_listing(chart_key)
        except Exception as e:
            print(f"[ERROR] fetch {chart_key} failed: {e}")
            results[chart_key] = []
    return results
