#!/usr/bin/env python3
"""纯 inotify 测试脚本 - 先监控再写入"""
import inotify.adapters, inotify.constants, time, os, json, threading

TEST_DIR = '/root/.openclaw/workspace/cron-events'
test_file = f'{TEST_DIR}/_raw_inotify_test.json'

events_captured = []
stop_flag = [False]

def watch_thread():
    i = inotify.adapters.Inotify()
    i.add_watch(TEST_DIR, inotify.constants.IN_ALL_EVENTS)
    print("监控已启动，等待事件...")
    for e in i.event_gen():
        if e is None: continue
        header, type_names, path, filename = e
        events_captured.append((list(type_names), path, filename))
        print(f"事件: {type_names} / {filename}")
        if stop_flag[0]:
            break
    print(f"监控线程退出，共捕获 {len(events_captured)} 个事件")

# 先启动监控
t = threading.Thread(target=watch_thread, daemon=True)
t.start()
time.sleep(1)  # 等监控稳定

# 再写入文件
with open(test_file, 'w') as f:
    json.dump({"raw": True}, f)
print(f"写入: {test_file}")

time.sleep(2)
stop_flag[0] = True
t.join(timeout=3)

# 清理
if os.path.exists(test_file):
    os.remove(test_file)
