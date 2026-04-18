#!/usr/bin/env python3
"""
Clawkeeper Responder - 自动审核响应器
监听坤哥的「允许/拒绝」指令，自动执行对应操作
"""

import os
import sys
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

# 坤哥飞书 chat ID
KUNGE_ID = "ou_c079cf9f93da3030aacb081900d55a8e"

# 允许的指令
ALLOWED_COMMANDS = {"允许", "拒绝", "allow", "reject", "同意", "cancel"}

# 指令缓存（防止重复处理）
processed = set()


class CommandResponder:
    """指令响应器"""
    
    def __init__(self, interceptor, notifier):
        self.interceptor = interceptor
        self.notifier = notifier
        self.last_check = datetime.now() - timedelta(seconds=30)
        
    def check_messages(self):
        """检查最新消息（需要通过 OpenClaw API 或飞书 API）"""
        # 这里通过读取 OpenClaw 的会话消息来实现
        # 实际由 OpenClaw session 消息触发
        pass
        
    def process_command(self, command, event_info):
        """
        处理指令
        command: "允许" / "拒绝"
        event_info: 关联的事件信息
        """
        cmd_lower = command.lower().strip()
        
        if cmd_lower not in ALLOWED_COMMANDS:
            return False, f"未知指令: {command}"
            
        path = event_info.get("path", "")
        
        if cmd_lower in {"允许", "allow", "同意"}:
            # 放行
            success, msg = self.interceptor.approve(path)
            self.notifier.send_simple(f"✅ 已放行: {path}", "SUCCESS")
            return success, msg
            
        elif cmd_lower in {"拒绝", "reject", "cancel"}:
            # 拒绝 + 回退
            success, msg = self.interceptor.reject(path, rollback=True)
            self.notifier.send_simple(f"❌ 已拒绝并回退: {path}", "WARN")
            return success, msg
            
        return False, "未处理"
        
    def handle_reply(self, text, chat_id=None):
        """
        处理坤哥的回复（由 OpenClaw 消息触发）
        text: 消息内容
        chat_id: 发送者 ID
        """
        # 只处理坤哥的消息
        if chat_id and chat_id != KUNGE_ID:
            return None
            
        # 提取指令
        cmd = None
        for keyword in ["允许", "allow", "同意", "拒绝", "reject", "cancel"]:
            if keyword in text.lower():
                cmd = keyword if keyword in {"允许", "拒绝", "同意"} else text.strip()
                break
                
        if not cmd:
            return None
            
        # 查找最近的待审核事件
        pending = self.interceptor.get_pending()
        if not pending:
            return None
            
        # 取最新的一个
        latest_path, pending_info = pending[-1]
        
        event_info = {
            "path": latest_path,
            "command": cmd,
            "timestamp": time.time(),
        }
        
        # 防重复
        msg_key = f"{latest_path}:{cmd}"
        if msg_key in processed:
            return None
        processed.add(msg_key)
        
        success, msg = self.process_command(cmd, event_info)
        
        return {"success": success, "message": msg, "path": latest_path}


class FeishuMessageListener:
    """
    飞书消息监听器
    通过轮询飞书开放平台 API 获取最新消息
    """
    
    def __init__(self, responder, feishu_app_id=None, feishu_app_secret=None):
        self.responder = responder
        self.app_id = feishu_app_id or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = feishu_app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self.token = None
        self.token_expires = 0
        self.running = False
        self._thread = None
        
    def get_token(self):
        """获取 tenant_access_token"""
        if time.time() < self.token_expires - 60:
            return self.token
            
        try:
            import urllib.request
            
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            data = json.dumps({
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }).encode()
            
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    self.token = result["tenant_access_token"]
                    self.token_expires = time.time() + result.get("expire", 7200)
                    return self.token
        except Exception as e:
            print(f"[Listener] 获取 token 失败: {e}")
            
        return None
        
    def fetch_messages(self, container_id, container_id_type="chat"):
        """拉取最新消息"""
        token = self.get_token()
        if not token:
            return []
            
        try:
            import urllib.request
            
            # 获取群消息
            url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type={container_id_type}&container_id={container_id}&sort_type=ByCreateTimeDesc&page_size=10"
            
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    return result.get("data", {}).get("items", [])
        except Exception as e:
            print(f"[Listener] 拉取消息失败: {e}")
            
        return []
        
    def poll_messages(self):
        """轮询消息"""
        self.running = True
        
        # 坤哥群的 container_id
        container_id = "oc_0533b03e077fedca255c4d2c6717deea"
        
        while self.running:
            try:
                messages = self.fetch_messages(container_id)
                
                for msg in messages:
                    sender = msg.get("sender", {}).get("id", "")
                    body = msg.get("body", {})
                    content = body.get("content", "")
                    
                    # 解析消息
                    try:
                        msg_data = json.loads(content)
                        text = msg_data.get("text", "")
                    except:
                        text = content
                        
                    # 处理指令
                    if sender == KUNGE_ID:
                        result = self.responder.handle_reply(text, chat_id=sender)
                        if result:
                            print(f"[Listener] 处理指令: {result}")
                            
            except Exception as e:
                print(f"[Listener] 轮询异常: {e}")
                
            time.sleep(5)  # 每5秒轮询
            
    def start(self):
        """启动监听"""
        if self._thread and self._thread.is_alive():
            return
            
        self._thread = threading.Thread(target=self.poll_messages, daemon=True)
        self._thread.start()
        print("[Listener] 飞书消息监听已启动")
        
    def stop(self):
        """停止监听"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[Listener] 飞书消息监听已停止")


def main():
    """测试用主程序"""
    sys.path.insert(0, str(Path(__file__).parent))
    
    from interceptor import Interceptor
    from detector import RiskDetector
    from notifier import FeishuNotifier
    
    detector = RiskDetector()
    notifier = FeishuNotifier()
    interceptor = Interceptor(detector, notifier)
    responder = CommandResponder(interceptor, notifier)
    
    # 测试处理拒绝指令
    test_event = {
        "path": "/root/.openclaw/workspace/AGENTS.md",
        "command": "拒绝",
    }
    
    # 模拟添加一个待审核事件
    from detector import Action, RiskLevel
    action = Action(
        level=RiskLevel.CRITICAL,
        action_type="BLOCK",
        message="测试拒绝",
        details=test_event
    )
    interceptor.block(action)
    
    # 处理拒绝
    result = responder.handle_reply("拒绝", chat_id=KUNGE_ID)
    print(f"处理结果: {result}")


if __name__ == "__main__":
    main()
