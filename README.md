# Game Infor — Steam Game Intelligence Agent

AI-powered Steam game intelligence monitoring agent. Tracks trending new releases, top sellers, and wishlist charts automatically, detects ranking anomalies, and pushes real-time alerts + daily briefings to Lark/Feishu.

## Features

- **Multi-chart monitoring** — Global Top Sellers, New & Trending, Popular Wishlists (50 games each)
- **Trend detection** — New entries, rank spikes, review explosions, rating drops, chart dropouts
- **LLM deep analysis** — Claude-powered game analysis explaining *why* a game is trending
- **Visual comparison charts** — 24h ranking change bar charts auto-generated and pushed
- **Lark/Feishu notifications** — Real-time alerts + structured daily report with charts

## Architecture

```
collector/          → Steam store scraping + official API
storage/            → SQLite persistence (games, snapshots, alerts)
analyzer/           → Rule engine + LLM deep analysis
notifier/           → Lark bot push (post messages + chart images)
visualizer.py       → Matplotlib ranking change charts
monitor.py          → Main pipeline: collect → store → analyze → notify
daily_report.py     → Daily briefing with charts
config.py           → All settings: thresholds, chat_id, schedule
```

## Quick Start

```bash
pip install -r requirements.txt
```

### 1. Configure

Edit `config.py`:
- `LARK_CHAT_ID` — Your Feishu group chat ID
- `LARK_NOTIFY_ENABLED` — Set to `True`
- Thresholds: `RANK_SPIKE_THRESHOLD`, `REVIEW_GROWTH_THRESHOLD`, etc.

### 2. Run

```bash
# Single monitoring run
python -u monitor.py

# Generate daily report with charts
python -u daily_report.py
```

### 3. Schedule

Windows Task Scheduler:
```powershell
$action = New-ScheduledTaskAction -Execute "E:\CC\game agent\run_daily.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
Register-ScheduledTask -TaskName "SteamMonitorDaily" -Action $action -Trigger $trigger
```

## Charts

The visualizer generates ranking change comparison charts for each monitored chart. Charts are automatically pushed to the configured Lark group.

## Requirements

- Python 3.9+
- `requests`, `beautifulsoup4`, `matplotlib`
- `lark-cli` (for Lark/Feishu notifications)
- Claude API access (for LLM analysis)
