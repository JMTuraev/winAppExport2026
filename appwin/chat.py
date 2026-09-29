"""Ichki chat — faqat ofis tarmog'i (LAN), internetga chiqmaydi.
Ma'lumot: data\\chat.db (WAL) + data\\chat_files\\<room>\\<id>_<nom>. Xonalar: kanal (#), guruh (tanlangan xodimlar), shaxsiy (2 kishi),
korxona threadi (INN). Har xabar/fayl bir yoki bir nechta ishga bog'lanadi (links jadvali): korxona(lar), soha(lar), tuman(lar),
vazifa (doska kartasi), xat / topshiriq — keyin «Fayllar» paneli va qidiruvda shu kesimlar bo'yicha topiladi."""
from __future__ import annotations
import json, os, re, sqlite3, datetime as dt, threading
from pathlib import Path
from app import db

_LOCK = threading.Lock()
MAX_FILE = 80 * 1024 * 1024
LINK_KINDS = ("company", "sector", "district", "issue", "doc")   # korxona · soha (tarmoq) · tuman · vazifa (doska kartasi) · xat/topshiriq
MAX_LINKS = 30
PRIVATE_KINDS = ("dm", "group")                                   # faqat a'zolar ko'radi
DEFAULT_CHANNELS = [("umumiy", "Bo'lim umumiy kanali"), ("kunlik-hisobot", "GTD yuklash, kunlik hisobot, svod"),
                    ("rahbar-topshiriqlari", "Rahbar topshiriqlari — har xabar ijro nazoratida")]

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, inn TEXT, topic TEXT,
  created_by INTEGER, created_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, last_id INTEGER NOT NULL DEFAULT 0, last_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rooms_inn ON rooms(inn) WHERE kind='company';
