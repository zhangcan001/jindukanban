from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


VERSION = "v5.0-desktop-shell"
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
WINDOW_TITLE = "工程进度管理系统"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        native_path = windows_module_path()
        if native_path and native_path.exists():
            return native_path.resolve().parent
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def windows_module_path() -> Path | None:
    if os.name != "nt":
        return None
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
        if length:
            return Path(buffer.value)
    except Exception:
        return None
    return None


def message_box(message: str, title: str = WINDOW_TITLE, flags: int = 0x40) -> int:
    if os.name == "nt":
        return int(ctypes.windll.user32.MessageBoxW(None, message, title, flags))
    print(f"{title}: {message}", flush=True)
    return 1


def ensure_dirs(app_dir: Path) -> tuple[Path, Path]:
    runtime_dir = app_dir / ".runtime"
    log_dir = app_dir / "logs"
    for path in (
        runtime_dir,
        log_dir,
        app_dir / "data",
        app_dir / "uploads",
        app_dir / "exports",
        app_dir / "backups",
    ):
        path.mkdir(parents=True, exist_ok=True)
    return runtime_dir, log_dir


def write_log(log_file: Path, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8", errors="ignore") as file:
        file.write(f"[{timestamp}] {message}\n")


def url_ready(url: str, allow_client_error: bool = False, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if allow_client_error:
                return 200 <= response.status < 500
            return 200 <= response.status < 300
    except Exception:
        return False


def wait_url(url: str, seconds: int, log_file: Path, name: str, allow_client_error: bool = False) -> bool:
    for _ in range(seconds):
        if url_ready(url, allow_client_error=allow_client_error):
            write_log(log_file, f"{name} ready: {url}")
            return True
        time.sleep(1)
    write_log(log_file, f"{name} timeout: {url}")
    return False


def listening_pid(port: int) -> str | None:
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="ignore",
            check=False,
        )
    except OSError:
        return None
    needle = f":{port}"
    for line in result.stdout.splitlines():
        if needle in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts:
                return parts[-1]
    return None


def process_command_line(pid: str) -> str:
    powershell = (
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId="
        + pid
        + "\" -ErrorAction SilentlyContinue; if($p){$p.CommandLine}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", powershell],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        return result.stdout.strip()
    except OSError:
        return ""


def port_owner(port: int, app_dir: Path) -> tuple[str, str | None]:
    pid = listening_pid(port)
    if not pid:
        return "free", None
    command = process_command_line(pid).lower()
    normalized_app = str(app_dir).lower()
    if normalized_app in command:
        return "project", pid
    return "other", pid


def write_pid(runtime_dir: Path, name: str, pid: str | int | None) -> None:
    if pid:
        (runtime_dir / f"{name}.pid").write_text(str(pid), encoding="ascii")


def start_backend(python_exe: Path, backend_dir: Path, runtime_dir: Path, log_file: Path, env: dict[str, str]) -> subprocess.Popen:
    out_file = open(runtime_dir / "backend.out.log", "a", encoding="utf-8", errors="ignore")
    err_file = open(runtime_dir / "backend.err.log", "a", encoding="utf-8", errors="ignore")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    command = [
        str(python_exe),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(BACKEND_PORT),
    ]
    write_log(log_file, "starting backend: " + " ".join(command))
    return subprocess.Popen(
        command,
        cwd=str(backend_dir),
        env=env,
        stdout=out_file,
        stderr=err_file,
        creationflags=creationflags,
    )


def stop_project_backend(app_dir: Path, runtime_dir: Path, log_file: Path) -> None:
    candidates: list[str] = []
    pid_file = runtime_dir / "backend.pid"
    if pid_file.exists():
        candidates.append(pid_file.read_text(encoding="ascii", errors="ignore").strip())
    listening = listening_pid(BACKEND_PORT)
    if listening:
        candidates.append(listening)

    normalized_app = str(app_dir).lower()
    stopped: set[str] = set()
    for pid in candidates:
        if not pid or pid in stopped:
            continue
        command = process_command_line(pid).lower()
        if normalized_app not in command:
            write_log(log_file, f"skip non-project backend pid={pid}")
            continue
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {int(pid)} -Force"],
                capture_output=True,
                text=True,
                check=False,
            )
            stopped.add(pid)
            write_log(log_file, f"stopped backend pid={pid}")
        except Exception as exc:
            write_log(log_file, f"failed to stop backend pid={pid}: {exc}")
    if pid_file.exists():
        pid_file.unlink(missing_ok=True)


