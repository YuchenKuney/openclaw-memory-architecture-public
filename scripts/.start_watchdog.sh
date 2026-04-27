#!/bin/bash
exec python3 -u /root/.openclaw/workspace/task_watchdog.py --systemd >> /root/.openclaw/workspace/memory/watchdog.log 2>&1