CREATE UNIQUE INDEX IF NOT EXISTS ux_rooms_channel ON rooms(name) WHERE kind='channel';
CREATE TABLE IF NOT EXISTS room_members (
  room_id INTEGER NOT NULL, user_id INTEGER NOT NULL, last_read_id INTEGER NOT NULL DEFAULT 0, joined_at TEXT, PRIMARY KEY (room_id, user_id)
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL, user_id INTEGER, kind TEXT NOT NULL DEFAULT 'text', text TEXT,
  file_id INTEGER, reply_to INTEGER, link_kind TEXT NOT NULL DEFAULT '', link_id TEXT, link_label TEXT,
  created_at TEXT NOT NULL, edited_at TEXT, deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_msg_room ON messages(room_id, id);
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL, message_id INTEGER, filename TEXT NOT NULL, stored TEXT NOT NULL,
  size INTEGER NOT NULL DEFAULT 0, mime TEXT, user_id INTEGER, created_at TEXT NOT NULL,
  link_kind TEXT NOT NULL DEFAULT '', link_id TEXT, link_label TEXT
);
CREATE INDEX IF NOT EXISTS ix_files_room ON files(room_id, id);
CREATE TABLE IF NOT EXISTS pins (room_id INTEGER NOT NULL, message_id INTEGER NOT NULL, PRIMARY KEY (room_id, message_id));
CREATE TABLE IF NOT EXISTS links (
  id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '', label TEXT NOT NULL,
  UNIQUE (message_id, kind, ref, label)
);
CREATE INDEX IF NOT EXISTS ix_links_msg ON links(message_id);
CREATE INDEX IF NOT EXISTS ix_links_ref ON links(kind, ref);
"""

# ------------------------------------------------------------ db
def db_path() -> Path: return db.BASE / "chat.db"
def files_dir() -> Path: return db.BASE / "chat_files"
def now() -> str: return dt.datetime.now().isoformat(timespec="seconds")

_FTS: bool | None = None

def connect() -> sqlite3.Connection:
    global _FTS
    p = db_path(); p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA synchronous=NORMAL")
    con.create_function("ulower", 1, _ulower, deterministic=True)
    con.executescript(SCHEMA)
    if con.execute("PRAGMA user_version").fetchone()[0] < 1:        # 2.2.1 → 2.3: bitta bog'lanish (link_kind) → links jadvali
        with _LOCK:
            con.execute("""INSERT OR IGNORE INTO links(message_id, kind, ref, label)
                           SELECT id, link_kind, coalesce(link_id, ''), coalesce(nullif(link_label, ''), link_id, '') FROM messages
                           WHERE link_kind<>'' AND deleted=0""")
            con.execute("PRAGMA user_version=1"); con.commit()
    if _FTS is None:
        try:
            con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS msg_fts USING fts5(text, tokenize='unicode61 remove_diacritics 2')")
            _FTS = True
        except sqlite3.OperationalError:
            _FTS = False
    return con

def init() -> None:
    """Standart kanallar (birinchi ishga tushirishda)."""
    con = connect()
    try:
        for name, topic in DEFAULT_CHANNELS:
            if not con.execute("SELECT 1 FROM rooms WHERE kind='channel' AND name=?", (name,)).fetchone():
                con.execute("INSERT INTO rooms(kind, name, topic, created_at) VALUES('channel', ?, ?, ?)", (name, topic, now()))
        con.commit()
    finally: con.close()

def _ulower(s):
    return s.lower() if isinstance(s, str) else s          # SQLite lower() faqat lotin harflarini kichraytiradi (kirill uchun)

# ------------------------------------------------------------ helpers
def _users(auth_con) -> dict[int, dict]:
    return {r["id"]: {"id": r["id"], "name": r["name"], "login": r["login"], "role": r["role"], "active": bool(r["active"])}
            for r in auth_con.execute("SELECT id, name, login, role, active FROM users")}

def _online_ids(auth_con, minutes: int = 5) -> set[int]:
    since = (dt.datetime.now() - dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")
    return {r[0] for r in auth_con.execute("SELECT DISTINCT user_id FROM user_sessions WHERE closed=0 AND last_seen>=?", (since,))}

def _last_seen(auth_con) -> dict[int, str]:
    return {r[0]: r[1] for r in auth_con.execute("SELECT user_id, max(last_seen) FROM user_sessions GROUP BY user_id")}

def _member(con, room: sqlite3.Row, uid: int) -> bool:
    if room["kind"] in ("channel", "company"): return True          # bo'lim ichida ochiq
    return bool(con.execute("SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (room["id"], uid)).fetchone())

def _room(con, rid: int, uid: int) -> sqlite3.Row:
    r = con.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if not r: raise ValueError("Xona topilmadi")
    if not _member(con, r, uid): raise PermissionError("Bu suhbat sizga ochiq emas")
    return r

def _touch_member(con, rid: int, uid: int, last_read: int | None = None) -> None:
    con.execute("INSERT OR IGNORE INTO room_members(room_id, user_id, joined_at) VALUES(?,?,?)", (rid, uid, now()))
    if last_read is not None:
        con.execute("UPDATE room_members SET last_read_id=max(last_read_id, ?) WHERE room_id=? AND user_id=?", (last_read, rid, uid))

def _safe_name(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (name or "fayl").strip()).strip(". ") or "fayl"
    return name[:120]

def _fts_put(con, mid: int, text: str) -> None:
    if _FTS and text:
        try: con.execute("INSERT OR REPLACE INTO msg_fts(rowid, text) VALUES(?,?)", (mid, text))
        except sqlite3.OperationalError: pass

def _fts_del(con, mid: int) -> None:
    if _FTS:
        try: con.execute("DELETE FROM msg_fts WHERE rowid=?", (mid,))
        except sqlite3.OperationalError: pass

def room_title(r: sqlite3.Row | dict, users: dict, me: int, members: list[int] | None = None) -> str:
    if r["kind"] == "dm":
        other = [m for m in (members or []) if m != me]
        u = users.get(other[0]) if other else None
        return u["name"] if u else (users.get(me, {}).get("name", "Men") + " (o'zim)")
    return r["name"]

# ------------------------------------------------------------ rooms
def rooms(con, auth_con, me: dict) -> dict:
    uid = me["id"]; users = _users(auth_con); online = _online_ids(auth_con)
    mem_rows = con.execute("SELECT room_id, user_id, last_read_id FROM room_members").fetchall()
    members: dict[int, list[int]] = {}; my_read: dict[int, int] = {}
    for m in mem_rows:
        members.setdefault(m["room_id"], []).append(m["user_id"])
        if m["user_id"] == uid: my_read[m["room_id"]] = m["last_read_id"]
    last = {r["room_id"]: dict(r) for r in con.execute("""SELECT m.room_id, m.id, m.user_id, m.kind, m.text, m.created_at, f.filename
                                                          FROM messages m LEFT JOIN files f ON f.id=m.file_id
                                                          WHERE m.deleted=0 AND m.id IN (SELECT max(id) FROM messages WHERE deleted=0 GROUP BY room_id)""")}
    out = []
    for r in con.execute("SELECT * FROM rooms WHERE archived=0 ORDER BY kind, name"):
        if not _member(con, r, uid): continue
        mids = members.get(r["id"], [])
        if r["kind"] == "dm" and uid not in mids: continue
        read = my_read.get(r["id"], 0)
        unread = con.execute("SELECT count(*) FROM messages WHERE room_id=? AND id>? AND deleted=0 AND user_id!=?", (r["id"], read, uid)).fetchone()[0]
        lm = last.get(r["id"])
        other = None
        if r["kind"] == "dm":
            o = [m for m in mids if m != uid]
            other = users.get(o[0]) if o else None
        out.append({"id": r["id"], "kind": r["kind"], "name": room_title(r, users, uid, mids), "inn": r["inn"], "topic": r["topic"],
                    "unread": unread, "last_id": lm["id"] if lm else 0, "last_at": lm["created_at"] if lm else r["created_at"],
                    "last_text": (lm["filename"] and ("📎 " + lm["filename"])) or (lm["text"] or "") if lm else "",
                    "last_by": users.get(lm["user_id"], {}).get("name") if lm else None, "last_kind": lm["kind"] if lm else None,
                    "other_id": other["id"] if other else None, "online": (other["id"] in online) if other else None,
                    "members": len(mids) if r["kind"] in PRIVATE_KINDS else None, "created_by": r["created_by"]})
    seen = _last_seen(auth_con)
    return {"rooms": out, "users": [{**u, "online": u["id"] in online, "last_seen": seen.get(u["id"])} for u in users.values() if u["active"] or u["id"] == uid],
            "online": sorted(online), "fts": bool(_FTS)}

def create_room(con, auth_con, me: dict, body: dict) -> dict:
    kind = body.get("kind"); uid = me["id"]
    if kind == "channel":
        if me["role"] not in ("superadmin", "operator"): raise PermissionError("Kanalni superadmin yoki operator ochadi")
        name = re.sub(r"[^\w\-]+", "-", (body.get("name") or "").strip().lower(), flags=re.U).strip("-")[:40]
        if not name: raise ValueError("Kanal nomi kerak (masalan: gijduvon)")
        r = con.execute("SELECT id FROM rooms WHERE kind='channel' AND name=?", (name,)).fetchone()
        if r:
            con.execute("UPDATE rooms SET archived=0 WHERE id=?", (r["id"],)); con.commit(); return {"id": r["id"], "existing": True}
        cur = con.execute("INSERT INTO rooms(kind, name, topic, created_by, created_at) VALUES('channel', ?, ?, ?, ?)",
                          (name, (body.get("topic") or "").strip()[:200], uid, now()))
        rid = cur.lastrowid
        _system(con, rid, uid, f"{me['name']} kanalni ochdi")
        con.commit(); return {"id": rid}
    if kind == "dm":
        other = int(body.get("user_id") or 0)
        if not other: raise ValueError("Xodimni tanlang")
        if not auth_con.execute("SELECT 1 FROM users WHERE id=? AND active=1", (other,)).fetchone(): raise ValueError("Xodim topilmadi")
        pair = sorted({uid, other})
        for r in con.execute("SELECT id FROM rooms WHERE kind='dm'"):
            mids = sorted(m[0] for m in con.execute("SELECT user_id FROM room_members WHERE room_id=?", (r["id"],)))
            if mids == pair or (len(pair) == 1 and mids == pair * 2): return {"id": r["id"], "existing": True}
        cur = con.execute("INSERT INTO rooms(kind, name, created_by, created_at) VALUES('dm', '', ?, ?)", (uid, now()))
        rid = cur.lastrowid
        for m in pair: _touch_member(con, rid, m)
        con.commit(); return {"id": rid}
    if kind == "group":
        name = re.sub(r"\s+", " ", (body.get("name") or "").strip())[:60]
        if not name: raise ValueError("Guruh nomini yozing")
        ids = {int(x) for x in (body.get("members") or []) if str(x).isdigit()} | {uid}
        active = {r[0] for r in auth_con.execute("SELECT id FROM users WHERE active=1")}
        ids &= active | {uid}
        if len(ids) < 2: raise ValueError("Kamida bitta xodimni tanlang")
        cur = con.execute("INSERT INTO rooms(kind, name, topic, created_by, created_at) VALUES('group', ?, ?, ?, ?)",
                          (name, (body.get("topic") or "").strip()[:200], uid, now()))
        rid = cur.lastrowid
        for m in ids: _touch_member(con, rid, m)
        _system(con, rid, uid, f"{me['name']} «{name}» guruhini ochdi · {len(ids)} a'zo")
        con.commit(); return {"id": rid}
    if kind == "company":
        inn = re.sub(r"\D", "", body.get("inn") or "")
        if not inn: raise ValueError("Korxona INN kerak")
        r = con.execute("SELECT id FROM rooms WHERE kind='company' AND inn=?", (inn,)).fetchone()
        if r:
            con.execute("UPDATE rooms SET archived=0 WHERE id=?", (r["id"],)); con.commit(); return {"id": r["id"], "existing": True}
        lc = db.connect()
        try: c = lc.execute("SELECT name, district_full FROM companies WHERE inn=?", (inn,)).fetchone()
        finally: lc.close()
        if not c: raise ValueError("Bunday INN bazada yo'q")
        cur = con.execute("INSERT INTO rooms(kind, name, inn, topic, created_by, created_at) VALUES('company', ?, ?, ?, ?, ?)",
                          (c["name"], inn, c["district_full"] or "", uid, now()))
        rid = cur.lastrowid
        _system(con, rid, uid, f"{me['name']} korxona threadini ochdi · INN {inn}")
        con.commit(); return {"id": rid}
    raise ValueError("Noma'lum xona turi")

def archive_room(con, me: dict, rid: int, on: bool = True) -> dict:
    r = con.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if not r: raise ValueError("Xona topilmadi")
    if r["kind"] == "channel" and me["role"] != "superadmin": raise PermissionError("Kanalni faqat superadmin yopadi")
    if r["kind"] == "dm": raise ValueError("Shaxsiy suhbat yopilmaydi")
    if r["kind"] == "group" and me["role"] != "superadmin" and r["created_by"] != me["id"]: raise PermissionError("Guruhni ochgan xodim yoki superadmin yopadi")
    con.execute("UPDATE rooms SET archived=? WHERE id=?", (1 if on else 0, rid)); con.commit()
    return {"ok": True}

def room_members(con, auth_con, me: dict, body: dict) -> dict:
    """Guruhga xodim qo'shish / chiqarish. Qo'shish — har bir a'zo; chiqarish — guruhni ochgan yoki superadmin (o'zini — har kim)."""
    rid = int(body.get("id") or 0); r = _room(con, rid, me["id"])
    if r["kind"] != "group": raise ValueError("A'zolar faqat guruhda boshqariladi")
    users = _users(auth_con); uid = me["id"]
    cur = {m[0] for m in con.execute("SELECT user_id FROM room_members WHERE room_id=?", (rid,))}
    add = [int(x) for x in (body.get("add") or []) if str(x).isdigit() and int(x) in users and users[int(x)]["active"] and int(x) not in cur]
    rem = [int(x) for x in (body.get("remove") or []) if str(x).isdigit() and int(x) in cur]
    if rem and any(x != uid for x in rem) and me["role"] != "superadmin" and r["created_by"] != uid:
        raise PermissionError("A'zoni guruhni ochgan xodim yoki superadmin chiqaradi")
    for x in add: _touch_member(con, rid, x)
    for x in rem: con.execute("DELETE FROM room_members WHERE room_id=? AND user_id=?", (rid, x))
    if add: _system(con, rid, uid, f"{me['name']} qo'shdi: " + ", ".join(users[x]["name"] for x in add))
    for x in rem: _system(con, rid, uid, f"{users[x]['name']} guruhdan chiqdi" if x == uid else f"{me['name']} chiqardi: {users[x]['name']}")
    con.commit(); return {"ok": True, "added": len(add), "removed": len(rem)}

def set_topic(con, me: dict, rid: int, topic: str) -> dict:
    r = con.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if r and r["kind"] == "group": _room(con, rid, me["id"])
    elif me["role"] not in ("superadmin", "operator"): raise PermissionError("Mavzuni superadmin yoki operator o'zgartiradi")
    con.execute("UPDATE rooms SET topic=? WHERE id=?", ((topic or "").strip()[:200], rid)); con.commit(); return {"ok": True}

# ------------------------------------------------------------ messages
def _system(con, rid: int, uid: int, text: str) -> int:
    cur = con.execute("INSERT INTO messages(room_id, user_id, kind, text, created_at) VALUES(?,?,'system',?,?)", (rid, uid, text, now()))
    con.execute("UPDATE rooms SET last_id=?, last_at=? WHERE id=?", (cur.lastrowid, now(), rid))
    return cur.lastrowid

def _msg_rows(con, rows, users: dict) -> list[dict]:
    ids = [r["id"] for r in rows]
    files = {}
    if ids:
        fids = [r["file_id"] for r in rows if r["file_id"]]
        if fids:
            files = {f["id"]: dict(f) for f in con.execute(f"SELECT * FROM files WHERE id IN ({','.join('?' * len(fids))})", fids)}
        pinned = {p[0] for p in con.execute(f"SELECT message_id FROM pins WHERE message_id IN ({','.join('?' * len(ids))})", ids)}
    else: pinned = set()
    links: dict[int, list[dict]] = {}
    if ids:
        for l in con.execute(f"SELECT message_id, kind, ref, label FROM links WHERE message_id IN ({','.join('?' * len(ids))}) ORDER BY id", ids):
            links.setdefault(l["message_id"], []).append({"kind": l["kind"], "id": l["ref"], "label": l["label"]})
    reply_ids = [r["reply_to"] for r in rows if r["reply_to"]]
    replies = {}
    if reply_ids:
        for r in con.execute(f"SELECT m.id, m.user_id, m.text, m.kind, m.deleted, f.filename FROM messages m LEFT JOIN files f ON f.id=m.file_id WHERE m.id IN ({','.join('?' * len(reply_ids))})", reply_ids):
            replies[r["id"]] = {"id": r["id"], "by": users.get(r["user_id"], {}).get("name", "—"),
                                "text": "(o'chirilgan)" if r["deleted"] else (r["filename"] and ("📎 " + r["filename"])) or (r["text"] or "")[:160]}
    out = []
    for r in rows:
        u = users.get(r["user_id"]) or {}
        m = {"id": r["id"], "room_id": r["room_id"], "user_id": r["user_id"], "by": u.get("name", "—"), "role": u.get("role"),
             "kind": r["kind"], "text": "" if r["deleted"] else (r["text"] or ""), "deleted": bool(r["deleted"]),
             "created_at": r["created_at"], "edited_at": r["edited_at"], "reply": replies.get(r["reply_to"]) if r["reply_to"] else None,
             "links": links.get(r["id"], []), "pinned": r["id"] in pinned}
        m["link"] = m["links"][0] if m["links"] else None
        f = files.get(r["file_id"]) if r["file_id"] else None
        if f and not r["deleted"]:
            m["file"] = {"id": f["id"], "name": f["filename"], "size": f["size"], "mime": f["mime"], "links": m["links"], "link": m["link"]}
        out.append(m)
    return out

def messages(con, auth_con, me: dict, rid: int, before: int | None = None, around: int | None = None, limit: int = 60) -> dict:
    uid = me["id"]; r = _room(con, rid, uid); users = _users(auth_con)
    limit = max(10, min(int(limit or 60), 200))
    if around:
        rows = con.execute("SELECT * FROM messages WHERE room_id=? AND id<=? ORDER BY id DESC LIMIT ?", (rid, around, limit // 2)).fetchall()[::-1]
        rows += con.execute("SELECT * FROM messages WHERE room_id=? AND id>? ORDER BY id LIMIT ?", (rid, around, limit // 2)).fetchall()
    elif before:
        rows = con.execute("SELECT * FROM messages WHERE room_id=? AND id<? ORDER BY id DESC LIMIT ?", (rid, before, limit)).fetchall()[::-1]
    else:
        rows = con.execute("SELECT * FROM messages WHERE room_id=? ORDER BY id DESC LIMIT ?", (rid, limit)).fetchall()[::-1]
    has_more = bool(rows) and bool(con.execute("SELECT 1 FROM messages WHERE room_id=? AND id<? LIMIT 1", (rid, rows[0]["id"])).fetchone())
    mids = [m[0] for m in con.execute("SELECT user_id FROM room_members WHERE room_id=?", (rid,))]
    online = _online_ids(auth_con)
    if r["kind"] in ("channel", "company"):
        member_list = [u for u in users.values() if u["active"]]
    else:
        member_list = [users[m] for m in mids if m in users]
    seen = _last_seen(auth_con)
    if not before and not around:
        _touch_member(con, rid, uid, rows[-1]["id"] if rows else 0); con.commit()
    room = {"id": r["id"], "kind": r["kind"], "name": room_title(r, users, uid, mids), "inn": r["inn"], "topic": r["topic"], "archived": bool(r["archived"]),
            "created_by": r["created_by"]}
    if r["kind"] == "company" and r["inn"]:
        lc = db.connect()
        try:
            c = lc.execute("SELECT name, district_full, tarmoq FROM companies WHERE inn=?", (r["inn"],)).fetchone()
            if c: room.update({"name": c["name"], "district": c["district_full"], "tarmoq": c["tarmoq"]})
            room["issues"] = [dict(i) for i in lc.execute("SELECT id, title, status, due_date FROM issues WHERE inn=? ORDER BY status='closed', id DESC LIMIT 8", (r["inn"],))]
        finally: lc.close()
    return {"room": room, "messages": _msg_rows(con, rows, users), "has_more": has_more,
            "members": [{**u, "online": u["id"] in online, "last_seen": seen.get(u["id"])} for u in member_list],
            "peer_read": _peer_read(con, rid, uid),
            "files_count": con.execute("SELECT count(*) FROM files WHERE room_id=?", (rid,)).fetchone()[0],
            "pins": _msg_rows(con, con.execute("SELECT m.* FROM messages m JOIN pins p ON p.message_id=m.id WHERE m.room_id=? AND m.deleted=0 ORDER BY m.id DESC LIMIT 10", (rid,)).fetchall(), users)}

def _peer_read(con, rid: int, uid: int) -> int:
    """Boshqa a'zolar o'qigan eng katta xabar id — ✓✓ belgisi uchun."""
    return con.execute("SELECT coalesce(max(last_read_id), 0) FROM room_members WHERE room_id=? AND user_id!=?", (rid, uid)).fetchone()[0]

def _links(raw) -> list[tuple[str, str, str]]:
    """Bog'lanishlar ro'yxati: [{kind, id, label}] (yoki eski bitta {kind,id,label} / JSON matn) → [(kind, ref, label)]."""
    if raw in (None, "", [], {}): return []
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except ValueError: raise ValueError("Bog'lanish ma'lumoti noto'g'ri")
    if isinstance(raw, dict): raw = [raw]
    out, seen = [], set()
    for x in raw[:MAX_LINKS]:
        if not isinstance(x, dict): continue
        kind = (x.get("kind") or "").strip()
        if not kind: continue
        if kind not in LINK_KINDS: raise ValueError("Noto'g'ri bog'lanish turi")
        ref = str(x.get("id") if x.get("id") is not None else "").strip()[:80]
        label = re.sub(r"\s+", " ", str(x.get("label") or ref)).strip()[:160]
        if not label: continue
        k = (kind, ref, label) if kind == "doc" else (kind, ref, "")
        if k in seen: continue
        seen.add(k); out.append((kind, ref, label))
    return out

def _save_links(con, mid: int, links: list[tuple[str, str, str]], replace: bool = False) -> None:
    if replace: con.execute("DELETE FROM links WHERE message_id=?", (mid,))
    for kind, ref, label in links:
        con.execute("INSERT OR IGNORE INTO links(message_id, kind, ref, label) VALUES(?,?,?,?)", (mid, kind, ref, label))

def send(con, auth_con, me: dict, body: dict) -> dict:
    uid = me["id"]; rid = int(body.get("room") or 0); r = _room(con, rid, uid)
    if r["archived"]: raise ValueError("Bu xona yopilgan")
    text = (body.get("text") or "").strip()
    if not text: raise ValueError("Bo'sh xabar")
    if len(text) > 8000: raise ValueError("Xabar juda uzun (8000 belgigacha)")
    reply_to = int(body.get("reply_to") or 0) or None
    if reply_to and not con.execute("SELECT 1 FROM messages WHERE id=? AND room_id=?", (reply_to, rid)).fetchone(): reply_to = None
    links = _links(body.get("links") if body.get("links") is not None else body.get("link"))
    ts = now()
    cur = con.execute("INSERT INTO messages(room_id, user_id, kind, text, reply_to, created_at) VALUES(?,?,'text',?,?,?)",
                      (rid, uid, text, reply_to, ts))
    mid = cur.lastrowid
    _save_links(con, mid, links)
    _fts_put(con, mid, text)
    con.execute("UPDATE rooms SET last_id=?, last_at=? WHERE id=?", (mid, ts, rid))
    _touch_member(con, rid, uid, mid)
    con.commit()
    users = _users(auth_con)
    return {"ok": True, "message": _msg_rows(con, [con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()], users)[0]}

def upload(con, auth_con, me: dict, rid: int, filename: str, raw: bytes, mime: str | None, link: dict | None, text: str = "") -> dict:
    uid = me["id"]; r = _room(con, rid, uid)
    if r["archived"]: raise ValueError("Bu xona yopilgan")
    if not raw: raise ValueError("Fayl bo'sh")
    if len(raw) > MAX_FILE: raise ValueError("Fayl juda katta (80 MB gacha)")
    links = _links(link)
    name = _safe_name(filename); ts = now()
    with _LOCK:
        cur = con.execute("INSERT INTO files(room_id, filename, stored, size, mime, user_id, created_at) VALUES(?,?,?,?,?,?,?)",
                          (rid, name, "", len(raw), mime or "", uid, ts))
        fid = cur.lastrowid
        folder = files_dir() / str(rid); folder.mkdir(parents=True, exist_ok=True)
        stored = f"{fid}_{name}"
        tmp = folder / (stored + ".tmp"); tmp.write_bytes(raw); os.replace(tmp, folder / stored)
        cur = con.execute("INSERT INTO messages(room_id, user_id, kind, text, file_id, created_at) VALUES(?,?,'file',?,?,?)",
                          (rid, uid, (text or "").strip()[:2000], fid, ts))
        mid = cur.lastrowid
        _save_links(con, mid, links)
        con.execute("UPDATE files SET stored=?, message_id=? WHERE id=?", (stored, mid, fid))
        _fts_put(con, mid, name + " " + (text or ""))
        con.execute("UPDATE rooms SET last_id=?, last_at=? WHERE id=?", (mid, ts, rid))
        _touch_member(con, rid, uid, mid)
        con.commit()
    users = _users(auth_con)
    return {"ok": True, "message": _msg_rows(con, [con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()], users)[0]}

def file_path(con, me: dict, fid: int) -> tuple[Path, str]:
    f = con.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    if not f: raise ValueError("Fayl topilmadi")
    _room(con, f["room_id"], me["id"])
    p = files_dir() / str(f["room_id"]) / f["stored"]
    if not p.is_file(): raise ValueError("Fayl diskda yo'q")
    return p, f["filename"]

def set_links(con, auth_con, me: dict, body: dict) -> dict:
    """Xabar yoki faylning bog'lanishlarini almashtirish (ko'p tanlov): body {message_id | file_id, links:[{kind,id,label}]}."""
    mid = int(body.get("message_id") or 0)
    if not mid and body.get("file_id"):
        f = con.execute("SELECT message_id FROM files WHERE id=?", (int(body["file_id"]),)).fetchone()
        if not f: raise ValueError("Fayl topilmadi")
        mid = f["message_id"]
    m = con.execute("SELECT * FROM messages WHERE id=? AND deleted=0", (mid,)).fetchone()
    if not m or m["kind"] == "system": raise ValueError("Xabar topilmadi")
    _room(con, m["room_id"], me["id"])
    links = _links(body.get("links") if body.get("links") is not None else body.get("link"))
    _save_links(con, mid, links, replace=True)
    if m["file_id"] and links:
        f = con.execute("SELECT filename FROM files WHERE id=?", (m["file_id"],)).fetchone()
        _system(con, m["room_id"], me["id"], f"{me['name']} «{f['filename'] if f else 'fayl'}» faylini bog'ladi → " + ", ".join(l[2] for l in links[:4]) + (f" (+{len(links) - 4})" if len(links) > 4 else ""))
    con.commit()
    users = _users(auth_con)
    return {"ok": True, "message": _msg_rows(con, [con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()], users)[0]}

def link_file(con, auth_con, me: dict, body: dict) -> dict:
    """Eski API (/api/chat/file/link {id, link}) — set_links ga yo'naltiriladi."""
    r = set_links(con, auth_con, me, {"file_id": body.get("id"), "links": body.get("links") if body.get("links") is not None else body.get("link")})
    m = r["message"]
    return {"ok": True, "file": {"id": int(body.get("id") or 0), "link": m["link"], "links": m["links"]}, "message": m}

