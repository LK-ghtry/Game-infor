"""Bot 私聊监听 — 常驻进程，接收私聊消息并用 LLM 智能回复"""
import subprocess
import json
import sys
import os
from datetime import datetime

LARK_CLI = r"E:\npm-global\lark-cli.cmd"
_llm = None


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def reply_to(chat_id, msg_id, text):
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


def get_status_text():
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
    except Exception as e:
        return f"状态查询失败: {e}"


def get_llm():
    """延迟导入 LLM 配置"""
    global _llm
    if _llm is None:
        from analyzer.llm import _get_api_config
        _llm = _get_api_config()
    return _llm


SYSTEM_PROMPT = """你是「Steam 游戏情报 Agent」，一个专注于 Steam 游戏市场监控的智能助手。

你的能力：
- 每天 9:00 自动采集 Steam 三大榜单（全球热销、热门新品、愿望单）数据
- 生成日报并推送到飞书群，包含 LLM 市场分析洞察
- 监控排名飙升、评论暴涨、好评率暴跌等异常并预警
- 回答关于 Steam 游戏市场、榜单趋势的问题

你的风格：专业、简洁、有洞察。用中文回复，控制在 200 字以内。"""


def chat_with_llm(user_message):
    """用 LLM 进行自然对话"""
    cfg = get_llm()
    if not cfg["api_key"]:
        return None

    import requests

    headers = {
        "Content-Type": "application/json",
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
    }

    body = {
        "model": cfg["model"],
        "max_tokens": 2048,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
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
        return "".join(texts) if texts else None
    except Exception as e:
        log(f"LLM 对话失败: {e}")
        return None


def handle_message(event):
    msg_type = event.get("message_type", "")
    content = event.get("content", "").strip()
    sender_id = event.get("sender_id", "")
    chat_id = event.get("chat_id", "")

    log(f"收到私聊 [{sender_id}]: {content[:100]}")

    # 优先处理特殊命令
    content_lower = content.lower()

    if any(w in content_lower for w in ["状态", "status"]):
        return get_status_text()

    if any(w in content_lower for w in ["日报", "report"]):
        return "我会在每天 9:00 自动生成 Steam 日报并推送到群聊。如需立即查看，可以说「运行日报」触发手动生成。"

    if content_lower in ["运行日报"]:
        log("手动触发日报生成...")
        try:
            r = subprocess.run(
                [r"C:\Python314\python.exe", "-u", "daily_report.py"],
                capture_output=True, text=True, timeout=300, encoding="utf-8",
                cwd=os.path.dirname(__file__),
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            if r.returncode == 0:
                return "日报已生成并推送到群聊，请查看。"
            return f"日报生成失败: {r.stderr[-200:]}"
        except Exception as e:
            return f"日报生成异常: {e}"

    # 其他消息走 LLM 对话
    reply = chat_with_llm(content)
    if reply:
        return reply

    return "抱歉，我暂时无法回复。请稍后再试，或发送「状态」查看监控信息。"


def run():
    log("Bot 私聊监听启动（LLM 模式）...")
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
            stdin=subprocess.PIPE,
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
