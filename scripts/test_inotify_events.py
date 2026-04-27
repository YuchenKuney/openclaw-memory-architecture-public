#!/usr/bin/env python3
import inotify.adapters, inotify.constants, time, os, json

i = inotify.adapters.Inotify()
wd = i.add_watch('/root/.openclaw/workspace/cron-events', 256)
print(f"watch descriptor: {wd}")

# 写入测试文件
test_file = '/root/.openclaw/workspace/cron-events/_inotify_test.json'
with open(test_file, 'w') as f:
    json.dump({"test": True}, f)
print(f"写入: {test_file}")

# 等待事件
events = []
timeout_at = time.time() + 5
while time.time() < timeout_at:
    e = i.event_gen()
    if e is None:
        break
    for ev in e:
        if ev is None: continue
        header, type_names, path, filename = ev
        events.append((list(type_names), path, filename))
        print(f"捕获: {type_names} {path}/{filename}")

# 删除测试文件
os.remove(test_file)
print(f"事件数: {len(events)}")
