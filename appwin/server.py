"""AppWin server: the site handler (AppWin\\app — the former EksportMonitor code, now part of AppWin) + login, roles,
audit, LAN binding, backup and update APIs. Standalone: PYTHONPATH = AppWin\\vendor;AppWin."""
from __future__ import annotations
import json, os, sys, socket, threading, time, datetime as dt, urllib.parse, shutil, webbrowser, http.cookies
from pathlib import Path
from app import server as legacy, db          # AppWin\app (site)
from . import auth, backup, update, chat, xatlar, __version__

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
APP_DIR = ROOT.parent                          # AppWin\
CONFIG = APP_DIR / "config.json"
COOKIE = "em_session"
STARTED = dt.datetime.now()
PUBLIC_GET_PREFIXES = ("/appwin/", "/static/fonts/", "/static/chart.umd.js", "/static/vendor/")
SUPERADMIN_POSTS = ("/api/backups/restore", "/api/reset", "/api/init/", "/api/customs/clear", "/api/settings/reset")
EXPORT_LOCK = threading.Lock()
_BK_CACHE: dict = {"t": 0, "v": None}
_MF_CACHE: dict = {"t": 0, "v": None}

def update_manifest_cached(max_age: float = 30) -> dict:
    if time.time() - _MF_CACHE["t"] > max_age:
        _MF_CACHE["v"] = update.manifest(APP_DIR); _MF_CACHE["t"] = time.time()
    return _MF_CACHE["v"]
_first_admin: dict | None = None

def backup_status_cached(max_age: float = 60) -> dict | None:
    """Disk status for the status line — at most once a minute (a sleeping USB disk must not slow every page)."""
    if time.time() - _BK_CACHE["t"] > max_age:
        try: _BK_CACHE["v"] = backup.disk_status(load_config())
        except Exception: _BK_CACHE["v"] = None
        _BK_CACHE["t"] = time.time()
    return _BK_CACHE["v"]

def load_config() -> dict:
    r"""AppWin\config.json. data_dir default: ..\data (the shared D:\2026 export\data layout) if it exists, else AppWin\data."""
    cfg = legacy.load_config()                 # same file (app.server.APP_DIR == AppWin); gives port/open_browser defaults
    cfg.setdefault("host", "0.0.0.0")
    own = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    cfg.update(own)
    if "data_dir" in own:
        d = Path(own["data_dir"])
        cfg["data_path"] = (d if d.is_absolute() else APP_DIR / d).resolve()
    else:
        shared = APP_DIR.parent / "data"
        cfg["data_path"] = (shared if (shared / "export.db").exists() else APP_DIR / "data").resolve()
    return cfg

