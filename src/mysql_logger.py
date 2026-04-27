#!/usr/bin/env python3
"""写入日志到远程MySQL服务器"""
import pymysql
import json
import sys
from datetime import datetime

MYSQL_CONFIG = {
    "host": "178.128.52.85",
    "port": 3306,
    "user": "openclaw",
    "password": "openclaw123",
    "database": "memory_log",
    "charset": "utf8mb4"
}

def log_event(session_key: str, event_type: str, content: str, extra: dict = None):
    """写入一条事件日志"""
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        event_data = json.dumps(extra) if extra else None
        cursor.execute(
            "INSERT INTO memory_events (session_key, event_type, content, event_data) VALUES (%s, %s, %s, %s)",
            (session_key, event_type, content, event_data)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"MySQL log error: {e}", file=sys.stderr)
        return False

def log_task_event(task_id: str, step_id: str, status: str, progress: float, extra: dict = None):
    """写入任务事件"""
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        event_data = json.dumps(extra) if extra else None
        cursor.execute(
            "INSERT INTO task_events (task_id, step_id, status, progress, event_data) VALUES (%s, %s, %s, %s, %s)",
            (task_id, step_id, status, progress, event_data)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"MySQL task log error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: mysql_logger.py <session_key> <event_type> <content> [json_extra]")
        sys.exit(1)
    
    session_key = sys.argv[1]
    event_type = sys.argv[2]
    content = sys.argv[3]
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    
    log_event(session_key, event_type, content, extra)