def edit(con, auth_con, me: dict, body: dict) -> dict:
    mid = int(body.get("id") or 0); m = con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    if not m or m["deleted"]: raise ValueError("Xabar topilmadi")
    if m["user_id"] != me["id"] and me["role"] != "superadmin": raise PermissionError("Faqat o'z xabaringizni tahrirlaysiz")
    if m["kind"] == "system": raise ValueError("Tizim xabari tahrirlanmaydi")
    text = (body.get("text") or "").strip()
    if not text and m["kind"] == "text": raise ValueError("Bo'sh xabar")
    con.execute("UPDATE messages SET text=?, edited_at=? WHERE id=?", (text[:8000], now(), mid)); _fts_put(con, mid, text); con.commit()
    users = _users(auth_con)
    return {"ok": True, "message": _msg_rows(con, [con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()], users)[0]}

def delete(con, me: dict, mid: int) -> dict:
    m = con.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    if not m: raise ValueError("Xabar topilmadi")
    if m["user_id"] != me["id"] and me["role"] != "superadmin": raise PermissionError("Faqat o'z xabaringizni o'chirasiz")
    con.execute("UPDATE messages SET deleted=1 WHERE id=?", (mid,)); _fts_del(con, mid)
    con.execute("DELETE FROM links WHERE message_id=?", (mid,))
    con.execute("DELETE FROM pins WHERE message_id=?", (mid,))
    if m["file_id"]:
        f = con.execute("SELECT * FROM files WHERE id=?", (m["file_id"],)).fetchone()
        if f:
            try: (files_dir() / str(f["room_id"]) / f["stored"]).unlink(missing_ok=True)
            except Exception: pass
            con.execute("DELETE FROM files WHERE id=?", (f["id"],))
    con.commit(); return {"ok": True}