def validate_package(root: Path, app_dir: Path, log_file: Path) -> tuple[Path, Path]:
    backend_dir = app_dir / "backend"
    frontend_dist = app_dir / "frontend_dist"
    python_exe = backend_dir / ".venv" / "Scripts" / "python.exe"
    checks = [
        (app_dir.exists(), "未找到 app 目录，请确认整个交付文件夹完整。"),
        ((backend_dir / "app" / "main.py").exists(), "未找到 app\\backend\\app\\main.py。"),
        ((frontend_dist / "index.html").exists(), "未找到 app\\frontend_dist\\index.html。"),
        (python_exe.exists(), "未找到内置 Python 运行环境：app\\backend\\.venv\\Scripts\\python.exe。"),
    ]
    for ok, message in checks:
        if not ok:
            write_log(log_file, message)
            raise RuntimeError(message)
    write_log(log_file, f"root={root}")
    write_log(log_file, f"app_dir={app_dir}")
    return backend_dir, python_exe


def launch_window(app_dir: Path, runtime_dir: Path, log_file: Path) -> None:
    try:
        import webview
    except Exception as exc:
        raise RuntimeError("未找到桌面窗口运行组件 pywebview，请重新构建安装包。") from exc

    window = webview.create_window(
        WINDOW_TITLE,
        f"{BACKEND_URL}/",
        width=1280,
        height=820,
        min_size=(1100, 700),
    )

    def on_closing() -> bool:
        answer = message_box("是否退出工程进度管理系统？", WINDOW_TITLE, 0x24)
        if answer != 6:
            return False
        stop_project_backend(app_dir, runtime_dir, log_file)
        return True

    window.events.closing += on_closing
    write_log(log_file, "opening desktop window")
    webview.start(debug=False)


def main() -> int:
    root = app_root()
    app_dir = root / "app"
    runtime_dir, log_dir = ensure_dirs(app_dir)
    log_file = log_dir / "desktop_launcher.log"
    write_log(log_file, f"{VERSION} launcher start")

    try:
        backend_dir, python_exe = validate_package(root, app_dir, log_file)
        env = os.environ.copy()
        env.update(
            {
                "APP_RUN_MODE": "desktop-shell",
                "APP_RUNTIME_MODE": "desktop-shell",
                "BACKEND_PORT": str(BACKEND_PORT),
            }
        )

        status, pid = port_owner(BACKEND_PORT, app_dir)
        if url_ready(f"{BACKEND_URL}/api/health"):
            if status != "project":
                raise RuntimeError(f"端口 {BACKEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            write_log(log_file, f"reuse backend pid={pid}")
            write_pid(runtime_dir, "backend", pid)
        else:
            if status == "other":
                raise RuntimeError(f"端口 {BACKEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            if status == "project":
                raise RuntimeError("本项目后端占用端口但健康检查未通过，请运行 停止系统.bat 后重试。")
            backend = start_backend(python_exe, backend_dir, runtime_dir, log_file, env)
            write_pid(runtime_dir, "backend", backend.pid)
            if not wait_url(f"{BACKEND_URL}/api/health", 60, log_file, "backend health"):
                raise RuntimeError("系统启动失败，请运行 诊断系统.bat 查看日志。")
            write_pid(runtime_dir, "backend", listening_pid(BACKEND_PORT) or backend.pid)

        if not wait_url(f"{BACKEND_URL}/", 30, log_file, "frontend index", allow_client_error=True):
            raise RuntimeError("系统首页加载失败，请运行 诊断系统.bat 查看日志。")

        launch_window(app_dir, runtime_dir, log_file)
        return 0
    except Exception as exc:
        write_log(log_file, f"ERROR: {exc}")
        message_box(f"{exc}\n\n请运行 诊断系统.bat 查看日志。", "系统启动失败", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