def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        try:
            ips = [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")]
            return ips[0] if ips else "127.0.0.1"
        except Exception: return "127.0.0.1"

def server_info(con=None) -> dict:
    last_backup = None
    try:
        bk = sorted(db.BACKUP_DIR.glob("export_*.db")) if db.BACKUP_DIR.exists() else []
        last_backup = bk[-1].name if bk else None
    except Exception: pass
    return {"host": legacy.HOST, "ip": lan_ip(), "port": PORT, "version": __version__, "started": STARTED.isoformat(timespec="seconds"),
            "uptime_min": int((dt.datetime.now() - STARTED).total_seconds() // 60), "db_path": str(db.DB_PATH),
            "db_mb": round(db.DB_PATH.stat().st_size / 1048576, 1) if db.DB_PATH.exists() else 0, "last_backup": last_backup,
            "readonly": legacy.STATE["readonly"], "python": sys.version.split()[0]}

PORT = 8765

class Handler(legacy.Handler):
    server_version = f"EksportMonitor-AppWin/{__version__}"
    user: dict | None = None
    _code: int = 200

    # ---- plumbing
    def send_json(self, obj, code=200):
        self._code = code
        return super().send_json(obj, code)

    def send_file(self, path: Path, download_name=None, extra=None, inline_name=None):
        self._code = 200
        if download_name and self.user:
            self._audit("Excel yukladi", self.path.split("?")[0], download_name)
        return super().send_file(path, download_name, extra, inline_name)

    def client_ip(self) -> str: return self.client_address[0]

    def send_site(self):
        """EksportMonitor index.html + AppWin brand (logo, header, user chip) — the site's own files stay untouched."""
        html = (legacy.STATIC / "index.html").read_text(encoding="utf-8")
        inj_head = '<link rel="icon" href="/appwin/logo.svg"><link rel="stylesheet" href="/appwin/brand.css">'
        inj_body = '<script src="/appwin/brand.js"></script>'
        html = html.replace("</head>", inj_head + "\n</head>", 1).replace("</body>", inj_body + "\n</body>", 1)
        data = html.encode("utf-8")
        self._code = 200
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def cookie_token(self) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):        # by hand: SimpleCookie stops at any odd cookie from another app
            k, _, v = part.strip().partition("=")
            if k == COOKIE and v: return v.strip()
        return None

    def drain_body(self):
        """Read and discard an unread request body (uploads) before an early 401/403 — otherwise Windows resets the socket and the browser shows «Failed to fetch»."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            while n > 0:
                chunk = self.rfile.read(min(n, 1 << 20)); n -= len(chunk)
                if not chunk: break
        except Exception: pass

    def load_user(self, page: str | None = None):
        con = auth.connect()
        try: self.user = auth.session_user(con, self.cookie_token(), self.client_ip(), page)
        finally: con.close()
        return self.user

    def _audit(self, action: str, path: str, detail: str = "", ok: bool = True):
        try:
            con = auth.connect()
            try:
                auth.audit(con, self.user["id"] if self.user else None, self.user["login"] if self.user else None, self.client_ip(), action, path, detail, ok)
                con.commit()
            finally: con.close()
        except Exception as e:
            sys.stderr.write(f"audit xato: {e}\n")

    def redirect(self, to: str):
        self.send_response(302); self.send_header("Location", to); self.send_header("Cache-Control", "no-store"); self.end_headers()

    def set_cookie(self, token: str, max_age: int):
        self.send_header("Set-Cookie", f"{COOKIE}={token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Lax")

    def require_role(self, *roles):
        if not self.user or self.user["role"] not in roles:
            self._audit("rad etildi", self.path.split("?")[0], f"rol {self.user['role'] if self.user else '-'} — ruxsat yo'q", ok=False)
            raise PermissionError("Bu amal uchun ruxsatingiz yo'q")

    # ---- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = u.path
        try:
            if p.startswith("/appwin/"):
                f = (STATIC / p[len("/appwin/"):]).resolve()
                if STATIC in f.parents and f.is_file(): return self.send_file(f)
                return self.send_json({"error": "topilmadi"}, 404)
            if p == "/appwin-update/manifest":
                return self.send_json(update_manifest_cached())
            if p == "/appwin-update/file":
                f = update.safe_rel(q.get("p", ""), APP_DIR)
                if f is None or not f.is_file(): return self.send_json({"error": "topilmadi"}, 404)
                return self.send_file(f)
            if p == "/login":
                if self.load_user(): return self.redirect("/")
                return self.send_file(STATIC / "login.html")
            self.load_user()
            if p == "/api/auth/me":
                if not self.user:
                    return self.send_json({"user": None, "server": {"version": __version__, "port": PORT, "ip": lan_ip(), "host": legacy.HOST}})
                con = auth.connect()
                try: n_online = len(auth.online(con))
                finally: con.close()
                bk = backup_status_cached() if self.user["role"] == "superadmin" else None
                return self.send_json({"user": {k: v for k, v in self.user.items() if k != "token"}, "server": server_info(), "online": n_online,
                                       "roles": auth.ROLES, "backup": bk})
            if not self.user:
                if any(p.startswith(x) for x in PUBLIC_GET_PREFIXES): return super().do_GET()
                if p.startswith("/api/"): return self.send_json({"error": "Kirish talab qilinadi", "login": True}, 401)
                return self.redirect("/login")
            if auth.must_change_blocked(self.user, p):
                if p.startswith("/api/"): return self.send_json({"error": "Avval parolni o'zgartiring", "must_change": True}, 403)
                return self.redirect("/login")
            if p in ("/", "/index.html", "/legacy", "/legacy/"): return self.send_site()
            if p == "/chat": return self.send_file(STATIC / "chat.html")
            if p.startswith("/api/chat/"): return self.chat_get(p, q)
            if p.startswith("/api/xatlar/"): return self.xat_get(p, q)
            if p == "/admin":
                self.require_role("superadmin")
                return self.send_file(STATIC / "admin.html")
            if p == "/logout":
                con = auth.connect()
                try: auth.logout(con, self.user["token"], self.user, self.client_ip())
                finally: con.close()
                self.send_response(302); self.send_header("Location", "/login"); self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"); self.end_headers(); return
            if p == "/api/auth/online":
                self.require_role("superadmin", "operator")
                con = auth.connect()
                try: return self.send_json({"online": [{k: v for k, v in o.items() if k not in ("ip", "host")} for o in auth.online(con)]})
                finally: con.close()
            if p.startswith("/api/admin/"):
                self.require_role("superadmin")
                con = auth.connect()
                try:
                    if p == "/api/admin/users":
                        lc = legacy.conn()
                        try: dists = [dict(r) for r in lc.execute("SELECT code, name_uz FROM districts ORDER BY name_uz")]
                        finally: lc.close()
                        return self.send_json({"users": auth.list_users(con), "roles": auth.ROLES, "districts": dists})
                    if p == "/api/admin/online": return self.send_json({"online": auth.online(con)})
                    if p == "/api/admin/audit": return self.send_json(auth.audit_list(con, q))
                    if p == "/api/admin/audit.xlsx":
                        out = db.BASE / "exports" / f"audit_{dt.datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{os.getpid()}_{threading.get_ident()}.xlsx"
                        try: return self.send_file(audit_xlsx(auth.audit_list(con, dict(q, limit="2000"))["rows"], out), download_name=f"audit_{dt.date.today().isoformat()}.xlsx")
                        finally:
                            try: out.unlink(missing_ok=True)
                            except Exception: pass
                    if p == "/api/admin/backup":
                        cfg = load_config(); st = backup.disk_status(cfg)
                        st["snapshots"] = backup.list_snapshots(backup.backup_root(cfg))[::-1][:40] if st.get("connected") else []
                        _BK_CACHE.update({"t": time.time(), "v": {k: v for k, v in st.items() if k != "snapshots"}})
                        return self.send_json(st)
                    if p == "/api/admin/update":
                        return self.send_json({"repos": [update.repo_status(APP_DIR, fetch=q.get("fetch") != "0")],
                                               "stamp": update_manifest_cached()["stamp"], "exe": sys.executable})
                    if p == "/api/admin/server":
                        info = server_info()
                        info["sessions_open"] = con.execute("SELECT count(*) FROM user_sessions WHERE closed=0 AND expires_at>?", (auth.now(),)).fetchone()[0]
                        info["audit_today"] = con.execute("SELECT count(*) FROM user_audit WHERE ts>=?", (dt.date.today().isoformat(),)).fetchone()[0]
                        info["audit_denied_today"] = con.execute("SELECT count(*) FROM user_audit WHERE ts>=? AND ok=0", (dt.date.today().isoformat(),)).fetchone()[0]
                        info["auth_db"] = str(auth.db_path())
                        info["backups"] = [{"name": b.name, "mb": round(b.stat().st_size / 1048576, 1)} for b in sorted(db.BACKUP_DIR.glob("export_*.db"))[-8:][::-1]] if db.BACKUP_DIR.exists() else []
                        return self.send_json(info)
                    return self.send_json({"error": "topilmadi"}, 404)
                finally: con.close()
            if p == "/api/my/today":
                con = legacy.conn()
                try: return self.send_json(today_panel(con, self.user))
                finally: con.close()
            if p.startswith("/api/export") or p.endswith("/template"):     # legacy writes reports to fixed file names: one at a time
                with EXPORT_LOCK: return super().do_GET()
            return super().do_GET()
        except PermissionError as e:
            return self.send_json({"error": str(e)}, 403)
        except Exception as e:
            return legacy.err_json(self, e, self.path)

    # ---- POST
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); p = u.path
        try:
            if p == "/api/quit": return super().do_POST()          # local restart handshake (token-protected)
            # CSRF: a page from another host must not post here
            origin = self.headers.get("Origin")
            if origin:
                oh = urllib.parse.urlparse(origin).hostname
                hh = (self.headers.get("Host") or "").split(":")[0]
                if oh not in (hh, "127.0.0.1", "localhost"):
                    return self.send_json({"error": "Tashqi sahifadan so'rov qabul qilinmaydi"}, 403)
                self.headers.replace_header("Origin", "http://127.0.0.1")   # legacy check accepts only localhost
            if p == "/api/auth/login":
                body = self.body_json()
                con = auth.connect()
                try:
                    try:
                        user, token, max_age = auth.login(con, body.get("login"), body.get("password"), self.client_ip(),
                                                          body.get("host") or "", self.headers.get("User-Agent") or "", bool(body.get("remember")))
                    except PermissionError as e:
                        con.commit(); return self.send_json({"error": str(e)}, 401)
                finally: con.close()
                payload = json.dumps({"ok": True, "user": user}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload))); self.set_cookie(token, max_age); self.send_header("Cache-Control", "no-store")
                self.end_headers(); self.wfile.write(payload); return
            self.load_user()
            if not self.user: self.drain_body(); return self.send_json({"error": "Kirish talab qilinadi", "login": True}, 401)
            if auth.must_change_blocked(self.user, p): self.drain_body(); return self.send_json({"error": "Avval parolni o'zgartiring", "must_change": True}, 403)
            if p == "/api/auth/logout":
                con = auth.connect()
                try: auth.logout(con, self.user["token"], self.user, self.client_ip())
                finally: con.close()
                payload = b'{"ok": true}'
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload)))
                self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"); self.end_headers(); self.wfile.write(payload); return
            if p == "/api/auth/page":
                body = self.body_json(); self.load_user(page=(body.get("page") or "")[:80]); return self.send_json({"ok": True})
            if p.startswith("/api/chat/"): return self.chat_post(p, urllib.parse.parse_qs(u.query))
            if p.startswith("/api/xatlar/"): return self.xat_post(p)
            if p == "/api/auth/password":
                body = self.body_json(); con = auth.connect()
                try:
                    auth.change_password(con, self.user, body.get("old"), body.get("new"))
                    auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "parol o'zgartirdi", p, ""); con.commit()
                finally: con.close()
                return self.send_json({"ok": True})
            if p.startswith("/api/admin/"):
                self.require_role("superadmin")
                body = self.body_json(); con = auth.connect()
                try:
                    if p == "/api/admin/user/save":
                        r = auth.save_user(con, body, self.user)
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "foydalanuvchi saqlandi", p,
                                   f"{r['login']} · {r['role_name']}" + (" · parol yangilandi" if body.get("password") else "")); con.commit()
                        return self.send_json({"ok": True, "user": r})
                    if p == "/api/admin/user/active":
                        r = auth.set_active(con, int(body["id"]), bool(body["active"]), self.user)
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "foydalanuvchi holati", p,
                                   f"{r['login']} → {'faol' if r['active'] else 'bloklangan'}"); con.commit()
                        return self.send_json({"ok": True, "user": r})
                    if p == "/api/admin/backup/run":
                        r = backup.run(load_config(), by=self.user["login"], reason="manual")
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "tashqi zaxira", p, f"{r['name']} · {r['mb']} MB · {'✓' if r['ok'] else 'XATO'}", ok=r["ok"]); con.commit()
                        return self.send_json({"ok": True, **r})
                    if p == "/api/admin/backup/verify":
                        return self.send_json(backup.verify(load_config(), body.get("name")))
                    if p == "/api/admin/update/pull":
                        res = update.repo_pull(APP_DIR)
                        _MF_CACHE["t"] = 0
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "yangilanish", p,
                                   ("✓ " if res["ok"] else "✕ ") + (res.get("out") or res.get("error") or "")[:200], ok=res["ok"]); con.commit()
                        return self.send_json({"ok": True, "appwin": res})
                    if p == "/api/admin/restart":
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "qayta ishga tushirish", p, ""); con.commit()
                        self.send_json({"ok": True})
                        def _go():
                            time.sleep(0.6); update.restart_self(APP_DIR, log=lambda *a: sys.stderr.write(" ".join(map(str, a)) + "\n"))
                            time.sleep(1.5); legacy.release_lock(); os._exit(0)
                        threading.Thread(target=_go, daemon=True).start(); return
                    if p == "/api/admin/user/kick":
                        n = auth.close_user_sessions(con, int(body["id"]))
                        auth.audit(con, self.user["id"], self.user["login"], self.client_ip(), "sessiya yopildi", p, f"user {body['id']} · {n} sessiya"); con.commit()
                        return self.send_json({"ok": True, "closed": n})
                    return self.send_json({"error": "topilmadi"}, 404)
                finally: con.close()
            # everything else is EksportMonitor: writers only; whole-database actions — superadmin only
            if self.user["role"] not in auth.WRITE_ROLES:
                self.drain_body()
                self._audit("rad etildi", p, f"{auth.action_name(p, 'POST')} — {self.user['role_name']} roliga ruxsat yo'q", ok=False)
                return self.send_json({"error": f"«{self.user['role_name']}» roli o'zgartira olmaydi — faqat ko'rish"}, 403)
            if any(p.startswith(x) for x in SUPERADMIN_POSTS) and self.user["role"] != "superadmin":
                self.drain_body()
                self._audit("rad etildi", p, f"{auth.action_name(p, 'POST')} — faqat superadmin", ok=False)
                return self.send_json({"error": "Bu amal faqat superadmin uchun (butun bazaga ta'sir qiladi)"}, 403)
            fname = self.headers.get("X-Filename")
            detail = urllib.parse.unquote(fname) if fname else ""
            super().do_POST()
            self._audit(auth.action_name(p, "POST"), p, detail, ok=self._code < 400)
        except PermissionError as e:
            return self.send_json({"error": str(e)}, 403)
        except Exception as e:
            return legacy.err_json(self, e, self.path)

    # ---- chat (ichki, faqat LAN) — hamma faol xodimga ochiq, rol talab qilmaydi
    def chat_get(self, p: str, q: dict):
        con = chat.connect(); ac = auth.connect()
        try:
            me = self.user
            if p == "/api/chat/rooms": return self.send_json(chat.rooms(con, ac, me))
            if p == "/api/chat/messages":
                return self.send_json(chat.messages(con, ac, me, int(q.get("room") or 0), int(q["before"]) if q.get("before") else None,
                                                    int(q["around"]) if q.get("around") else None, int(q.get("limit") or 60)))
            if p == "/api/chat/updates":
                return self.send_json(chat.updates(con, ac, me, int(q["room"]) if q.get("room") else None, int(q.get("since") or 0)))
            if p == "/api/chat/unread": return self.send_json({"unread": chat.unread_total(con, me)})
            if p == "/api/chat/search": return self.send_json(chat.search(con, ac, me, q.get("q", ""), int(q["room"]) if q.get("room") else None))
            if p == "/api/chat/files": return self.send_json(chat.files(con, ac, me, int(q["room"]) if q.get("room") else None, q.get("link"), q.get("q"), ref=q.get("ref")))
            if p == "/api/chat/lookup": return self.send_json(chat.lookup(q.get("q", ""), kinds=q.get("kinds"), con=con))
            if p == "/api/chat/file":
                path, name = chat.file_path(con, me, int(q.get("id") or 0))
                self._code = 200
                if q.get("inline"): return legacy.Handler.send_file(self, path, inline_name=name)
                return legacy.Handler.send_file(self, path, download_name=name)
            if p == "/api/chat/stats": return self.send_json(chat.stats(con))
            return self.send_json({"error": "topilmadi"}, 404)
        finally: con.close(); ac.close()

    def chat_post(self, p: str, qs: dict):
        q = {k: v[0] for k, v in qs.items()}
        con = chat.connect(); ac = auth.connect()
        try:
            me = self.user
            if p == "/api/chat/upload":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > chat.MAX_FILE: self.drain_body(); raise ValueError("Fayl bo'sh yoki juda katta (80 MB gacha)")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "fayl")
                link = q.get("links") or ({"kind": q.get("link_kind", ""), "id": q.get("link_id"), "label": q.get("link_label", "")} if q.get("link_kind") else None)
                r = chat.upload(con, ac, me, int(q.get("room") or 0), fname, raw, self.headers.get("Content-Type"), link, urllib.parse.unquote(q.get("text", "")))
                self._audit("chat fayl", p, fname); return self.send_json(r)
            body = self.body_json()
            if p == "/api/chat/send": return self.send_json(chat.send(con, ac, me, body))
            if p == "/api/chat/room":
                r = chat.create_room(con, ac, me, body)
                if not r.get("existing"): self._audit("chat xona", p, f"{body.get('kind')} · {body.get('name') or body.get('inn') or body.get('user_id')}")
                return self.send_json(r)
            if p == "/api/chat/room/archive": return self.send_json(chat.archive_room(con, me, int(body["id"]), bool(body.get("on", True))))
            if p == "/api/chat/room/topic": return self.send_json(chat.set_topic(con, me, int(body["id"]), body.get("topic", "")))
            if p == "/api/chat/read": return self.send_json(chat.mark_read(con, me, int(body["room"]), int(body.get("last_id") or 0)))
            if p == "/api/chat/edit": return self.send_json(chat.edit(con, ac, me, body))
            if p == "/api/chat/delete": return self.send_json(chat.delete(con, me, int(body["id"])))
            if p == "/api/chat/pin": return self.send_json(chat.pin(con, me, int(body["id"]), bool(body.get("on", True))))
            if p == "/api/chat/file/link": return self.send_json(chat.link_file(con, ac, me, body))
            if p == "/api/chat/links": return self.send_json(chat.set_links(con, ac, me, body))
            if p == "/api/chat/room/members": return self.send_json(chat.room_members(con, ac, me, body))
            return self.send_json({"error": "topilmadi"}, 404)
        finally: con.close(); ac.close()

    # ---- Хатлар (xatlar reyestri va xotirasi) — o'qish hammaga, yozish: superadmin / operator
    def xat_get(self, p: str, q: dict):
        con = xatlar.connect()
        try:
            if p == "/api/xatlar/list": return self.send_json(xatlar.list_letters(con, q))
            if p == "/api/xatlar/facets": return self.send_json(xatlar.facets(con))
            if p == "/api/xatlar/get": return self.send_json(xatlar.get_letter(con, int(q.get("id") or 0)))
            if p == "/api/xatlar/company": return self.send_json(xatlar.company_letters(con, (q.get("inn") or "").strip()))
            if p == "/api/xatlar/count": return self.send_json({"n": xatlar.company_count(con, (q.get("inn") or "").strip())})
            if p == "/api/xatlar/lookup": return self.send_json(xatlar.lookup(q.get("q", "")))
            if p == "/api/xatlar/stats": return self.send_json(xatlar.stats(con))
            if p == "/api/xatlar/file":
                path, name = xatlar.file_path(con, int(q.get("id") or 0))
                self._code = 200
                if q.get("dl"):
                    self._audit("xat faylini yukladi", p, name)
                    return legacy.Handler.send_file(self, path, download_name=name)
                return legacy.Handler.send_file(self, path, inline_name=name)
            return self.send_json({"error": "topilmadi"}, 404)
        finally: con.close()

    def xat_post(self, p: str):
        if self.user["role"] not in auth.WRITE_ROLES:
            self.drain_body()
            self._audit("rad etildi", p, f"xatlar — {self.user['role_name']} roliga ruxsat yo'q", ok=False)
            return self.send_json({"error": f"«{self.user['role_name']}» roli xatlarni o'zgartira olmaydi — faqat ko'rish"}, 403)
        con = xatlar.connect()
        try:
            if p == "/api/xatlar/upload":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > xatlar.MAX_FILE: self.drain_body(); raise ValueError("Fayl bo'sh yoki juda katta (80 MB gacha)")
                raw = self.rfile.read(n)
                fname = urllib.parse.unquote(self.headers.get("X-Filename") or "fayl")
                r = xatlar.upload(raw, fname, self.user)
                self._audit("xat fayli yuklandi", p, fname); return self.send_json(r)
            body = self.body_json()
            if p == "/api/xatlar/update":
                r = xatlar.update_letter(con, int(body.get("id") or 0), body, self.user)
                what = "tasdiqladi" if body.get("review") else ("arxiv" if "hidden" in body and len(body) <= 3 else "tahrirladi")
                self._audit(f"xat {what}", p, f"#{r['id']} {(r.get('title') or '')[:80]}"); return self.send_json(r)
            if p == "/api/xatlar/create":
                r = xatlar.create(con, body, self.user)
                self._audit("xat qo'shdi", p, f"#{r['id']} {(r.get('title') or '')[:80]}"); return self.send_json(r)
            return self.send_json({"error": "topilmadi"}, 404)
        finally: con.close()

# ------------------------------------------------------------ «Bugun» panel data
def today_panel(con, user: dict) -> dict:
    st = {}
    try:
        from app import report
        st["last_date"] = report.last_data_date(con); st["opening_date"] = report.opening_date(con)
    except Exception: st["last_date"] = None
    today = dt.date.today().isoformat()
    st["today"] = today
    st["gtd_today"] = bool(st["last_date"] and st["last_date"] >= today)
    st["open_issues"] = [dict(r) for r in con.execute("""SELECT i.id, i.title, i.kind, i.status, i.due_date, i.responsible, c.name AS company, c.inn
                                                         FROM issues i LEFT JOIN companies c ON c.inn=i.inn
                                                         WHERE i.status='open' ORDER BY coalesce(i.due_date,'9') LIMIT 12""")] if _has(con, "issues", "title") else []
    st["issues_total"] = con.execute("SELECT count(*) FROM issues WHERE status='open'").fetchone()[0] if _has(con, "issues", "title") else 0
    st["issues_overdue"] = con.execute("SELECT count(*) FROM issues WHERE status='open' AND due_date<?", (today,)).fetchone()[0] if _has(con, "issues", "due_date") else 0
    ac = auth.connect()
    try:
        st["my_audit"] = [dict(r) for r in ac.execute("SELECT ts, action, detail, ok FROM user_audit WHERE user_id=? ORDER BY id DESC LIMIT 8", (user["id"],))]
        st["online"] = [{k: v for k, v in o.items() if k not in ("ip", "host")} for o in auth.online(ac)]
    finally: ac.close()
    st["uploads_week"] = [dict(r) for r in con.execute("SELECT report_date, count(*) AS n FROM gtd_rows WHERE report_date>=? GROUP BY report_date ORDER BY report_date",
                                                        ((dt.date.today() - dt.timedelta(days=6)).isoformat(),))] if _has(con, "gtd_rows", "report_date") else []
    return st

def _has(con, table: str, col: str) -> bool:
    try: return col in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    except Exception: return False

def audit_xlsx(rows: list[dict], out: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "Audit"
    ws.append(["Vaqt", "Xodim", "IP", "Harakat", "Manzil", "Tafsilot", "Natija"])
    for c in ws[1]: c.font = Font(bold=True)
    def safe(v):
        v = "" if v is None else str(v)
        return ("'" + v) if v[:1] in ("=", "+", "-", "@") else v
    for r in rows: ws.append([r["ts"].replace("T", " "), safe(r["login"]), r["ip"], r["action"], r["path"], safe(r["detail"]), "✓" if r["ok"] else "✕"])
    for col, w in zip("ABCDEFG", (18, 14, 15, 22, 30, 60, 7)): ws.column_dimensions[col].width = w
    out.parent.mkdir(parents=True, exist_ok=True); wb.save(out); return out

# ------------------------------------------------------------ main
def bind(host: str, port: int):
    try: return legacy.ThreadingHTTPServer((host, port), Handler)
    except OSError: return None

def start(cfg: dict | None = None, quiet: bool = False) -> "legacy.ThreadingHTTPServer | None":
    """Bind, prepare the database and start serving in a daemon thread. Returns the server (None if the port is busy)."""
    global PORT, _first_admin
    cfg = cfg or load_config()
    legacy.set_data_dir(cfg["data_path"])
    PORT = int(cfg["port"]); host = cfg.get("host", "0.0.0.0")
    local = f"http://127.0.0.1:{PORT}/"
    say = (lambda *a: None) if quiet else print
    srv = bind(host, PORT)
    if srv is None:
        info = legacy.read_lock()
        if legacy.quit_running(PORT, info.get("token")):
            for _ in range(24):
                time.sleep(0.25); srv = bind(host, PORT)
                if srv: break
        if srv is None:
            say("=" * 70); say(f"PORT {PORT} BAND — eski sayt yoki AppWin ishlab turibdi. Uning oynasini yoping va qayta urinib ko'ring."); say("=" * 70)
            return None
        say("Eski nusxa yopildi, AppWin ishga tushdi.")
    if not db.DB_PATH.exists():
        seed = legacy.ROOT / "seed" / "export.db"
        if seed.exists(): shutil.copy2(seed, db.DB_PATH); say("Boshlang'ich baza nusxalandi:", db.DB_PATH)
    con = db.connect()
    if not db.integrity_ok(con): say("DIQQAT: baza butunlik tekshiruvidan o'tmadi!")
    con.close()
    ac = auth.connect()
    try: _first_admin = auth.init(ac)
    finally: ac.close()
    if _first_admin:
        note = db.BASE / "ADMIN_PAROL.txt"
        note.write_text(f"AppWin superadmin\nlogin: {_first_admin['login']}\nparol: {_first_admin['password']}\n(birinchi kirishda o'zgartiriladi; keyin bu faylni o'chiring)\n", encoding="utf-8")
        say("=" * 70); say(f"BIRINCHI KIRISH — superadmin: login «{_first_admin['login']}», parol «{_first_admin['password']}»"); say(f"(saqlandi: {note})"); say("=" * 70)
    try: chat.init()
    except Exception as e: say("chat init xato:", e)
    try: xatlar.init()
    except Exception as e: say("xatlar init xato:", e)
    legacy.acquire_lock()
    threading.Thread(target=legacy.heartbeat, daemon=True).start()
    today = dt.date.today().isoformat()
    if not (db.BACKUP_DIR.exists() and any(today in f.name for f in db.BACKUP_DIR.glob("export_*daily*.db"))):
        db.backup("daily")
    say(f"AppWin {__version__} ishlayapti.\n  Bu kompyuterda: {local}\n  Ofis tarmog'ida: http://{lan_ip()}:{PORT}/\n  Baza: {db.DB_PATH}")
    if legacy.STATE["readonly"]: say(f"DIQQAT: baza {legacy.STATE['lock_owner'].get('host')} kompyuterida ochiq — faqat ko'rish rejimi.")
    threading.Thread(target=srv.serve_forever, daemon=True, name="appwin-http").start()
    return srv

def stop(srv) -> None:
    try:
        with legacy.WRITE_LOCK:                    # let a running upload / import finish first
            srv.shutdown(); srv.server_close()
    except Exception: pass
    legacy.release_lock()

def main():
    cfg = load_config()
    srv = start(cfg)
    if srv is None: return
    print("To'xtatish: bu oynani yoping (yoki Ctrl+C).")
    if cfg.get("open_browser", True): threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/")).start()
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt: pass
    finally: stop(srv)

if __name__ == "__main__":
    main()