def pin(con, me: dict, mid: int, on: bool) -> dict:
    m = con.execute("SELECT room_id FROM messages WHERE id=? AND deleted=0", (mid,)).fetchone()
    if not m: raise ValueError("Xabar topilmadi")
    _room(con, m["room_id"], me["id"])
    if on: con.execute("INSERT OR IGNORE INTO pins(room_id, message_id) VALUES(?,?)", (m["room_id"], mid))
    else: con.execute("DELETE FROM pins WHERE message_id=?", (mid,))
    con.commit(); return {"ok": True}

def mark_read(con, me: dict, rid: int, last_id: int) -> dict:
    _room(con, rid, me["id"]); _touch_member(con, rid, me["id"], int(last_id or 0)); con.commit(); return {"ok": True}

# ------------------------------------------------------------ live updates (polling, 3 s)
def updates(con, auth_con, me: dict, rid: int | None, since: int) -> dict:
    uid = me["id"]; users = _users(auth_con); online = _online_ids(auth_con)
    out = {"online": sorted(online), "now": now()}
    if rid:
        r = _room(con, rid, uid)
        rows = con.execute("SELECT * FROM messages WHERE room_id=? AND id>? ORDER BY id LIMIT 200", (rid, since)).fetchall()
        out["messages"] = _msg_rows(con, rows, users)
        # tahrir / o'chirish / bog'lanish o'zgargan eski xabarlar
        changed = con.execute("SELECT * FROM messages WHERE room_id=? AND id<=? AND (edited_at>? OR deleted=1) ORDER BY id DESC LIMIT 50",
                              (rid, since, (dt.datetime.now() - dt.timedelta(seconds=20)).isoformat(timespec="seconds"))).fetchall()
        out["changed"] = _msg_rows(con, changed, users)
        if rows:
            _touch_member(con, rid, uid, rows[-1]["id"]); con.commit()
        out["peer_read"] = _peer_read(con, rid, uid)
    # boshqa xonalardagi o'qilmaganlar
    reads = {m["room_id"]: m["last_read_id"] for m in con.execute("SELECT room_id, last_read_id FROM room_members WHERE user_id=?", (uid,))}
    unread = {}
    for r in con.execute("SELECT id, kind FROM rooms WHERE archived=0"):
        if r["id"] == rid: continue
        if r["kind"] in PRIVATE_KINDS and r["id"] not in reads: continue
        n = con.execute("SELECT count(*) FROM messages WHERE room_id=? AND id>? AND deleted=0 AND user_id!=?", (r["id"], reads.get(r["id"], 0), uid)).fetchone()[0]
        if n: unread[str(r["id"])] = n
    out["unread"] = unread
    out["max_id"] = con.execute("SELECT coalesce(max(id),0) FROM messages").fetchone()[0]
    return out

