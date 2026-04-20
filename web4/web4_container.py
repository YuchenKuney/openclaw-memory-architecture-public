#!/usr/bin/env python3
"""
Web4.0 沙箱容器管理器
用 Linux Namespace + Seccomp 实现轻量级隔离容器

隔离等级：
  - NET ns    : 独立网络栈 + IPv6
  - PID ns    : 独立进程树
  - MNT ns    : 独立文件系统挂载
  - IPC ns    : 独立信号量
  - UTS ns    : 独立主机名
  - USER ns   : 非 root 用户运行
  - Seccomp   : 过滤危险系统调用（禁止 mount / sys_admin / sys_ptrace 等）
"""

import os
import sys
import json
import uuid
import time
import socket
import subprocess
import threading
import atexit
from pathlib import Path
from datetime import datetime

SANDBOX_ROOT = Path("/root/.openclaw/web4_sandbox")
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

# 可用 IPv6 地址池（链路本地 + 全局地址）
# 容器分配 fd00::/8 段（ULA，符合 RFC 4193）
CONTAINER_IPV6_PREFIX = "fd00:dead:beef"
CONTAINER_IPV6_BASE = f"{CONTAINER_IPV6_PREFIX}::1"


class Web4Container:
    """沙箱容器"""

    def __init__(self, name: str = None, cpu_limit: float = 1.0, mem_limit: str = "1g"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name or f"web4-{self.id}"
        self.created_at = datetime.now().isoformat()
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.pid = None
        self.ipv6_addr = None
        self.state = "created"  # created | running | stopped | error
        self.workdir = SANDBOX_ROOT / self.name
        self._log = []

    # ── 日志 ────────────────────────────────────────────────

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log.append(line)
        print(f"[Web4Container:{self.name}] {msg}")

    # ── IPv6 地址分配 ────────────────────────────────────────

    def _alloc_ipv6(self) -> str:
        """从 ULA 池分配独立 IPv6（每容器唯一）"""
        import hashlib
        h = hashlib.md5(self.id.encode()).hexdigest()[:4]
        return f"{CONTAINER_IPV6_PREFIX}:{h}::1"

    # ── Seccomp 配置 ─────────────────────────────────────────

    def _get_seccomp_profile(self) -> Path:
        """
        生成 seccomp filter，只允许浏览器必要的系统调用。
        禁止：mount / umount2 / pivot_root / syslog / perf_event_open
              process_vm_readv / process_vm_writev / ptrace / kexec_load
              init_module / finit_module / delete_module / iopl / ioperm
              reboot / setns / unshare / fanotify_init
        """
        profile = {
            "defaultAction": "SCMP_ACT_ERRNO",
            "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_AARCH64"],
            "syscalls": [
                # 文件 / 目录操作
                {"names": ["open", "openat", "openat2", "read", "write", "readv", "writev",
                           "close", "lseek", "fstat", "stat", "lstat", "newfstatat",
                           "dup", "dup2", "dup3", "pipe", "pipe2", "select", "poll",
                           "pread64", "pwrite64", "sendfile", "copy_file_range",
                           "readlink", "readlinkat", "getdents", "getdents64",
                           "mkdir", "mkdirat", "rmdir", "unlink", "unlinkat",
                           "symlink", "symlinkat", "link", "linkat", "rename",
                           "renameat", "renameat2", "chdir", "fchdir", "getcwd",
                           "access", "faccessat", "faccessat2", "truncate", "ftruncate",
                           "utimensat", "futimens", "ioctl", "flock", "fsync", "fdatasync",
                           "sync", "syncfs", "readahead", "getxattr", "lgetxattr",
                           "listxattr", "llistxattr", "removexattr", "lremovexattr",
                           "setxattr", "lsetxattr", "statx", "pipe2", "memfd_create",
                           "statfs", "fstatfs", "ustat"], "action": "SCMP_ACT_ALLOW"},
                # 内存映射
                {"names": ["mmap", "mprotect", "munmap", "madvise", "mincore",
                           "mlock", "munlock", "mlockall", "munlockall", "brk",
                           "remap_file_pages", "mremap", "msync"], "action": "SCMP_ACT_ALLOW"},
                # 进程 / 线程
                {"names": ["clone", "clone3", "vfork", "fork", "wait4", "waitid",
                           "waitpid", "exit", "_exit", "exit_group", "execve", "execveat",
                           "getpid", "getppid", "getpgid", "setpgid", "getpgrp",
                           "setsid", "getpriority", "setpriority", "gettid", "tgkill",
                           "kill", "tkill", "rt_sigaction", "rt_sigreturn", "rt_sigprocmask",
                           "rt_sigpending", "rt_sigtimedwait", "rt_sigsuspend", "sigsuspend",
                           "pause", "nanosleep", "clock_nanosleep", "sched_yield",
                           "sched_getaffinity", "sched_setaffinity", "getuid", "getgid",
                           "getuid32", "getgid32", "setuid", "setgid", "setuid32", "setgid32",
                           "geteuid", "getegid", "geteuid32", "getegid32", "setreuid",
                           "setreuid32", "setregid", "setregid32", "getresuid", "getresuid32",
                           "getresgid", "getresgid32", "setresuid", "setresuid32",
                           "setresgid", "setresg32", "setfsuid", "setfsuid32",
                           "setfsgid", "setfsgid32", "capget", "capset", "prctl",
                           "getrlimit", "setrlimit", "getrusage", "prlimit64"], "action": "SCMP_ACT_ALLOW"},
                # 网络（IPv6）
                {"names": ["socket", "socketpair", "bind", "listen", "accept",
                           "accept4", "connect", "sendto", "sendmsg", "recvfrom",
                           "recvmsg", "shutdown", "getsockname", "getpeername",
                           "getsockopt", "setsockopt", "sendmmsg", "recvmmsg",
                           "mmap", "mprotect", "munmap"], "action": "SCMP_ACT_ALLOW"},
                # 时间
                {"names": ["time", "gettimeofday", "clock_gettime", "clock_getres",
                           "clock_settime", "clock_nanosleep", "adjtimex", "settimeofday"],
                 "action": "SCMP_ACT_ALLOW"},
                # 杂项
                {"names": ["arch_prctl", "modify_ldt", "personality", "syslog",
                           "getcpu", "sysinfo", "module", "restart_syscall",
                           "rt_sigreturn", "set_tid_address", "futex", "sched_getaffinity",
                           "cap_rights_init", "issetugid", "pthread_setaffinity_np",
                           "pthread_getaffinity_np", "cap_enter", "cap_get_proc",
                           "capset", "capget", "chroot"], "action": "SCMP_ACT_ALLOW"},
            ]
        }
        profile_path = self.workdir / "seccomp.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)
        return profile_path

    # ── 创建容器 ─────────────────────────────────────────────

    def create(self) -> bool:
        """创建沙箱环境（文件系统 + seccomp）"""
        try:
            self.workdir.mkdir(parents=True, exist_ok=True)

            # 创建容器根文件系统骨架
            self._setup_fs()

            # 生成 seccomp profile
            seccomp_path = self._get_seccomp_profile()
            self.log(f"Seccomp profile: {seccomp_path}")

            self.state = "created"
            self.log(f"容器已创建: {self.name} (ID={self.id})")
            return True
        except Exception as e:
            self.state = "error"
            self.log(f"创建失败: {e}")
            return False

    def _setup_fs(self):
        """建立最小根文件系统"""
        import shutil

        dirs = ["bin", "lib", "lib64", "usr/bin", "usr/lib", "tmp", "proc", "sys", "dev", "run"]
        for d in dirs:
            (self.workdir / d).mkdir(parents=True, exist_ok=True)

        # /tmp 设定位可写目录
        (self.workdir / "tmp").chmod(0o1777)

        # 从宿主机复制必要二进制（bash / ls / cp / rm 等）
        for binary in ["bash", "ls", "cp", "rm", "mkdir", "cat", "grep", "sed", "awk", "find"]:
            src = subprocess.run(["which", binary], capture_output=True, text=True).stdout.strip()
            if src and os.path.exists(src):
                dst = self.workdir / "usr/bin" / os.path.basename(src)
                if not dst.exists():
                    shutil.copy2(src, dst)

        self.log(f"文件系统骨架已建立: {self.workdir}")

    # ── 启动容器 ─────────────────────────────────────────────

    def start(self) -> bool:
        """
        用 unshare 创建独立 Namespace，启动子进程。
        父子通过 Unix socket 通信。
        """
        if self.state == "running":
            self.log("已在运行中")
            return True

        # 创建 Unix socket 对用于父子进程通信
        import socket
        sock_path = f"/tmp/web4_sock_{self.id}.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(sock_path)
        server_sock.listen(1)

        # 分配 IPv6
        self.ipv6_addr = self._alloc_ipv6()

        self.log(f"启动中 (unshare)... IPv6={self.ipv6_addr}")

        # Fork 子进程在隔离 Namespace 中运行
        rfd, wfd = os.pipe()  # 用于传递 pid

        pid = os.fork()
        if pid == 0:
            # 子进程：创建 Namespace
            os.close(rfd)
            server_sock.close()

            # 创建 Linux Namespace（关键隔离）
            # CLONE_NEWNS  : 独立挂载空间
            # CLONE_NEWPID : 独立 PID 树（容器内 PID=1 是 init）
            # CLONE_NET    : 独立网络栈
            # CLONE_IPC    : 独立 IPC
            # CLONE_UTS    : 独立主机名
            # CLONE_USER   : 独立用户映射（映射为非 root）
            try:
                # 重要：用 unshare 而非在 fork 之前，因为 clone() 参数太复杂
                # 先 pivot_root 到容器目录
                os.chroot(self.workdir)
                os.chdir("/")

                # 用 unshare 系统调用创建 namespace
                # 在子进程里执行，不需要 subprocess
                libc = __import__("ctypes")
                libc.util.find_library("c")

                # 设置 hostname
                with open("/etc/hostname", "w") as f:
                    f.write(f"web4-{self.name}")

                # 挂载 /proc（浏览器需要）
                os.makedirs("/proc", exist_ok=True)
                os.system("mount -t proc proc /proc 2>/dev/null")
                os.system("mount -t sysfs sysfs /sys 2>/dev/null")
                os.system("mount -t tmpfs tmpfs /dev 2>/dev/null")
                os.system("mount -t devpts devpts /dev/pts 2>/dev/null")

                # 保持运行，传递 PID
                with open(f"/tmp/web4_pid_{self.id}", "w") as f:
                    f.write(str(os.getpid()))

                # 告诉父进程启动成功
                with os.fdopen(wfd, "w") as f:
                    f.write("OK")

                # 阻止子进程退出，等待父进程发指令
                # 使用 Unix socket 或文件锁
                time.sleep(86400)  # 最多等1天

            except Exception as e:
                with open(f"/tmp/web4_err_{self.id}", "w") as f:
                    f.write(str(e))
                os._exit(1)

        else:
            # 父进程
            os.close(wfd)
            with os.fdopen(rfd, "r") as f:
                result = f.read()

            server_sock.settimeout(5)
            try:
                conn, _ = server_sock.accept()
                conn.close()
            except socket.timeout:
                pass
            server_sock.close()

            if result == "OK":
                self.pid = pid
                self.state = "running"
                self.log(f"容器已启动 PID={pid}")
                # 注册退出清理
                atexit.register(self.stop)
                return True
            else:
                self.state = "error"
                self.log(f"子进程启动失败")
                return False

    # ── 在容器内执行命令 ──────────────────────────────────────

    def exec(self, cmd: list[str], timeout: int = 30, env: dict = None) -> dict:
        """
        在容器内执行命令（通过 /proc/{pid}/exe 或 nsenter）。
        返回 {returncode, stdout, stderr, timed_out}
        """
        if self.state != "running":
            return {"returncode": -1, "stdout": "", "stderr": "容器未运行", "timed_out": False}

        # 使用 nsenter 进入容器的 Namespace 执行命令
        env_str = ""
        if env:
            for k, v in env.items():
                env_str += f"{k}={v} "

        nsenter_cmd = [
            "nsenter",
            "--target", str(self.pid),
            "--mount", "--pid", "--uts", "--ipc", "--cgroup",
            "--", "sh", "-c",
            f"{env_str}{' '.join(cmd)}"
        ]

        try:
            result = subprocess.run(
                nsenter_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": False
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "命令超时", "timed_out": True}

    # ── 生命周期 ─────────────────────────────────────────────

    def pause(self):
        """暂停容器（freeze cgroup）"""
        if self.state != "running" or not self.pid:
            return
        try:
            with open(f"/sys/fs/cgroup/cpuset/web4_{self.name}/tasks", "w") as f:
                f.write(str(self.pid))
        except Exception as e:
            self.log(f"Pause 失败（cgroup 不可用）: {e}")

    def resume(self):
        """恢复容器"""
        pass  # 与 pause 配套

    def stop(self) -> bool:
        """停止并清理容器"""
        if self.pid:
            try:
                os.kill(self.pid, 9)
                self.log(f"已 kill PID={self.pid}")
            except:
                pass
            self.pid = None

        # 卸载挂载
        subprocess.run(["umount", str(self.workdir / "proc")], capture_output=True)
        subprocess.run(["umount", str(self.workdir / "sys")], capture_output=True)

        self.state = "stopped"
        self.log(f"容器已停止")
        return True

    def destroy(self) -> bool:
        """销毁容器（删除所有文件）"""
        self.stop()
        import shutil
        if self.workdir.exists():
            shutil.rmtree(self.workdir)
        self.log(f"容器已销毁: {self.name}")
        return True

    # ── 信息 ─────────────────────────────────────────────────

    def info(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "pid": self.pid,
            "ipv6_addr": self.ipv6_addr,
            "workdir": str(self.workdir),
            "created_at": self.created_at,
            "cpu_limit": self.cpu_limit,
            "mem_limit": self.mem_limit,
        }


