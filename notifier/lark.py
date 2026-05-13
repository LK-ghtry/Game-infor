"""飞书/Lark 消息推送 — 通过 lark-cli 发送预警和日报"""
import subprocess
import json
import os
from config import LARK_CHAT_ID, LARK_NOTIFY_ENABLED

LARK_CLI = r"E:\npm-global\lark-cli.cmd"


def send_alert(alert):
    """发送单条预警到飞书群"""
    if not LARK_NOTIFY_ENABLED or not LARK_CHAT_ID:
        print(f"[NOTIFY SKIP] {alert['message']}")
        return False

    severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
    emoji = severity_emoji.get(alert.get("severity", "info"), "📢")

    post = {
        "zh_cn": {
            "title": f"{emoji} Steam 游戏情报预警",
            "content": [
                [{"tag": "text", "text": alert.get("message", "")}],
                [{"tag": "text", "text": f"时间: {alert.get('time', '')}"}],
            ],
        }
    }
    return _lark_send(post)


def send_daily_report(report_text, alerts_count, games_tracked):
    """发送每日简报到飞书群"""
    if not LARK_NOTIFY_ENABLED or not LARK_CHAT_ID:
        print(f"[NOTIFY SKIP] daily report ({alerts_count} alerts, {games_tracked} games)")
        return False

    post = {
        "zh_cn": {
            "title": "📊 Steam 游戏情报日报",
            "content": [
                [{"tag": "text", "text": report_text[:8000]}],
                [{"tag": "text", "text": f"\n\n📈 追踪 {games_tracked} 款 | 预警 {alerts_count} 条"}],
            ],
        }
    }
    return _lark_send(post)


def _lark_send(post_content):
    """底层：通过 lark-cli api 裸调，@file 方式传 JSON 避免命令行长度/编码问题"""
    try:
        # 构造 API body: content 字段是 post 的 JSON 字符串（二次编码）
        body = {
            "receive_id": LARK_CHAT_ID,
            "msg_type": "post",
            "content": json.dumps(post_content, ensure_ascii=False),
        }

        tmp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".lark_tmp.json")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False)

            result = subprocess.run(
                [LARK_CLI, "api", "POST", "/open-apis/im/v1/messages",
                 "--params", '{"receive_id_type":"chat_id"}',
                 "--data", "@.lark_tmp.json",
                 "--as", "bot"],
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                cwd=os.path.dirname(os.path.dirname(__file__)),
            )
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if result.returncode != 0:
            print(f"[LARK ERROR] {result.stderr}")
            return False
        resp = json.loads(result.stdout)
        if resp.get("code") != 0:
            print(f"[LARK ERROR] {resp.get('msg', result.stdout)}")
            return False
        print(f"[LARK OK] message sent")
        return True
    except FileNotFoundError:
        print("[LARK ERROR] lark-cli not found, is it installed?")
        return False
    except Exception as e:
        print(f"[LARK ERROR] {e}")
        return False
