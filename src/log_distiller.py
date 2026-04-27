#!/usr/bin/env python3
"""每日日志蒸馏脚本 - 18:30执行"""
import pymysql
import json
import sys
import os
from datetime import datetime, date
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

MYSQL_CONFIG = {
    "host": "178.128.52.85",
    "port": 3306,
    "user": "openclaw",
    "password": "openclaw123",
    "database": "memory_log",
    "charset": "utf8mb4"
}

WORKSPACE = Path("/root/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"

def get_today_events():
    """获取今天的所有事件"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    today = date.today().isoformat()
    cursor.execute("""
        SELECT session_key, event_type, content, event_data, created_at 
        FROM memory_events 
        WHERE DATE(created_at) = %s
        ORDER BY created_at ASC
    """, (today,))
    
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return events

def distill_events(events):
    """蒸馏事件 - 提取关键信息生成摘要"""
    if not events:
        return "今日无事件记录。", []
    
    # 按session分组
    sessions = {}
    for e in events:
        sk = e['session_key']
        if sk not in sessions:
            sessions[sk] = []
        sessions[sk].append(e)
    
    # 生成摘要
    summary_parts = [f"## {date.today().isoformat()} 日志蒸馏报告\n"]
    summary_parts.append(f"**总事件数**: {len(events)}")
    summary_parts.append(f"**会话数**: {len(sessions)}\n")
    
    # 按类型统计
    type_count = {}
    for e in events:
        t = e['event_type']
        type_count[t] = type_count.get(t, 0) + 1
    
    summary_parts.append("### 事件类型统计")
    for t, c in sorted(type_count.items(), key=lambda x: -x[1]):
        summary_parts.append(f"- {t}: {c}")
    summary_parts.append("")
    
    # 重要事件提取
    important = [e for e in events if e['event_type'] in ('task_done', 'error', 'decision', 'user_request')]
    
    if important:
        summary_parts.append("### 重要事件")
        for e in important[:20]:  # 最多20条
            content = e['content'][:200] + "..." if len(e['content']) > 200 else e['content']
            ts = e['created_at'].strftime("%H:%M")
            summary_parts.append(f"- [{ts}] **{e['event_type']}**: {content}")
        summary_parts.append("")
    
    # 生成可执行建议
    suggestions = generate_suggestions(events)
    if suggestions:
        summary_parts.append("### 执行建议")
        for s in suggestions:
            summary_parts.append(f"- {s}")
        summary_parts.append("")
    
    return "\n".join(summary_parts), list(sessions.keys())

def generate_suggestions(events):
    """根据事件生成执行建议"""
    suggestions = []
    errors = [e for e in events if e['event_type'] == 'error']
    if errors:
        suggestions.append(f"关注 {len(errors)} 个错误需要处理")
    
    tasks = [e for e in events if e['event_type'] == 'task_pending']
    if tasks:
        suggestions.append(f"有 {len(tasks)} 个任务待完成")
    
    return suggestions

def save_to_long_memory(summary: str, session_keys: list):
    """保存到长期记忆"""
    today = date.today()
    today_str = today.isoformat()
    
    # 保存每日摘要
    summary_file = MEMORY_DIR / f"{today_str}.md"
    
    # 如果文件已存在，追加
    if summary_file.exists():
        existing = summary_file.read_text()
        # 检查是否已蒸馏过
        if "日志蒸馏报告" in existing:
            print(f"今日已蒸馏，跳过: {summary_file}")
            return
        content = existing + "\n\n" + summary
    else:
        content = summary
    
    summary_file.write_text(content)
    
    # 保存会话详情到sessions目录
    sessions_dir = MEMORY_DIR / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    
    for sk in session_keys:
        safe_name = sk.replace("/", "_").replace(":", "_")[:50]
        session_file = sessions_dir / f"{today_str}_{safe_name}.json"
        
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT * FROM memory_events 
            WHERE DATE(created_at) = %s AND session_key = %s
            ORDER BY created_at ASC
        """, (today_str, sk))
        session_events = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 转换为可序列化的格式
        serializable = []
        for e in session_events:
            ce = dict(e)
            if ce.get('event_data'):
                ce['event_data'] = json.loads(ce['event_data'])
            ce['created_at'] = ce['created_at'].isoformat()
            serializable.append(ce)
        
        session_file.write_text(json.dumps(serializable, ensure_ascii=False, indent=2))
    
    return True

def cleanup_old_events(days: int = 7):
    """清理旧事件（保留7天）"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM memory_events 
        WHERE DATE(created_at) < DATE_SUB(CURDATE(), INTERVAL %s DAY)
    """, (days,))
    
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    return deleted

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始日志蒸馏...")
    
    # 1. 获取今天事件
    events = get_today_events()
    print(f"获取到 {len(events)} 条事件")
    
    # 2. 蒸馏
    summary, session_keys = distill_events(events)
    print(f"蒸馏完成，生成摘要")
    
    # 3. 保存到长期记忆
    if events:
        save_to_long_memory(summary, session_keys)
        print(f"已保存到 {MEMORY_DIR}")
    
    # 4. 清理旧数据
    deleted = cleanup_old_events(7)
    print(f"清理了 {deleted} 条旧事件")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 蒸馏完成!")
