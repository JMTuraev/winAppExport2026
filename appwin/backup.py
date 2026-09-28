"""Backup to the always-connected external disk (config.json: "backup_dir", e.g. "E:\\\\EksportMonitor_zaxira").
Copies export.db with the SQLite backup API (safe while the server runs) + the data sub-folders that hold user files.
Keeps the last 30 daily snapshots and the first snapshot of each month for a year."""
from __future__ import annotations
import json, os, shutil, sqlite3, threading, datetime as dt, hashlib
from pathlib import Path
from app import db

_LOCK = threading.Lock()

KEEP_DAILY = 30
KEEP_MONTHLY = 12
SKIP_DIRS = {"backups", "incoming", "exports", "tmp", "gtd_archive"}     # regenerable / already versioned elsewhere

def backup_root(cfg: dict) -> Path | None:
    d = cfg.get("backup_dir")
    return Path(d) if d else None

def disk_status(cfg: dict) -> dict:
    root = backup_root(cfg)
    if not root: return {"configured": False, "connected": False, "path": None}
    drive = Path(root.anchor) if root.anchor else root
    connected = drive.exists()
    st = {"configured": True, "connected": connected, "path": str(root), "free_gb": None, "last": None, "count": 0}
    if connected:
        try:
            u = shutil.disk_usage(str(drive)); st["free_gb"] = round(u.free / 1024 ** 3, 1)
        except Exception: pass
        snaps = list_snapshots(root)
        st["count"] = len(snaps)
        if snaps: st["last"] = snaps[-1]
    return st

def list_snapshots(root: Path) -> list[dict]:
    out = []
    if not root.exists(): return out
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / "export.db").exists() and (p / "zaxira.json").exists():     # finished snapshots only
            meta = {}
            try: meta = json.loads((p / "zaxira.json").read_text(encoding="utf-8"))
            except Exception: pass
            out.append({"name": p.name, "path": str(p), "mb": meta.get("mb"), "ok": meta.get("ok"), "at": meta.get("at"), "by": meta.get("by")})
    return out

def run(cfg: dict, by: str = "", reason: str = "exit") -> dict:
    with _LOCK: return _run(cfg, by, reason)

def _sqlite_copy(src_path: Path, dst_path: Path) -> None:
    src = sqlite3.connect(str(src_path), timeout=60)
    try:
        dst = sqlite3.connect(str(dst_path))
        try: src.backup(dst)
        finally: dst.close()
    finally: src.close()

def _run(cfg: dict, by: str = "", reason: str = "exit") -> dict:
    root = backup_root(cfg)
    if not root: raise ValueError("Zaxira diski sozlanmagan (config.json → backup_dir)")
    drive = Path(root.anchor) if root.anchor else root
    if not drive.exists(): raise ValueError(f"Zaxira diski ulanmagan: {drive}")
    root.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M")
    final = root / stamp
    if final.exists(): final = root / (stamp + "-" + dt.datetime.now().strftime("%S"))
    dest = root / (".tmp-" + final.name)                       # written under a temp name, renamed when complete
    if dest.exists(): shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    # 1) databases — SQLite online backup (consistent even while others write); accounts/audit live in appwin.db
    _sqlite_copy(db.DB_PATH, dest / "export.db")
    adb = db.BASE / "appwin.db"
    if adb.exists(): _sqlite_copy(adb, dest / "appwin.db")
    # 2) integrity check of the copy
    chk = sqlite3.connect(str(dest / "export.db"))
    try: ok = chk.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally: chk.close()
    # 3) user files next to the database
    files = 0; total = (dest / "export.db").stat().st_size
    for sub in sorted(db.BASE.iterdir()):
        if sub.name in SKIP_DIRS or sub.name.startswith("."): continue
        if sub.is_dir():
            shutil.copytree(sub, dest / sub.name, dirs_exist_ok=True)
            for f in (dest / sub.name).rglob("*"):
                if f.is_file(): files += 1; total += f.stat().st_size
        elif sub.is_file() and sub.suffix.lower() in (".json", ".xlsx", ".xls"):
            shutil.copy2(sub, dest / sub.name); files += 1; total += sub.stat().st_size
    meta = {"at": dt.datetime.now().isoformat(timespec="seconds"), "by": by, "reason": reason, "ok": ok, "files": files,
            "mb": round(total / 1048576, 1), "source": str(db.DB_PATH), "sha256": _sha(dest / "export.db")}
    (dest / "zaxira.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(dest, final); dest = final
    for old in root.glob(".tmp-*"):                            # leftovers of interrupted runs
        shutil.rmtree(old, ignore_errors=True)
    removed = prune(root)
    try:
        con = db.connect(); db.log(con, "external_backup", dest=str(dest), **meta); con.commit(); con.close()
    except Exception: pass
    return {"name": dest.name, "path": str(dest), **meta, "removed": removed}

def prune(root: Path) -> list[str]:
    snaps = list_snapshots(root)
    if len(snaps) <= KEEP_DAILY: return []
    keep = {s["name"] for s in snaps[-KEEP_DAILY:]}
    firsts = {}
    for s in snaps:
        m = s["name"][:7]
        firsts.setdefault(m, s["name"])
    months = sorted(firsts)[-KEEP_MONTHLY:]
    keep |= {firsts[m] for m in months}
    removed = []
    for s in snaps:
        if s["name"] not in keep:
            try: shutil.rmtree(s["path"]); removed.append(s["name"])
            except Exception: pass
    return removed

def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def verify(cfg: dict, name: str | None = None) -> dict:
    """Open a snapshot read-only and compare a few totals with the live database."""
    root = backup_root(cfg)
    snaps = list_snapshots(root) if root else []
    if not snaps: raise ValueError("Zaxira topilmadi")
    snap = next((s for s in snaps if s["name"] == name), snaps[-1])
    q = "SELECT (SELECT count(*) FROM companies), (SELECT count(*) FROM gtd_rows), (SELECT count(*) FROM items), (SELECT count(*) FROM issues)"
    live = sqlite3.connect(str(db.DB_PATH)); bk = sqlite3.connect(f"file:{Path(snap['path']) / 'export.db'}?mode=ro", uri=True)
    try:
        a = live.execute(q).fetchone(); b = bk.execute(q).fetchone(); integ = bk.execute("PRAGMA integrity_check").fetchone()[0]
    finally: live.close(); bk.close()
    return {"name": snap["name"], "integrity": integ, "live": {"companies": a[0], "gtd_rows": a[1], "items": a[2], "issues": a[3]},
            "backup": {"companies": b[0], "gtd_rows": b[1], "items": b[2], "issues": b[3]}}
