#!/usr/bin/env python3
"""
Clawkeeper Auditor - 审计报告生成器
生成周期性审计报告，总结 AI 行为
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path


class Auditor:
    """审计器"""
    
    def __init__(self, audit_log_path=None):
        self.audit_log_path = audit_log_path or os.environ.get(
            "CLAWKEEPER_AUDIT_LOG",
            "/root/.openclaw/workspace/clawkeeper/audit.log"
        )
        
    def get_entries(self, since=None, until=None, level_filter=None):
        """
        获取审计日志条目
        since/until: Unix timestamp 或 datetime
        level_filter: RiskLevel 名称列表
        """
        entries = []
        
        if not os.path.exists(self.audit_log_path):
            return entries
            
        # 时间标准化
        if isinstance(since, datetime):
            since_ts = since.timestamp()
        elif since is None:
            since_ts = 0
        else:
            since_ts = since
            
        if isinstance(until, datetime):
            until_ts = until.timestamp()
        elif until is None:
            until_ts = float("inf")
        else:
            until_ts = until
            
        with open(self.audit_log_path) as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # 时间过滤
                    entry_ts = entry.get("time")
                    if entry_ts:
                        try:
                            dt = datetime.fromisoformat(entry_ts.replace("Z", "+00:00"))
                            if not (since_ts <= dt.timestamp() <= until_ts):
                                continue
                        except:
                            pass
                            
                    # 等级过滤
                    if level_filter:
                        if entry.get("level") not in level_filter:
                            continue
                            
                    entries.append(entry)
                    
                except json.JSONDecodeError:
                    continue
                    
        return entries
        
    def generate_report(self, period_hours=24):
        """
        生成审计报告
        period_hours: 报告周期（小时）
        """
        since = time.time() - (period_hours * 3600)
        entries = self.get_entries(since=since)
        
        # 统计
        stats = {
            "total": len(entries),
            "by_level": {},
            "by_event": {},
            "blocked": 0,
            "paused": 0,
            "allowed": 0,
        }
        
        for entry in entries:
            level = entry.get("level", "UNKNOWN")
            event = entry.get("event", "UNKNOWN")
            action_type = entry.get("action", {}).get("action_type", "UNKNOWN")
            
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            stats["by_event"][event] = stats["by_event"].get(event, 0) + 1
            
            if action_type == "BLOCK":
                stats["blocked"] += 1
            elif action_type == "PAUSE":
                stats["paused"] += 1
            elif action_type == "LOG":
                stats["allowed"] += 1
                
        # 构建报告
        report = {
            "period": {
                "hours": period_hours,
                "since": datetime.fromtimestamp(since).isoformat(),
                "until": datetime.now().isoformat(),
            },
            "summary": stats,
            "entries": entries[-50:],  # 最近50条
        }
        
        return report
        
    def format_text_report(self, period_hours=24):
        """生成文本格式报告"""
        report = self.generate_report(period_hours)
        
        lines = [
            "=" * 50,
            f"🛡️ Clawkeeper 审计报告（过去{period_hours}小时）",
            "=" * 50,
            "",
            f"总事件数: {report['summary']['total']}",
            f"  🔴 拦截: {report['summary']['blocked']}",
            f"  ⚠️ 暂停: {report['summary']['paused']}",
            f"  ✅ 放行: {report['summary']['allowed']}",
            "",
            "按风险等级:",
        ]
        
        for level, count in sorted(report["summary"]["by_level"].items()):
            lines.append(f"  {level}: {count}")
            
        lines.append("")
        lines.append("按事件类型:")
        for event, count in sorted(report["summary"]["by_event"].items()):
            lines.append(f"  {event}: {count}")
            
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
        
    def save_report(self, period_hours=24, output_path=None):
        """保存报告到文件"""
        if output_path is None:
            output_path = os.environ.get(
                "CLAWKEEPER_REPORT",
                f"/root/.openclaw/workspace/clawkeeper/reports/audit_{int(time.time())}.json"
            )
            
        report = self.generate_report(period_hours)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        return output_path


if __name__ == "__main__":
    auditor = Auditor()
    
    # 生成24小时报告
    print(auditor.format_text_report(period_hours=24))
    
    # 保存 JSON 报告
    report_path = auditor.save_report(24)
    print(f"\n报告已保存: {report_path}")
