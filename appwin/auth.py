"""Users, roles, sessions and audit for the office LAN app.
They live in their OWN file, data\\appwin.db — so a restore / reset / re-init of export.db never touches accounts or the audit trail."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, threading, datetime as dt
from pathlib import Path

DB_NAME = "appwin.db"
_LOCK = threading.Lock()

def db_path() -> Path:
    from app import db
    return db.BASE / DB_NAME

def connect() -> sqlite3.Connection:
    p = db_path(); p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA synchronous=NORMAL")
    return con

def migrate_from_export(con: sqlite3.Connection) -> None:
    """One-time: earlier AppWin builds kept the tables inside export.db — carry them over, then drop them there."""
    from app import db
    try:
        src = sqlite3.connect(str(db.DB_PATH)); src.row_factory = sqlite3.Row
        have = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users','user_sessions','user_audit')")}
        if "users" in have and con.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
            for t in ("users", "user_audit"):
                if t in have:
                    rows = src.execute(f"SELECT * FROM {t}").fetchall()
                    if rows:
                        cols = rows[0].keys()
                        con.executemany(f"INSERT OR IGNORE INTO {t}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [tuple(r) for r in rows])
            con.commit()
        src.close()
        w = sqlite3.connect(str(db.DB_PATH))
        for t in have: w.execute(f"DROP TABLE IF EXISTS {t}")
        w.commit(); w.close()
    except Exception:
        pass

ROLES = {
    "superadmin": "Superadmin",
    "operator":   "Operator",          # uploads, edits, Excel
    "viewer":     "Ko'ruvchi",         # read-only + Excel
    "district":   "Tuman xodimi",      # read-only, own districts (filtering comes in phase 2)
}
WRITE_ROLES = {"superadmin", "operator"}
SESSION_HOURS = 12
SESSION_HOURS_REMEMBER = 24 * 30
ONLINE_MINUTES = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  login TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  districts TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1,
  must_change INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  last_login TEXT
);
CREATE TABLE IF NOT EXISTS user_sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  ip TEXT, host TEXT, agent TEXT,
  created_at TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  page TEXT,
  closed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user ON user_sessions(user_id, closed);
CREATE TABLE IF NOT EXISTS user_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user_id INTEGER, login TEXT, ip TEXT,
  action TEXT NOT NULL,
  path TEXT,
  detail TEXT,
  ok INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_user_audit_ts ON user_audit(ts);
"""

def now() -> str: return dt.datetime.now().isoformat(timespec="seconds")

def init(con: sqlite3.Connection) -> dict | None:
    """Create tables; if there is no user at all, create the first superadmin. Returns its credentials once."""
    con.executescript(SCHEMA)
    migrate_from_export(con)
    if con.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
        pwd = secrets.token_urlsafe(6)
        con.execute("INSERT INTO users(login, name, pass_hash, role, active, must_change, created_at) VALUES (?,?,?,?,1,1,?)",
                    ("admin", "Superadmin", hash_password(pwd), "superadmin", now()))
        con.commit()
        return {"login": "admin", "password": pwd}
    cleanup_sessions(con)
    con.commit()
    return None

# ------------------------------------------------------------ passwords
def hash_password(pwd: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 120_000)
    return "pbkdf2$120000$" + salt.hex() + "$" + h.hex()

def check_password(pwd: str, stored: str) -> bool:
    try:
        _, iters, salt, h = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False

def validate_password(pwd: str) -> str | None:
    if len(pwd or "") < 6: return "Parol kamida 6 belgi bo'lsin"
    return None

# ------------------------------------------------------------ users
def user_row(r) -> dict:
    return {"id": r["id"], "login": r["login"], "name": r["name"], "role": r["role"], "role_name": ROLES.get(r["role"], r["role"]),
            "districts": json.loads(r["districts"] or "[]"), "active": bool(r["active"]), "must_change": bool(r["must_change"]),
            "created_at": r["created_at"], "last_login": r["last_login"]}

def list_users(con) -> list[dict]:
    rows = con.execute("SELECT * FROM users ORDER BY CASE role WHEN 'superadmin' THEN 0 ELSE 1 END, name").fetchall()
    online = {r["user_id"] for r in con.execute("SELECT DISTINCT user_id FROM user_sessions WHERE closed=0 AND last_seen>=?", (_ago(ONLINE_MINUTES),))}
    out = []
    for r in rows:
        u = user_row(r); u["online"] = r["id"] in online; out.append(u)
    return out

