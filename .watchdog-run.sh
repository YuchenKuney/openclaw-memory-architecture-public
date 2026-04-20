#!/bin/bash
# watchdog-run.sh - 正确的 double-fork daemon
# 不依赖 task_watchdog.py 的 --daemon 参数，自己实现 daemonize
WORKSPACE="/root/.openclaw/workspace"
PYTHON="/usr/bin/python3"
LOG="$WORKSPACE/memory/watchdog-daemon.log"

echo "[WD] $(date '+%Y-%m-%d %H:%M:%S') Starting watchdog" >> $LOG

# Stage 1: fork
PID1=$(python3 -c "
import os, sys, time
pid = os.fork()
if pid > 0:
    # 父进程：写 PIDFile，等 2 秒，退出
    open('$WORKSPACE/.watchdog.pid', 'w').write(str(pid))
    print(pid, flush=True)
    sys.exit(0)
sys.exit(0)
" 2>> $LOG)
echo "[WD] Stage1 done, PID1=$PID1" >> $LOG

# Stage 2: 子进程成为 session leader，fork 孙进程后退出
WD_CHILD=$(python3 -c "
import os, sys, time
os.chdir('/')
os.setsid()
os.umask(0o022)

pid2 = os.fork()
if pid2 > 0:
    # 写孙进程 PID 到 PIDFile（覆盖 Stage 1 的 PID）
    time.sleep(0.5)
    open('$WORKSPACE/.watchdog.pid', 'w').write(str(pid2))
    sys.exit(0)
else:
    # 孙进程：真正的 watchdog
    os.setsid()
    os.chdir('$WORKSPACE')
    sys.stdout.flush()
    sys.stderr.flush()
    import task_watchdog
    task_watchdog.watchdog_loop(daemon=True, once=False)
" 2>> $LOG)
echo "[WD] Watchdog grandchild=$WD_CHILD" >> $LOG