def unread_total(con, me: dict) -> int:
    uid = me["id"]
    reads = {m["room_id"]: m["last_read_id"] for m in con.execute("SELECT room_id, last_read_id FROM room_members WHERE user_id=?", (uid,))}
    n = 0
    for r in con.execute("SELECT id, kind FROM rooms WHERE archived=0"):
        if r["kind"] in PRIVATE_KINDS and r["id"] not in reads: continue
        n += con.execute("SELECT count(*) FROM messages WHERE room_id=? AND id>? AND deleted=0 AND user_id!=?", (r["id"], reads.get(r["id"], 0), uid)).fetchone()[0]
    return n

# ------------------------------------------------------------ search, files, lookup
def search(con, auth_con, me: dict, q: str, rid: int | None = None, limit: int = 40) -> dict:
    q = (q or "").strip(); uid = me["id"]; users = _users(auth_con)
    if len(q) < 2: return {"rows": []}
    rows = []
    if _FTS:
        try:
            fq = " ".join('"' + t.replace('"', '') + '"*' for t in q.split()[:6])
            ids = [r[0] for r in con.execute("SELECT rowid FROM msg_fts WHERE msg_fts MATCH ? ORDER BY rank LIMIT ?", (fq, limit * 3))]
            if ids: rows = con.execute(f"SELECT * FROM messages WHERE id IN ({','.join('?' * len(ids))}) AND deleted=0 ORDER BY id DESC", ids).fetchall()
        except sqlite3.OperationalError: rows = []
    like = "%" + q.lower() + "%"
    if not rows:
        rows = con.execute("""SELECT m.* FROM messages m LEFT JOIN files f ON f.id=m.file_id
                              WHERE m.deleted=0 AND (ulower(m.text) LIKE ? OR ulower(f.filename) LIKE ?) ORDER BY m.id DESC LIMIT ?""", (like, like, limit * 3)).fetchall()
    # ishga bog'langanlar: «Тўқимачилик», «Ғиждувон», korxona nomi yoki INN, «xat №…» bo'yicha
    have = {r["id"] for r in rows}
    extra = [r for r in con.execute("""SELECT DISTINCT m.* FROM links l JOIN messages m ON m.id=l.message_id
                                        WHERE m.deleted=0 AND (ulower(l.label) LIKE ? OR l.ref=?) ORDER BY m.id DESC LIMIT ?""", (like, q, limit * 3)) if r["id"] not in have]
    rows = list(rows) + extra
    room_cache: dict[int, sqlite3.Row | None] = {}
    out = []
    for r in rows:
        if rid and r["room_id"] != rid: continue
        if r["room_id"] not in room_cache:
            rr = con.execute("SELECT * FROM rooms WHERE id=?", (r["room_id"],)).fetchone()
            room_cache[r["room_id"]] = rr if rr and _member(con, rr, uid) else None
        rr = room_cache[r["room_id"]]
        if not rr: continue
        mids = [m[0] for m in con.execute("SELECT user_id FROM room_members WHERE room_id=?", (rr["id"],))] if rr["kind"] in PRIVATE_KINDS else []
        if rr["kind"] in PRIVATE_KINDS and uid not in mids: continue
        m = _msg_rows(con, [r], users)[0]
        m["room"] = {"id": rr["id"], "kind": rr["kind"], "name": room_title(rr, users, uid, mids)}
        out.append(m)
        if len(out) >= limit: break
    return {"rows": out}

