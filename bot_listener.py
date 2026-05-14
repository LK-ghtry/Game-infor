"""Bot 私聊监听 — 常驻进程，接收私聊消息并自动回复"""
import subprocess
import json
import sys
import os
from datetime import datetime

LARK_CLI = r"E:\npm-global\lark-cli.cmd"


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def reply_to(chat_id, msg_id, text):
    """回复私聊消息"""
    body = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }
    tmp = os.path.join(os.path.dirname(__file__), ".reply_tmp.json")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
        result = subprocess.run(
            [LARK_CLI, "api", "POST", "/open-apis/im/v1/messages",
             "--params", '{"receive_id_type":"chat_id"}',
             "--data", "@.reply_tmp.json",
             "--as", "bot"],
            capture_output=True, text=True, timeout=15, encoding="utf-8",
            cwd=os.path.dirname(__file__),
        )
        if result.returncode != 0:
            log(f"回复失败: {result.stderr}")
            return False
        resp = json.loads(result.stdout)
        if resp.get("code") != 0:
            log(f"回复失败: {resp.get('msg')}")
            return False
        return True
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def handle_message(event):
    """处理单条私聊消息，返回回复文本"""
    msg_type = event.get("message_type", "")
    content = event.get("content", "").strip()
    sender_id = event.get("sender_id", "")
    chat_id = event.get("chat_id", "")

    log(f"收到私聊 [{sender_id}]: {content[:100]}")

    # 简单关键字匹配
    content_lower = content.lower()

    if any(w in content_lower for w in ["你好", "hello", "hi", "在吗", "bot"]):
        return (
            "你好！我是 Steam 游戏情报监控 Bot。\n\n"
            "我会在每天 9:00 自动推送 Steam 三大榜单的日报到群里。\n\n"
            "你可以私聊我以下关键词：\n"
            "• 日报 / report — 查看最近动态\n"
            "• 状态 / status — 查看监控状态\n"
            "• 帮助 / help — 显示此消息"
        )

    if any(w in content_lower for w in ["日报", "report"]):
        return "日报功能已集成到每日 9:00 自动推送。如需手动触发，请联系管理员运行 daily_report.py。"

    if any(w in content_lower for w in ["状态", "status"]):
        # 读取数据库统计
        try:
            from storage.db import get_conn
            conn = get_conn()
            game_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            snap_count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            last_snap = conn.execute("SELECT MAX(snapshot_time) FROM snapshots").fetchone()[0]
            alert_count = conn.execute("SELECT COUNT(*) FROM alerts WHERE date(created_at)=date('now')").fetchone()[0]
            conn.close()
            return (
                f"Steam 监控状态\n"
                f"• 追踪游戏: {game_count} 款\n"
                f"• 累计快照: {snap_count} 条\n"
                f"• 最后采集: {last_snap}\n"
                f"• 今日预警: {alert_count} 条\n"
                f"• 下次日报: 每天 9:00"
            )
        except Exception:
            return "状态查询暂时不可用，请稍后再试。"

    if any(w in content_lower for w in ["帮助", "help"]):
        return (
            "可用命令：\n"
            "• 日报 / report\n"
            "• 状态 / status\n"
            "• 帮助 / help\n\n"
            "每日 9:00 自动推送日报到群聊。"
        )

    # 默认回复
    return (
        "收到消息，但我暂时无法理解。\n"
        "试试发送「帮助」查看我能做什么。"
    )


def run():
    log("Bot 私聊监听启动...")
    while True:
        log("启动事件监听...")
        proc = subprocess.Popen(
            [LARK_CLI, "event", "consume", "im.message.receive_v1",
             "--as", "bot",
             "--jq", 'select(.chat_type=="p2p" and .message_type=="text")'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            stdin=subprocess.PIPE,  # keep stdin open to prevent EOF shutdown
        )

        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    reply_text = handle_message(event)
                    chat_id = event.get("chat_id", "")
                    if chat_id and reply_text:
                        reply_to(chat_id, event.get("message_id", ""), reply_text)
                        log(f"已回复 [{chat_id}]")
                except json.JSONDecodeError:
                    log(f"解析事件失败: {line[:200]}")
                except Exception as e:
                    log(f"处理消息异常: {e}")
        except Exception as e:
            log(f"监听连接断开: {e}")
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()

        log("5秒后重连...")
        import time
        time.sleep(5)


if __name__ == "__main__":
    run()