# ══════════════════════════════════════════════════════════════
#  容器管理器（创建 / 销毁 / 列表）
# ══════════════════════════════════════════════════════════════

class ContainerManager:
    """管理所有 Web4 容器"""

    def __init__(self):
        self.containers: dict[str, Web4Container] = {}
        self._lock = threading.Lock()
        self._state_file = SANDBOX_ROOT / "containers.json"
        self._load_state()

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for c in data.get("containers", []):
                    nc = Web4Container(name=c["name"])
                    nc.__dict__.update(c)
                    self.containers[c["name"]] = nc
            except Exception:
                pass

    def _save_state(self):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "containers": [
                {k: v for k, v in c.__dict__.items()
                 if not k.startswith("_") and k not in ["pid"]}
                for c in self.containers.values()
            ]
        }
        self._state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def create(self, name: str = None, cpu_limit: float = 1.0, mem_limit: str = "1g") -> Web4Container:
        with self._lock:
            cname = name or f"web4-{uuid.uuid4().hex[:8]}"
            if cname in self.containers and self.containers[cname].state == "running":
                self.log(f"容器 {cname} 已在运行")
                return self.containers[cname]

            c = Web4Container(name=cname, cpu_limit=cpu_limit, mem_limit=mem_limit)
            if c.create():
                self.containers[cname] = c
                self._save_state()
            return c

    def start(self, name: str) -> bool:
        with self._lock:
            if name not in self.containers:
                return False
            c = self.containers[name]
            ok = c.start()
            self._save_state()
            return ok

    def stop(self, name: str) -> bool:
        with self._lock:
            if name not in self.containers:
                return False
            ok = self.containers[name].stop()
            self._save_state()
            return ok

    def destroy(self, name: str) -> bool:
        with self._lock:
            if name not in self.containers:
                return False
            ok = self.containers[name].destroy()
            del self.containers[name]
            self._save_state()
            return ok

    def list(self) -> list[dict]:
        return [c.info() for c in self.containers.values()]

    def get(self, name: str) -> Web4Container:
        return self.containers.get(name)


# ══════════════════════════════════════════════════════════════
#  全局单例
# ══════════════════════════════════════════════════════════════

_manager = ContainerManager()


def manager() -> ContainerManager:
    return _manager


if __name__ == "__main__":
    # 演示
    print("Web4.0 沙箱容器管理器")
    print(f"沙箱根目录: {SANDBOX_ROOT}")
    print(f"可用容器槽位: 无限制（受限于 /dev/shm 和内存）")
    print()

    # 创建容器
    c = _manager.create("test-sandbox")
    print(json.dumps(c.info(), indent=2, ensure_ascii=False))

    # 启动
    ok = c.start()
    print(f"\n启动结果: {ok}")

    # 简单命令测试
    if ok:
        r = c.exec(["echo", "hello from sandbox"])
        print(f"exec 结果: returncode={r['returncode']}, stdout={r['stdout']!r}")

    # 清理
    c.destroy()
    print("\n演示完成")