def files(con, auth_con, me: dict, rid: int | None, link_kind: str | None, q: str | None, limit: int = 80, ref: str | None = None) -> dict:
    uid = me["id"]; users = _users(auth_con)
    sql = "SELECT f.*, m.deleted FROM files f LEFT JOIN messages m ON m.id=f.message_id WHERE coalesce(m.deleted,0)=0"; args: list = []
    if rid: sql += " AND f.room_id=?"; args.append(rid)
    if link_kind == "none": sql += " AND NOT EXISTS (SELECT 1 FROM links l WHERE l.message_id=f.message_id)"
    elif link_kind in LINK_KINDS:
        sql += " AND EXISTS (SELECT 1 FROM links l WHERE l.message_id=f.message_id AND l.kind=?" + (" AND l.ref=?" if ref else "") + ")"
        args += [link_kind] + ([ref] if ref else [])
    if q:
        sql += " AND (ulower(f.filename) LIKE ? OR EXISTS (SELECT 1 FROM links l WHERE l.message_id=f.message_id AND (ulower(l.label) LIKE ? OR l.ref=?)))"
        args += ["%" + q.lower() + "%"] * 2 + [q.strip()]
    sql += " ORDER BY f.id DESC LIMIT ?"; args.append(limit)
    room_cache: dict[int, sqlite3.Row | None] = {}
    out = []
    frows = con.execute(sql, args).fetchall()
    lk_by: dict[int, list[dict]] = {}
    mids = [f["message_id"] for f in frows if f["message_id"]]
    if mids:
        for l in con.execute(f"SELECT message_id, kind, ref, label FROM links WHERE message_id IN ({','.join('?' * len(mids))}) ORDER BY id", mids):
            lk_by.setdefault(l["message_id"], []).append({"kind": l["kind"], "id": l["ref"], "label": l["label"]})
    for f in frows:
        if f["room_id"] not in room_cache:
            rr = con.execute("SELECT * FROM rooms WHERE id=?", (f["room_id"],)).fetchone()
            ok = rr and _member(con, rr, uid)
            if ok and rr["kind"] in PRIVATE_KINDS and not con.execute("SELECT 1 FROM room_members WHERE room_id=? AND user_id=?", (rr["id"], uid)).fetchone(): ok = False
            room_cache[f["room_id"]] = rr if ok else None
        rr = room_cache[f["room_id"]]
        if not rr: continue
        out.append({"id": f["id"], "name": f["filename"], "size": f["size"], "mime": f["mime"], "by": users.get(f["user_id"], {}).get("name", "—"),
                    "created_at": f["created_at"], "message_id": f["message_id"], "room": {"id": rr["id"], "kind": rr["kind"], "name": room_title(rr, users, uid)},
                    "links": lk_by.get(f["message_id"], [])})
    return {"rows": out}