def save_user(con, body: dict, actor: dict) -> dict:
    with _LOCK: return _save_user(con, body, actor)

def _save_user(con, body: dict, actor: dict) -> dict:
    uid = body.get("id")
    login = (body.get("login") or "").strip().lower()
    name = (body.get("name") or "").strip()
    role = body.get("role") or "viewer"
    districts = body.get("districts") or []
    if role not in ROLES: raise ValueError("Rol noto'g'ri")
    if not name: raise ValueError("Ism kiritilmadi")
    if not uid:
        if not login or not login.replace(".", "").replace("_", "").isalnum(): raise ValueError("Login: faqat harf, raqam, nuqta")
        pwd = body.get("password") or ""
        err = validate_password(pwd)
        if err: raise ValueError(err)
        if con.execute("SELECT 1 FROM users WHERE login=?", (login,)).fetchone(): raise ValueError("Bunday login bor")
        cur = con.execute("INSERT INTO users(login, name, pass_hash, role, districts, active, must_change, created_at) VALUES (?,?,?,?,?,1,1,?)",
                          (login, name, hash_password(pwd), role, json.dumps(districts, ensure_ascii=False), now()))
        uid = cur.lastrowid
    else:
        cur_u = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not cur_u: raise ValueError("Foydalanuvchi topilmadi")
        if cur_u["role"] == "superadmin" and role != "superadmin" and _superadmins(con) <= 1:
            raise ValueError("Oxirgi superadmin rolini o'zgartirib bo'lmaydi")
        con.execute("UPDATE users SET name=?, role=?, districts=? WHERE id=?", (name, role, json.dumps(districts, ensure_ascii=False), uid))
        if body.get("password"):
            err = validate_password(body["password"])
            if err: raise ValueError(err)
            con.execute("UPDATE users SET pass_hash=?, must_change=1 WHERE id=?", (hash_password(body["password"]), uid))
            con.execute("UPDATE user_sessions SET closed=1 WHERE user_id=? AND closed=0", (uid,))
    con.commit()
    return user_row(con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

def set_active(con, uid: int, active: bool, actor: dict) -> dict:
    with _LOCK: return _set_active(con, uid, active, actor)

def _set_active(con, uid: int, active: bool, actor: dict) -> dict:
    u = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not u: raise ValueError("Foydalanuvchi topilmadi")
    if uid == actor["id"]: raise ValueError("O'zingizni bloklab bo'lmaydi")
    if u["role"] == "superadmin" and not active and _superadmins(con) <= 1: raise ValueError("Oxirgi superadminni bloklab bo'lmaydi")
    con.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, uid))
    if not active: con.execute("UPDATE user_sessions SET closed=1 WHERE user_id=?", (uid,))
    con.commit()
    return user_row(con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

def change_password(con, user: dict, old: str, new: str) -> None:
    r = con.execute("SELECT pass_hash, must_change FROM users WHERE id=?", (user["id"],)).fetchone()
    if not r["must_change"] and not check_password(old or "", r["pass_hash"]): raise ValueError("Joriy parol noto'g'ri")
    err = validate_password(new)
    if err: raise ValueError(err)
    con.execute("UPDATE users SET pass_hash=?, must_change=0 WHERE id=?", (hash_password(new), user["id"]))
    if user.get("token"): con.execute("UPDATE user_sessions SET closed=1 WHERE user_id=? AND token<>?", (user["id"], _tok(user["token"])))
    con.commit()
    if user.get("login") == "admin":
        try: (db_path().parent / "ADMIN_PAROL.txt").unlink(missing_ok=True)
        except Exception: pass

def _superadmins(con) -> int:
    return con.execute("SELECT count(*) FROM users WHERE role='superadmin' AND active=1").fetchone()[0]

# ------------------------------------------------------------ sessions
def _ago(minutes: int) -> str: return (dt.datetime.now() - dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")

# brute-force guard: after 5 failures for a login (or from an IP) within 10 minutes, wait 30 s between attempts
_FAILS: dict[str, list[float]] = {}
FAIL_LIMIT, FAIL_WINDOW, FAIL_WAIT = 5, 600, 30

def _throttled(key: str) -> int:
    import time
    now_t = time.time(); arr = [t for t in _FAILS.get(key, []) if now_t - t < FAIL_WINDOW]; _FAILS[key] = arr
    if len(arr) >= FAIL_LIMIT and now_t - arr[-1] < FAIL_WAIT: return int(FAIL_WAIT - (now_t - arr[-1])) + 1
    return 0

def _fail(key: str):
    import time
    _FAILS.setdefault(key, []).append(time.time())

def _tok(token: str) -> str: return hashlib.sha256(token.encode("utf-8")).hexdigest()

def cleanup_sessions(con) -> None:
    con.execute("DELETE FROM user_sessions WHERE closed=1 OR expires_at<?", (_ago(60 * 24 * 30),))
    con.commit()

_DUMMY_HASH = None

def login(con, login_: str, pwd: str, ip: str, host: str, agent: str, remember: bool) -> tuple[dict, str, int]:
    global _DUMMY_HASH
    login_ = (login_ or "").strip().lower()[:64]
    key_l = "l:" + login_; key_ip = "ip:" + (ip or "")
    with _LOCK:                                   # check + count atomically: parallel guesses can't slip past the limit
        wait = max(_throttled(key_l), _throttled(key_ip))
        if wait:
            audit(con, None, login_, ip, "kirish xato", "/api/auth/login", f"juda ko'p urinish — {wait} s kutish", ok=False); con.commit()
            raise PermissionError(f"Juda ko'p noto'g'ri urinish. {wait} soniyadan keyin qayta urining")
        _fail(key_l); _fail(key_ip)              # counted up front; removed again on success
        if len(_FAILS) > 5000: _FAILS.clear()
    u = con.execute("SELECT * FROM users WHERE login=?", (login_,)).fetchone()
    if _DUMMY_HASH is None: _DUMMY_HASH = hash_password("x")
    ok = check_password(pwd or "", u["pass_hash"] if u else _DUMMY_HASH) and u is not None   # same cost for unknown logins
    if not ok:
        audit(con, None, login_, ip, "kirish xato", "/api/auth/login", "parol noto'g'ri", ok=False); con.commit()
        raise PermissionError("Login yoki parol noto'g'ri")
    if not u["active"]:
        audit(con, u["id"], u["login"], ip, "kirish xato", "/api/auth/login", "bloklangan", ok=False)
        raise PermissionError("Bu foydalanuvchi bloklangan — superadminga murojaat qiling")
    hours = SESSION_HOURS_REMEMBER if remember else SESSION_HOURS
    token = secrets.token_urlsafe(32)
    exp = (dt.datetime.now() + dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    con.execute("INSERT INTO user_sessions(token, user_id, ip, host, agent, created_at, last_seen, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                (_tok(token), u["id"], ip, (host or "")[:80], (agent or "")[:200], now(), now(), exp))
    con.execute("UPDATE users SET last_login=? WHERE id=?", (now(), u["id"]))
    with _LOCK:
        _FAILS.pop(key_l, None)
        if _FAILS.get(key_ip): _FAILS[key_ip] = _FAILS[key_ip][:-1]
    user = user_row(u)
    audit(con, u["id"], u["login"], ip, "kirdi", "/api/auth/login", host or "")
    con.commit()
    return user, token, hours * 3600

def session_user(con, token: str | None, ip: str | None = None, page: str | None = None) -> dict | None:
    if not token: return None
    th = _tok(token)
    r = con.execute("SELECT s.token, s.expires_at, s.last_seen, u.* FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.closed=0", (th,)).fetchone()
    if not r or r["expires_at"] < now() or not r["active"]: return None
    # touch at most once a minute (keeps the DB quiet)
    if r["last_seen"] < _ago(1) or page:
        con.execute("UPDATE user_sessions SET last_seen=?, ip=coalesce(?, ip), page=coalesce(?, page) WHERE token=?", (now(), ip, page, th))
        con.commit()
    u = user_row(r); u["token"] = token
    return u

def logout(con, token: str, user: dict | None, ip: str) -> None:
    con.execute("UPDATE user_sessions SET closed=1 WHERE token=?", (_tok(token),))
    if user: audit(con, user["id"], user["login"], ip, "chiqdi", "/api/auth/logout", "")
    con.commit()

def online(con) -> list[dict]:
    rows = con.execute("""SELECT u.id, u.name, u.login, u.role, s.ip, s.host, s.page, s.last_seen, s.created_at
                          FROM user_sessions s JOIN users u ON u.id=s.user_id
                          WHERE s.closed=0 AND s.last_seen>=? ORDER BY s.last_seen DESC""", (_ago(ONLINE_MINUTES),)).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["id"] in seen: continue
        seen.add(r["id"])
        out.append({"id": r["id"], "name": r["name"], "login": r["login"], "role": r["role"], "role_name": ROLES.get(r["role"], r["role"]),
                    "ip": r["ip"], "host": r["host"], "page": r["page"], "last_seen": r["last_seen"], "since": r["created_at"]})
    return out

def close_user_sessions(con, uid: int) -> int:
    n = con.execute("UPDATE user_sessions SET closed=1 WHERE user_id=? AND closed=0", (uid,)).rowcount
    con.commit(); return n

MUST_CHANGE_OK = ("/api/auth/me", "/api/auth/password", "/api/auth/logout", "/api/auth/page", "/logout", "/login", "/appwin/", "/static/")

def must_change_blocked(user: dict | None, path: str) -> bool:
    return bool(user and user.get("must_change") and not any(path == p or path.startswith(p) for p in MUST_CHANGE_OK))

# ------------------------------------------------------------ audit
def audit(con, user_id, login_, ip, action: str, path: str = "", detail: str = "", ok: bool = True) -> None:
    con.execute("INSERT INTO user_audit(ts, user_id, login, ip, action, path, detail, ok) VALUES (?,?,?,?,?,?,?,?)",
                (now(), user_id, login_, ip, action, path, (detail or "")[:600], 1 if ok else 0))

def audit_list(con, q: dict) -> dict:
    where, args = [], []
    if q.get("user_id"): where.append("user_id=?"); args.append(int(q["user_id"]))
    if q.get("action"): where.append("action=?"); args.append(q["action"])
    if q.get("date_from"): where.append("ts>=?"); args.append(q["date_from"])
    if q.get("date_to"): where.append("ts<?"); args.append(q["date_to"] + "T99")
    if q.get("ok") in ("0", "1"): where.append("ok=?"); args.append(int(q["ok"]))
    if q.get("text"):
        where.append("(detail LIKE ? OR path LIKE ? OR login LIKE ?)"); t = f"%{q['text']}%"; args += [t, t, t]
    w = ("WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(q.get("limit") or 300), 2000))
    rows = con.execute(f"SELECT * FROM user_audit {w} ORDER BY id DESC LIMIT {limit}", args).fetchall()
    total = con.execute(f"SELECT count(*) FROM user_audit {w}", args).fetchone()[0]
    actions = [r[0] for r in con.execute("SELECT DISTINCT action FROM user_audit ORDER BY action")]
    return {"rows": [dict(r) for r in rows], "total": total, "actions": actions}

# ------------------------------------------------------------ what a POST means (human readable audit)
ACTION_NAMES = [
    ("/api/auth/login", "kirdi"), ("/api/auth/logout", "chiqdi"), ("/api/auth/password", "parol o'zgartirdi"),
    ("/api/admin/user/save", "foydalanuvchi saqlandi"), ("/api/admin/user/active", "foydalanuvchi holati"),
    ("/api/upload/preview", "GTD tekshirdi"), ("/api/upload/save", "GTD saqladi"), ("/api/upload/replace", "GTD almashtirdi"), ("/api/upload/void", "GTD bekor qildi"),
    ("/api/uploads/void", "GTD bekor qildi"), ("/api/issues", "vazifa/muammo"), ("/api/issue/", "vazifa/muammo"), ("/api/company/", "korxona"),
    ("/api/prev_year", "o'tgan yil ko'rsatkichi"), ("/api/analysis", "tahlil to'plami"),
    ("/api/template", "shablon yukladi"), ("/api/customs", "bojxona bazasi"), ("/api/companies/update", "korxona tahrir"),
    ("/api/companies", "korxona"), ("/api/board", "vazifa/muammo"), ("/api/backups/create", "zaxira oldi"), ("/api/backups/restore", "zaxiradan qaytardi"),
    ("/api/plans", "reja"), ("/api/periods", "amalda natijalar"), ("/api/fact_sets", "amalda to'plami"), ("/api/catalog", "katalog"), ("/api/export", "Excel yukladi"),
    ("/api/settings", "sozlamalar"), ("/api/reset", "bazani tozaladi"), ("/api/contacts", "aloqa import"),
]
def action_name(path: str, method: str) -> str:
    for pre, name in ACTION_NAMES:
        if path.startswith(pre): return name
    return "o'zgartirdi" if method == "POST" else "yukladi"
