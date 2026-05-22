from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


VERSION = "v4.9-exe-launcher"
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "5173"))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        native_path = windows_module_path()
        if native_path and native_path.exists():
            return native_path.resolve().parent
        exe_path = Path(sys.executable)
        repaired = repair_mojibake_path(str(exe_path))
        if repaired and repaired.exists() and (repaired.parent / "app").exists():
            return repaired.resolve().parent
        try:
            resolved = exe_path.resolve()
        except OSError:
            resolved = exe_path
        if resolved.exists():
            return resolved.parent
        return resolved.parent
    return Path(__file__).resolve().parents[1]


def repair_mojibake_path(path_text: str) -> Path | None:
    try:
        repaired = path_text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return None
    if repaired == path_text:
        return None
    return Path(repaired)


def windows_module_path() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, len(buffer))
        if length:
            return Path(buffer.value)
    except Exception:
        return None
    return None


def write_status(message: str) -> None:
    print(message, flush=True)


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


def url_ready(url: str, allow_client_error: bool = False, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if allow_client_error:
                return 200 <= response.status < 500
            return 200 <= response.status < 300
    except Exception:
        return False


def wait_url(url: str, name: str, allow_client_error: bool = False, seconds: int = 35) -> bool:
    for _ in range(seconds):
        if url_ready(url, allow_client_error=allow_client_error):
            return True
        time.sleep(1)
    write_status(f"[错误] {name} 超时：{url}")
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


def start_process(
    command: list[str],
    cwd: Path,
    runtime_dir: Path,
    log_name: str,
    env: dict[str, str],
) -> subprocess.Popen:
    out_file = open(runtime_dir / f"{log_name}.out.log", "a", encoding="utf-8", errors="ignore")
    err_file = open(runtime_dir / f"{log_name}.err.log", "a", encoding="utf-8", errors="ignore")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=out_file,
        stderr=err_file,
        creationflags=creationflags,
    )


def main() -> int:
    root = app_root()
    app_dir = root / "app"
    backend_dir = app_dir / "backend"
    frontend_dist = app_dir / "frontend_dist"
    python_exe = backend_dir / ".venv" / "Scripts" / "python.exe"

    print("========================================")
    print(f"工程进度管理系统 {VERSION} EXE 启动器")
    print(f"Backend URL {BACKEND_URL}")
    print(f"Frontend URL {FRONTEND_URL}")
    print("========================================")

    if not app_dir.exists():
        write_status("[错误] 未找到 app 目录，请确认整个交付文件夹完整。")
        return 1
    if not (backend_dir / "app" / "main.py").exists():
        write_status("[错误] 未找到 app\\backend\\app\\main.py。")
        return 1
    if not frontend_dist.joinpath("index.html").exists():
        write_status("[错误] 未找到 app\\frontend_dist\\index.html。")
        return 1
    if not python_exe.exists():
        write_status("[错误] 未找到内置 Python 运行环境：app\\backend\\.venv\\Scripts\\python.exe。")
        return 1

    runtime_dir, _ = ensure_dirs(app_dir)
    env = os.environ.copy()
    env.update(
        {
            "APP_RUN_MODE": "exe-launcher",
            "APP_RUNTIME_MODE": "exe-launcher",
            "BACKEND_PORT": str(BACKEND_PORT),
            "FRONTEND_PORT": str(FRONTEND_PORT),
        }
    )

    backend_status, backend_pid = port_owner(BACKEND_PORT, app_dir)
    if url_ready(f"{BACKEND_URL}/api/health"):
        if backend_status == "project":
            write_status("后端已运行，直接复用。")
            write_pid(runtime_dir, "backend", backend_pid)
        else:
            write_status(f"[错误] 端口 {BACKEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            return 1
    else:
        if backend_status == "other":
            write_status(f"[错误] 端口 {BACKEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            return 1
        if backend_status == "project":
            write_status("[错误] 本项目后端占用端口但健康检查未通过，请运行 停止系统.bat 后重试。")
            return 1
        write_status("正在启动后端...")
        backend = start_process(
            [str(python_exe), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            backend_dir,
            runtime_dir,
            "backend",
            env,
        )
        write_pid(runtime_dir, "backend", backend.pid)
        if not wait_url(f"{BACKEND_URL}/api/health", "后端健康检查"):
            write_status("[错误] 后端健康检查未通过，请查看 app\\.runtime\\backend.err.log。")
            return 1
        write_pid(runtime_dir, "backend", listening_pid(BACKEND_PORT) or backend.pid)
        write_status("后端健康检查通过。")

    frontend_status, frontend_pid = port_owner(FRONTEND_PORT, app_dir)
    if url_ready(f"{FRONTEND_URL}/", allow_client_error=True):
        if frontend_status == "project":
            write_status("前端已运行，直接复用。")
            write_pid(runtime_dir, "frontend", frontend_pid)
        else:
            write_status(f"[错误] 端口 {FRONTEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            return 1
    else:
        if frontend_status == "other":
            write_status(f"[错误] 端口 {FRONTEND_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            return 1
        if frontend_status == "project":
            write_status("[错误] 本项目前端占用端口但页面未就绪，请运行 停止系统.bat 后重试。")
            return 1
        write_status("正在启动前端...")
        frontend = start_process(
            [str(python_exe), "-m", "http.server", str(FRONTEND_PORT), "--bind", "127.0.0.1", "--directory", str(frontend_dist)],
            app_dir,
            runtime_dir,
            "frontend",
            env,
        )
        write_pid(runtime_dir, "frontend", frontend.pid)
        if not wait_url(f"{FRONTEND_URL}/", "前端端口检查", allow_client_error=True):
            write_status("[错误] 前端端口未就绪，请查看 app\\.runtime\\frontend.err.log。")
            return 1
        write_pid(runtime_dir, "frontend", listening_pid(FRONTEND_PORT) or frontend.pid)

    write_status("系统已启动，正在打开浏览器。")
    webbrowser.open(FRONTEND_URL)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"[错误] 网络检查失败：{exc}", flush=True)
        raise SystemExit(1)
    except Exception as exc:
        print(f"[错误] 启动器异常：{exc}", flush=True)
        raise SystemExit(1)