def lookup(q: str, limit: int = 8, kinds: str | None = None, con=None) -> dict:
    """Bog'lash uchun (export.db): korxonalar (nom/INN), sohalar (tarmoq), tumanlar, doska kartalari.
    q bo'sh bo'lsa — barcha tumanlar va sohalar (tez tanlash uchun), korxona/vazifa yo'q."""
    q = (q or "").strip(); like = "%" + q.lower() + "%"
    want = set((kinds or "company,sector,district,issue,doc").split(","))
    out = {"companies": [], "sectors": [], "districts": [], "issues": [], "docs": []}
    if "doc" in want and con is not None:       # oldin ishlatilgan xat / topshiriq nomlari — qayta tanlash uchun
        out["docs"] = [{"label": r[0], "n": r[1]} for r in con.execute("""SELECT label, count(*) FROM links WHERE kind='doc' AND (?='' OR ulower(label) LIKE ?)
                                                                        GROUP BY label ORDER BY max(id) DESC LIMIT ?""", (q, like, 8 if not q else limit))]
    lc = db.connect()
    try:
        lc.create_function("ulower", 1, _ulower, deterministic=True)
        if "company" in want and q:
            out["companies"] = [dict(r) for r in lc.execute("""SELECT inn, name, district_full AS district, tarmoq FROM companies
                                                             WHERE ulower(name) LIKE ? OR inn LIKE ? ORDER BY name LIMIT ?""", (like, q + "%", limit))]
        if "sector" in want:
            out["sectors"] = [{"name": r[0], "n": r[1]} for r in lc.execute("""SELECT trim(tarmoq), count(*) FROM companies
                                  WHERE tarmoq IS NOT NULL AND trim(tarmoq)<>'' AND (?='' OR ulower(tarmoq) LIKE ?) GROUP BY trim(tarmoq) ORDER BY 2 DESC, 1
                                  LIMIT ?""", (q, like, 60 if not q else limit))]
        if "district" in want:
            out["districts"] = [{"code": r[0], "name": r[1]} for r in lc.execute("""SELECT code, name_uz FROM districts
                                  WHERE ?='' OR ulower(name_uz) LIKE ? OR ulower(coalesce(name_ru,'')) LIKE ? OR code=? ORDER BY coalesce(order_no, 99), name_uz""",
                                  (q, like, like, q))]
        if "issue" in want and q:
            out["issues"] = [dict(r) for r in lc.execute("""SELECT i.id, i.title, i.status, i.due_date, i.inn, c.name AS company FROM issues i LEFT JOIN companies c ON c.inn=i.inn
                                                          WHERE ulower(i.title) LIKE ? OR (i.id=? ) ORDER BY i.status='closed', i.id DESC LIMIT ?""",
                                                       (like, int(q) if q.isdigit() else -1, limit))]
    finally: lc.close()
    return out

def stats(con) -> dict:
    return {"messages": con.execute("SELECT count(*) FROM messages WHERE deleted=0").fetchone()[0],
            "files": con.execute("SELECT count(*) FROM files").fetchone()[0],
            "rooms": con.execute("SELECT count(*) FROM rooms WHERE archived=0").fetchone()[0],
            "mb": round(sum(f.stat().st_size for f in files_dir().rglob("*") if f.is_file()) / 1048576, 1) if files_dir().exists() else 0}
