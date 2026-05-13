"""Steam 游戏情报监控 Agent — 配置中心"""

# --- 采集配置 ---
STEAM_LISTINGS = {
    "global_top_sellers": {
        "url": "https://store.steampowered.com/search/?filter=globaltopsellers&cc=us",
        "label": "全球热销",
    },
    "popular_new": {
        "url": "https://store.steampowered.com/search/?filter=popularnew&cc=us",
        "label": "热门新品",
    },
    "wishlist": {
        "url": "https://store.steampowered.com/search/?filter=popularwishlist&cc=us",
        "label": "愿望单",
    },
}

# 每个榜单抓取前 N 名
TOP_N = 50
# 获取详情/评论的 Top N（仅每个榜单前 N 名拉取完整数据）
TOP_DETAIL_N = 10
# 请求间隔范围（秒）
REQUEST_DELAY_MIN = 0.3
REQUEST_DELAY_MAX = 1.0
# 用户代理池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

# --- 预警阈值 ---
RANK_SPIKE_THRESHOLD = 20        # 排名上升超过 20 位视为飙升
REVIEW_GROWTH_THRESHOLD = 0.5    # 评论数增长率超过 50% 视为爆炸
SCORE_DROP_THRESHOLD = 10         # 好评率下降超过 10 个百分点视为暴跌

# --- 数据库 ---
DB_PATH = "E:/CC/game agent/data/steam_monitor.db"

# --- Lark 通知 ---
LARK_CHAT_ID = "oc_a46681999cc3d340fd8d9b662ba9e31d"
LARK_NOTIFY_ENABLED = True
