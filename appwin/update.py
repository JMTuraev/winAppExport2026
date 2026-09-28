"""Updates without reinstalling.
  * Server PC:  Superadmin → «Yangilanish» — `git pull` in AppWin + restart.
  * Staff PCs (client mode): on every start the app compares its AppWin files with the server's manifest and
    downloads the changed ones over the LAN — before any library is loaded, so files are free to replace."""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, urllib.request, urllib.parse, datetime as dt
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {"webview-data", "build", "__pycache__", ".git", "_update", "python", "data"}   # python never changes; data is not code
EXCLUDE_FILES = {"config.json", "appwin.log", "EksportMonitor.exe", "EksportMonitor2.exe"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".tmp"}

# ------------------------------------------------------------ manifest (served by the server)
def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def manifest(app_dir: Path = APP_DIR) -> dict:
    files = {}
    for root, dirs, names in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for n in names:
            p = Path(root) / n
            if n in EXCLUDE_FILES or p.suffix.lower() in EXCLUDE_SUFFIX: continue
            rel = p.relative_to(app_dir).as_posix()
            files[rel] = {"sha": _sha(p), "size": p.stat().st_size}
    from . import __version__
    stamp = hashlib.sha256("".join(f"{k}:{v['sha']}" for k, v in sorted(files.items())).encode()).hexdigest()[:12]
    return {"version": __version__, "stamp": stamp, "files": files, "count": len(files)}

def safe_rel(rel: str, app_dir: Path = APP_DIR) -> Path | None:
    rel = rel.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/") or not rel: return None
    p = (app_dir / rel).resolve()
    if app_dir.resolve() not in p.parents: return None
    if p.name in EXCLUDE_FILES or any(part in EXCLUDE_DIRS for part in p.relative_to(app_dir.resolve()).parts[:-1]): return None
    return p

# ------------------------------------------------------------ client side: pull changed files from the server
def client_update(server_url: str, app_dir: Path = APP_DIR, log=print, timeout: float = 4.0) -> dict:
    base = server_url.rstrip("/")
    try:
        with urllib.request.urlopen(base + "/appwin-update/manifest", timeout=timeout) as r: remote = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"manifest: {e}", "changed": 0}
    local = manifest(app_dir)["files"]
    todo = [rel for rel, meta in remote["files"].items() if local.get(rel, {}).get("sha") != meta["sha"]]
    if not todo: return {"ok": True, "changed": 0, "stamp": remote.get("stamp")}
    done, failed = [], []
    for rel in todo:
        dest = safe_rel(rel, app_dir)
        if dest is None: continue
        try:
            with urllib.request.urlopen(base + "/appwin-update/file?p=" + urllib.parse.quote(rel), timeout=30) as r: data = r.read()
            if hashlib.sha256(data).hexdigest() != remote["files"][rel]["sha"]: raise ValueError("sha mos emas")
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp"); tmp.write_bytes(data); os.replace(tmp, dest); done.append(rel)
        except Exception as e:
            failed.append(f"{rel}: {e}"); log("yangilash xato:", rel, e)
    log(f"serverdan yangilandi: {len(done)} fayl" + (f", xato {len(failed)}" if failed else ""))
    return {"ok": not failed, "changed": len(done), "failed": failed, "stamp": remote.get("stamp"), "files": done}

# ------------------------------------------------------------ server side: git
def _git(dir_: Path, *args, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=str(dir_), capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git topilmadi (Git for Windows o'rnatilmagan)"
    except subprocess.TimeoutExpired:
        return 124, "git javob bermadi (internet?)"

def repo_status(dir_: Path, fetch: bool = True) -> dict:
    st = {"dir": str(dir_), "name": dir_.name, "git": (dir_ / ".git").exists()}
    if not st["git"]: return st
    if fetch:
        code, out = _git(dir_, "fetch", "--quiet"); st["fetch_ok"] = code == 0
        if code != 0: st["error"] = out
    code, br = _git(dir_, "rev-parse", "--abbrev-ref", "HEAD"); st["branch"] = br if code == 0 else "?"
    code, log = _git(dir_, "log", "-1", "--format=%h · %ad · %s", "--date=format:%d.%m.%Y %H:%M"); st["head"] = log if code == 0 else ""
    code, n = _git(dir_, "rev-list", "--count", "HEAD..@{u}"); st["behind"] = int(n) if code == 0 and n.isdigit() else None
    code, n = _git(dir_, "rev-list", "--count", "@{u}..HEAD"); st["ahead"] = int(n) if code == 0 and n.isdigit() else None
    code, dirty = _git(dir_, "status", "--porcelain"); st["dirty"] = bool(dirty.strip()) if code == 0 else None
    if st.get("behind"):
        code, inc = _git(dir_, "log", "--format=%h %s", "HEAD..@{u}"); st["incoming"] = inc.splitlines()[:15] if code == 0 else []
    return st

def repo_pull(dir_: Path) -> dict:
    if not (dir_ / ".git").exists(): return {"ok": False, "error": "git repo emas"}
    code, out = _git(dir_, "pull", "--ff-only")
    return {"ok": code == 0, "out": out}

def restart_self(app_dir: Path = APP_DIR, log=print) -> None:
    """Start a fresh copy (exe if present, else the .bat) and let the caller exit; the new copy takes the port over."""
    exe = next((app_dir / n for n in ("EksportMonitor.exe", "EksportMonitor2.exe") if (app_dir / n).exists()), None)
    try:
        if exe and sys.executable.lower().endswith("pythonw.exe"):
            subprocess.Popen([str(exe)], cwd=str(app_dir), close_fds=True)
        else:
            bat = app_dir / "Ishga_tushirish.bat"
            subprocess.Popen(["cmd", "/c", "start", "", str(bat)], cwd=str(app_dir), close_fds=True)
        log("qayta ishga tushirilmoqda")
    except Exception as e:
        log("restart xato:", e)
