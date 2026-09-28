"""Каталог — Buxoro eksportyorlari mahsulot vitrinasi (Jafar, 26.09.2026).

Maqsad: korxonalar mahsulotlarini rasm, narx va ma'lumotlari bilan bir joyda yig'ish; elchixonalar orqali xorijiy
xaridorlarga havola (sayt) sifatida taqdim etish. Marketingning yuragi — shuning uchun hamma narsa korxona INN'iga
bog'langan (ma'lumot daraxti qoidasi): catalog_companies (inn) <- catalog_products <- catalog_media.

- 3 til: uz (lotin), ru, en — matnlar `i18n` JSON ustunida: {"uz": {...}, "ru": {...}, "en": {...}}.
- Shablon: bojxona bazasi (items) + kunlik GTD dan korxona eksport qilgan har bir TN VED kodi — «template» holatidagi
  mahsulot; xodim faqat rasm, narx va tavsifni to'ldiradi. Kategoriya HS-10 lug'atidan (hs_codes.tovar1/tovar2).
- Narx doim ochiq ko'rinadi (Jafar qarori); muddati o'tgan narx «indicative» deb belgilanadi.
- Xaridor korxona bilan to'g'ridan-to'g'ri emas, boshqarma orqali bog'lanadi: saytdagi so'rov -> catalog_inquiries.
- Sayt: app/static/site (bitta kod) — lokal /catalog/ da ko'rinadi va «Сайт пакети» bilan statik zip bo'lib chiqadi.
- Rasmlar brauzerda kichraytiriladi (Pillow yo'q): asosiy ≤1600px + eskiz ≤560px, data\\catalog\\<INN>\\ ichida.
"""
from __future__ import annotations
import json, re, base64, shutil, zipfile, datetime as dt, io
from pathlib import Path
from . import db, smart

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "static" / "site"
FONTS = ROOT / "static" / "fonts"
LANGS = ("uz", "ru", "en")
P_FIELDS = ("name", "desc", "specs", "pack", "capacity", "lead")
C_FIELDS = ("name", "tagline", "about", "address", "capacity")
C_STATUS = ("draft", "published", "hidden")
P_STATUS = ("template", "draft", "published", "hidden")
Q_STATUS = ("new", "sent", "talks", "deal", "lost")
MEDIA_KINDS = ("photo", "logo", "cover", "doc")
TABLES = ("catalog_companies", "catalog_products", "catalog_media", "catalog_inquiries")

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_companies (      -- витринадаги корхона (INN илдизи)
  inn TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'draft', slug TEXT UNIQUE,
  i18n TEXT,                                        -- {"uz":{name,tagline,about,address,capacity},"ru":{…},"en":{…}}
  founded INTEGER, employees INTEGER, website TEXT, video TEXT,
  logo INTEGER, cover INTEGER,                      -- catalog_media.id
  incoterms TEXT, payment TEXT, markets TEXT,        -- JSON: ["FCA","FOB"], ["prepay"], ["KZ","AF"]
  show_markets INTEGER NOT NULL DEFAULT 1,          -- божхона маълумотидан экспорт географиясини кўрсатиш
  featured INTEGER NOT NULL DEFAULT 0, position REAL NOT NULL DEFAULT 0,
  note TEXT,                                        -- ички изоҳ (манба, эслатма) — сайтга чиқмайди
  created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT, published_at TEXT
);
CREATE TABLE IF NOT EXISTS catalog_products (
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
  hs10 TEXT, sku TEXT,
  i18n TEXT,                                        -- {"uz":{name,desc,specs,pack,capacity,lead},…}
  price REAL, price_to REAL, currency TEXT NOT NULL DEFAULT 'USD', unit TEXT, incoterm TEXT,
  moq REAL, moq_unit TEXT, price_date TEXT, price_valid TEXT,
  featured INTEGER NOT NULL DEFAULT 0, position REAL NOT NULL DEFAULT 0,
  source TEXT,                                      -- gtd (шаблон) | manual | seed
  created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_catalog_products_inn ON catalog_products(inn);
CREATE TABLE IF NOT EXISTS catalog_media (          -- расмлар ва ҳужжатлар; файллар data\\catalog\\<INN>\\
  id INTEGER PRIMARY KEY AUTOINCREMENT, inn TEXT NOT NULL, product_id INTEGER,
  kind TEXT NOT NULL DEFAULT 'photo',               -- photo | logo | cover | doc
  doc_type TEXT, title TEXT, filename TEXT, stored TEXT NOT NULL DEFAULT '', thumb TEXT, mime TEXT,
  size INTEGER, w INTEGER, h INTEGER, valid_until TEXT, is_public INTEGER NOT NULL DEFAULT 1,
  position REAL NOT NULL DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')), deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_catalog_media_inn ON catalog_media(inn, product_id);
CREATE TABLE IF NOT EXISTS catalog_inquiries (      -- хорижий харидор сўровлари (элчихона, кўргазма, сайт …)
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, channel TEXT, source TEXT, country TEXT,
  buyer TEXT, contact TEXT, email TEXT, phone TEXT, inn TEXT, product_ids TEXT, volume TEXT, message TEXT,
  status TEXT NOT NULL DEFAULT 'new', amount REAL, next_step TEXT, due TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now','localtime')), updated_at TEXT, closed_at TEXT
);
"""

# божхона номлари -> ISO (geo.ISO тўлдирувчиси)
ISO_EXTRA = {"Гонконг": "HK", "Перу": "PE", "Бирлашган Қироллик": "GB", "Испания": "ES", "Италия": "IT"}

_I18N = None
def i18n() -> dict:
    global _I18N
    if _I18N is None:
        _I18N = json.loads((ROOT / "templates" / "catalog_i18n.json").read_text(encoding="utf-8"))
    return _I18N

def ensure(con):
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(catalog_products)")}
    if "cat1" not in cols:   # кategoriya qo'lda: HS lug'ati paxta sumkani «teri buyumlari»ga qo'yadi — xaridor uchun «To'qimachilik»
        con.execute("ALTER TABLE catalog_products ADD COLUMN cat1 TEXT"); con.execute("ALTER TABLE catalog_products ADD COLUMN cat2 TEXT")

def store() -> Path:
    p = db.BASE / "catalog"; p.mkdir(parents=True, exist_ok=True); return p

def now() -> str: return dt.datetime.now().isoformat(timespec="seconds")
def today() -> str: return dt.date.today().isoformat()
def jl(v, default=None):
    if v in (None, ""): return default
    try: return json.loads(v)
    except Exception: return default
def jd(v) -> str: return json.dumps(v, ensure_ascii=False)
def inn_str(v) -> str:
    s = re.sub(r"\D", "", str(v or ""))
    if not s: raise ValueError("ИНН кўрсатилмаган")
    return s

# ------------------------------------------------------------------ names, slugs, categories
_CYR = {**smart._CYR, "ў": "oʻ", "ғ": "gʻ", "ъ": "ʼ", "е": "e", "ц": "ts", "х": "x"}
def translit(s: str) -> str:
    """Ўзбек кирилл -> лотин (заҳира ном учун; асосий таржималар catalog_i18n.json да)."""
    out, prev = [], " "
    for ch in str(s or ""):
        lo = ch.lower()
        t = "ye" if lo == "е" and not prev.isalpha() else _CYR.get(lo, ch)
        if ch.isupper() and t: t = t[0].upper() + t[1:]
        out.append(t); prev = ch
    return "".join(out)

LEGAL = {  # tail in full_name -> (en, ru, uz)
    "MCHJ": ("LLC", "ООО", "MChJ"), "МЧЖ": ("LLC", "ООО", "MChJ"), "XK": ("PE", "ЧП", "XK"), "ХК": ("PE", "ЧП", "XK"),
    "AJ": ("JSC", "АО", "AJ"), "АЖ": ("JSC", "АО", "AJ"), "QK": ("Farm", "ФХ", "QK"), "FX": ("Farm", "ФХ", "FX"),
    "XAJ": ("PJSC", "ЧАО", "XAJ"), "QMJ": ("ALC", "ОДО", "QMJ"), "OK": ("Family enterprise", "СП", "OK"),
}
def split_legal(full_name: str, name: str) -> tuple[str, tuple | None]:
    src = (full_name or name or "").strip()
    m = re.search(r'[«"“]\s*(.+?)\s*[»"”]', src)
    brand = m.group(1) if m else re.sub(r'^(ООО|ИП|ЧП|АО|OOO|MCHJ|XK)\s+', "", src).strip(' ",')
    brand = re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", brand)).replace("`", "ʻ").replace("'", "ʻ").strip()
    tail = re.sub(r'.*[»"”]', "", src).strip(" ,.").upper() if m else ""
    return brand, LEGAL.get(tail)

def default_names(full_name: str, name: str) -> dict:
    brand, lg = split_legal(full_name, name)
    if not lg: return {"en": brand, "ru": brand, "uz": brand}
    return {"en": f"{brand} {lg[0]}", "ru": f"{lg[1]} «{brand}»", "uz": f"«{brand}» {lg[2]}"}

def slugify(s: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", translit(str(s or "")).lower().replace("ʻ", "").replace("ʼ", "")).strip("-")
    return base[:60] or "company"

def unique_slug(con, s: str, inn: str) -> str:
    base = slugify(s); cand = base; i = 2
    while con.execute("SELECT 1 FROM catalog_companies WHERE slug=? AND inn<>?", (cand, inn)).fetchone():
        cand = f"{base}-{i}"; i += 1
    return cand

_HS_CACHE: dict = {}
def hs_cat(con, hs: str | None) -> dict:
    """HS-10 -> {cat1, cat2, sprav2} (lug'atdan; aniq kod bo'lmasa — shu 6/4 xonali boshdagi eng ko'p guruh)."""
    hs = re.sub(r"\D", "", str(hs or ""))
    if not hs: return {}
    if hs in _HS_CACHE: return _HS_CACHE[hs]
    r = con.execute("SELECT tovar1, tovar2, sprav2 FROM hs_codes WHERE hs10=?", (hs,)).fetchone()
    if not r:
        for n in (8, 6, 4):
            if len(hs) < n: continue
            r = con.execute("SELECT tovar1, tovar2, sprav2, count(*) c FROM hs_codes WHERE hs10 LIKE ? GROUP BY 1,2 ORDER BY c DESC LIMIT 1", (hs[:n] + "%",)).fetchone()
            if r: break
    res = {"cat1": r["tovar1"], "cat2": r["tovar2"], "sprav2": r["sprav2"]} if r else {}
    _HS_CACHE[hs] = res
    return res

def iso_of(name_uz: str) -> str | None:
    from . import geo
    n = (name_uz or "").strip()
    return geo.ISO.get(n) or ISO_EXTRA.get(n)

def clean_gtd(desc: str) -> str:
    """GTD «Наименование товара» -> qisqa tavsif: «1, Хлопковое масло …, Производитель: …» -> «Хлопковое масло …»."""
    s = str(desc or "").split("\n")[0]
    s = re.sub(r"^\s*\d+\s*[,)]\s*", "", s)
    s = re.split(r",?\s*(Производитель|Изготовитель|производитель)\b|\s-\s*вес\b|\s*- вес:", s)[0]
    s = re.sub(r",\s*\d[\d\s]*\s*(шт|мест|кг|пар)\.?\s*$", "", s.strip(" ,;"))
    return s[:220].strip(" ,;")

# ------------------------------------------------------------------ customs (INN tree) summary
def customs(con, inn: str) -> dict:
    """Bojxona bazasi (items) + undan keyingi GTD: yillar, davlatlar, TN VED kodlari (shablon uchun)."""
    from . import companies as C
    rows = con.execute("""SELECT i.year y, i.hs10 hs, d.country c, sum(i.value) v, sum(i.netto) t FROM items i JOIN declarations d USING(decl_id)
                          WHERE i.inn=? AND i.regime='ЭК' GROUP BY 1,2,3""", (inn,)).fetchall()
    g = con.execute("""SELECT substr(report_date,1,4) y, tnved hs, country c, sum(stat_usd) v, sum(netto) t, max(product) p FROM gtd_rows
                       WHERE inn=? AND voided=0 AND kind<>'not_bukhara' AND dedup_key NOT IN (SELECT key FROM items WHERE inn=?) GROUP BY 1,2,3""", (inn, inn)).fetchall()
    desc = {}
    for r in con.execute("SELECT tnved, product, count(*) n FROM gtd_rows WHERE inn=? AND voided=0 GROUP BY 1,2 ORDER BY n DESC", (inn,)):
        if r["tnved"] and r["tnved"] not in desc and r["product"]: desc[r["tnved"]] = clean_gtd(r["product"])
    years, countries, hs = {}, {}, {}
    for r in [*rows, *g]:
        y = int(r["y"]); v = float(r["v"] or 0); t = float(r["t"] or 0)
        c = C.country_uz(r["c"]) if r["c"] else "—"
        years[y] = years.get(y, 0) + v
        cc = countries.setdefault(c, {"name": c, "iso": iso_of(c), "value": 0.0, "years": set()})
        cc["value"] += v; cc["years"].add(y)
        code = re.sub(r"\D", "", str(r["hs"] or ""))
        if not code: continue
        h = hs.setdefault(code, {"hs10": code, "value": 0.0, "netto": 0.0, "years": {}, "countries": set()})
        h["value"] += v; h["netto"] += t; h["years"][y] = h["years"].get(y, 0) + v; h["countries"].add(c)
    out_hs = []
    for code, h in hs.items():
        cat = hs_cat(con, code)
        out_hs.append({"hs10": code, "value": round(h["value"], 1), "netto": round(h["netto"], 1),
                       "years": {k: round(v, 1) for k, v in sorted(h["years"].items())}, "countries": sorted(h["countries"]),
                       "cat1": cat.get("cat1"), "cat2": cat.get("cat2"), "sprav2": cat.get("sprav2"), "gtd_desc": desc.get(code)})
    out_hs.sort(key=lambda x: -x["value"])
    cl = sorted(({**c, "value": round(c["value"], 1), "years": sorted(c["years"])} for c in countries.values() if c["name"] != "—"), key=lambda x: -x["value"])
    return {"years": {k: round(v, 1) for k, v in sorted(years.items())}, "countries": cl, "hs": out_hs}

# ------------------------------------------------------------------ helpers: rows -> dicts
def _pick(d: dict | None, fields) -> dict:
    d = d or {}
    return {l: {f: str((d.get(l) or {}).get(f) or "").strip() for f in fields} for l in LANGS}

def _txt(d: dict, lang: str, f: str) -> str:
    return ((d or {}).get(lang) or {}).get(f) or ""

def media_row(r) -> dict:
    x = dict(r); ext = Path(x["stored"] or "").suffix
    x["src"] = f"/catalog/media/{x['id']}{ext}" if x["kind"] != "doc" else f"/catalog/docs/{x['id']}{ext}"
    x["thumb_src"] = f"/catalog/media/{x['id']}_t.jpg" if x.get("thumb") else x["src"]
    return x

def _media(con, inn: str) -> list[dict]:
    return [media_row(r) for r in con.execute("SELECT * FROM catalog_media WHERE inn=? AND deleted=0 ORDER BY position, id", (inn,))]

def product_row(con, r, media: list | None = None) -> dict:
    x = dict(r); x["i18n"] = _pick(jl(x["i18n"], {}), P_FIELDS)
    cat = hs_cat(con, x["hs10"]); x["hs_cat1"], x["hs_cat2"] = cat.get("cat1"), cat.get("cat2")
    x["cat_manual"] = bool(x.get("cat1")); x["cat1"] = x.get("cat1") or cat.get("cat1"); x["cat2"] = x.get("cat2") or (cat.get("cat2") if not x["cat_manual"] else None)
    x["photos"] = [m for m in (media or []) if m["product_id"] == x["id"] and m["kind"] == "photo"]
    x["expired"] = bool(x.get("price_valid") and x["price_valid"] < today())
    return x

def company_names(con, inn: str) -> dict:
    r = con.execute("SELECT name, full_name, district_code, tarmoq FROM companies WHERE inn=?", (inn,)).fetchone()
    return dict(r) if r else {}

# ------------------------------------------------------------------ completeness
def score(c: dict, prods: list[dict], media: list[dict], has_contact: bool) -> tuple[int, list[str]]:
    t = c["i18n"]; pub = [p for p in prods if p["status"] == "published"]; live = [p for p in prods if p["status"] in ("published", "draft")]
    s = 0; warn = []
    if c.get("logo"): s += 10
    else: warn.append("logo")
    for lang, pts in (("en", 15), ("ru", 10), ("uz", 5)):
        if len(_txt(t, lang, "about")) >= 60: s += pts
        else: warn.append("about_" + lang)
    if c.get("cover") or any(m["kind"] == "photo" and not m["product_id"] for m in media): s += 10
    else: warn.append("gallery")
    if has_contact: s += 5
    else: warn.append("contact")
    if pub: s += 20
    else: warn.append("no_published")
    base = pub or live
    if base:
        ph = sum(1 for p in base if p["photos"]) / len(base); pr = sum(1 for p in base if p["price"]) / len(base)
        s += round(15 * ph) + round(10 * pr)
        if ph < 1: warn.append("photos")
        if pr < 1: warn.append("prices")
    if any(p["expired"] for p in base): warn.append("price_expired")
    if any(m["kind"] == "doc" and m["valid_until"] and m["valid_until"] < today() for m in media): warn.append("doc_expired")
    if any(p["status"] == "template" for p in prods): warn.append("templates")
    return min(100, s), warn

# ------------------------------------------------------------------ admin: list / detail
def overview(con, q: dict | None = None) -> dict:
    q = q or {}
    comps = [dict(r) for r in con.execute("""SELECT cc.*, c.name AS reg_name, c.full_name, c.district_code, c.tarmoq FROM catalog_companies cc
                                              LEFT JOIN companies c USING(inn) ORDER BY cc.featured DESC, cc.position, cc.updated_at DESC""")]
    prods = {}
    allmedia = {}
    for r in con.execute("SELECT * FROM catalog_media WHERE deleted=0 ORDER BY position, id"): allmedia.setdefault(r["inn"], []).append(media_row(r))
    for r in con.execute("SELECT * FROM catalog_products ORDER BY position, id"):
        prods.setdefault(r["inn"], []).append(product_row(con, r, allmedia.get(r["inn"])))
    contacts = {r[0] for r in con.execute("SELECT inn FROM company_contacts WHERE coalesce(phone,'')<>'' OR coalesce(phones,'') NOT IN ('','[]')")}
    out = []
    kpi = {"companies": 0, "published": 0, "draft": 0, "products": 0, "p_published": 0, "templates": 0, "no_photo": 0, "no_price": 0,
           "expired": 0, "doc_expired": 0, "inq_new": 0, "inq_open": 0}
    for c in comps:
        c["i18n"] = _pick(jl(c["i18n"], {}), C_FIELDS)
        ps = prods.get(c["inn"], []); md = allmedia.get(c["inn"], [])
        sc, warn = score(c, ps, md, c["inn"] in contacts)
        cats = sorted({p["cat1"] for p in ps if p["cat1"] and p["status"] in ("published", "draft")} or {p["cat1"] for p in ps if p["cat1"] and p["status"] == "template"})
        logo = next((m for m in md if m["id"] == c["logo"]), None)
        row = {"inn": c["inn"], "status": c["status"], "slug": c["slug"], "name": _txt(c["i18n"], "uz", "name") or _txt(c["i18n"], "en", "name") or c["reg_name"],
               "reg_name": c["reg_name"], "district_code": c["district_code"], "cats": cats, "featured": c["featured"],
               "logo": logo["thumb_src"] if logo else None, "updated_at": c["updated_at"] or c["created_at"],
               "n": len(ps), "n_pub": sum(1 for p in ps if p["status"] == "published"), "n_tpl": sum(1 for p in ps if p["status"] == "template"),
               "n_photo": sum(1 for p in ps if p["photos"] and p["status"] != "template"), "n_price": sum(1 for p in ps if p["price"] and p["status"] != "template"),
               "score": sc, "warn": warn}
        out.append(row)
        kpi["companies"] += 1; kpi["published" if c["status"] == "published" else "draft"] += c["status"] != "hidden"
        kpi["products"] += sum(1 for p in ps if p["status"] != "template"); kpi["p_published"] += row["n_pub"]; kpi["templates"] += row["n_tpl"]
        kpi["no_photo"] += sum(1 for p in ps if p["status"] in ("draft", "published") and not p["photos"])
        kpi["no_price"] += sum(1 for p in ps if p["status"] in ("draft", "published") and not p["price"])
        kpi["expired"] += sum(1 for p in ps if p["status"] in ("draft", "published") and p["expired"])
        kpi["doc_expired"] += "doc_expired" in warn
    for r in con.execute("SELECT status, count(*) n FROM catalog_inquiries GROUP BY 1"):
        if r["status"] == "new": kpi["inq_new"] = r["n"]
        if r["status"] in ("new", "sent", "talks"): kpi["inq_open"] += r["n"]
    tree = {}
    for r in con.execute("SELECT DISTINCT tovar1, tovar2 FROM hs_codes WHERE tovar1 IS NOT NULL ORDER BY 1, 2"): tree.setdefault(r[0], []).append(r[1])
    return {"companies": out, "kpi": kpi, "settings": site_settings(con), "seed": seed_status(con), "i18n": i18n(), "cat_tree": tree,
            "countries": _iso_names()}

def detail(con, inn: str) -> dict:
    inn = inn_str(inn)
    r = con.execute("SELECT * FROM catalog_companies WHERE inn=?", (inn,)).fetchone()
    if not r: raise ValueError("Корхона каталогда йўқ")
    c = dict(r); c["i18n"] = _pick(jl(c["i18n"], {}), C_FIELDS)
    for k in ("incoterms", "payment", "markets"): c[k] = jl(c[k], [])
    media = _media(con, inn)
    prods = [product_row(con, p, media) for p in con.execute("SELECT * FROM catalog_products WHERE inn=? ORDER BY position, id", (inn,))]
    reg = company_names(con, inn)
    cont = con.execute("SELECT * FROM company_contacts WHERE inn=?", (inn,)).fetchone()
    persons = [dict(p) for p in con.execute("SELECT name, role, phones FROM company_persons WHERE inn=? ORDER BY position, id", (inn,))]
    cust = customs(con, inn)
    have = {p["hs10"] for p in prods if p["hs10"]}
    tpl = [h for h in cust["hs"] if h["hs10"] not in have]
    has_contact = bool(cont and ((cont["phone"] or "").strip() or (cont["phones"] or "") not in ("", "[]")))
    sc, warn = score(c, prods, media, has_contact)
    return {"company": c, "products": prods, "media": [m for m in media if not m["product_id"]], "reg": reg,
            "contacts": dict(cont) if cont else None, "persons": persons, "customs": cust, "templates": tpl, "score": sc, "warn": warn,
            "default_names": default_names(reg.get("full_name"), reg.get("name"))}

# ------------------------------------------------------------------ admin: create / save
def _tpl_i18n(con, h: dict) -> dict:
    cat = i18n()["cat2"].get(h.get("cat2") or "", {})
    nm = {l: cat.get(l, "") for l in LANGS}
    if not nm["uz"] and h.get("sprav2"): nm["uz"] = translit(h["sprav2"])
    d = {l: {"name": nm[l] or nm["uz"] or nm["ru"] or nm["en"]} for l in LANGS}
    if h.get("gtd_desc"): d["ru"]["desc"] = h["gtd_desc"]
    return d

def add_products_from_templates(con, inn: str, hs_list: list[str] | None = None, status: str = "template") -> int:
    cust = customs(con, inn)
    have = {r[0] for r in con.execute("SELECT hs10 FROM catalog_products WHERE inn=? AND hs10 IS NOT NULL", (inn,))}
    pos = (con.execute("SELECT max(position) FROM catalog_products WHERE inn=?", (inn,)).fetchone()[0] or 0)
    n = 0
    for h in cust["hs"]:
        if h["hs10"] in have or (hs_list and h["hs10"] not in hs_list): continue
        pos += 1; n += 1
        con.execute("INSERT INTO catalog_products(inn, status, hs10, i18n, source, position, updated_at) VALUES(?,?,?,?,?,?,?)",
                    (inn, status, h["hs10"], jd(_tpl_i18n(con, h)), "gtd", pos, now()))
    return n

def add_company(con, inn: str, templates: bool = True) -> dict:
    inn = inn_str(inn)
    reg = company_names(con, inn)
    if not reg: raise ValueError("Бу ИНН реестрда йўқ (Korxonalar)")
    if con.execute("SELECT 1 FROM catalog_companies WHERE inn=?", (inn,)).fetchone(): return {"ok": True, "inn": inn, "exists": True}
    names = default_names(reg.get("full_name"), reg.get("name"))
    d = {l: {"name": names[l]} for l in LANGS}
    brand, _ = split_legal(reg.get("full_name"), reg.get("name"))
    with con:
        con.execute("INSERT INTO catalog_companies(inn, status, slug, i18n, updated_at) VALUES(?,?,?,?,?)", (inn, "draft", unique_slug(con, brand, inn), jd(d), now()))
        n = add_products_from_templates(con, inn) if templates else 0
        db.event(con, inn, "catalog", f"Каталогга қўшилди ({n} та ГТД шаблон)")
        db.log(con, "catalog_add", inn=inn, templates=n)
    return {"ok": True, "inn": inn, "templates": n}

def bulk_templates(con, body: dict) -> dict:
    """Барча экспортёрлар — каталогга қоралама + ГТД шаблонлари (фақат ҳали каталогда йўқлар)."""
    y1 = int(body.get("year_from") or (int(db.get_setting(con, "year") or dt.date.today().year) - 1)); mn = float(body.get("min_value") or 0)
    persons = bool(body.get("persons"))
    rows = con.execute("""SELECT i.inn, sum(i.value) v FROM items i JOIN companies c USING(inn)
                          WHERE i.regime='ЭК' AND i.year>=? AND coalesce(c.bukhara,1)<>0 AND i.kind<>'bnpz' GROUP BY 1 HAVING v>=?""", (y1, mn)).fetchall()
    have = {r[0] for r in con.execute("SELECT inn FROM catalog_companies")}
    added = tpl = 0
    for r in rows:
        if r["inn"] in have or (not persons and len(r["inn"]) >= 14): continue
        res = add_company(con, r["inn"]); added += 1; tpl += res.get("templates", 0)
    return {"ok": True, "added": added, "templates": tpl, "candidates": len(rows)}

def _clean_i18n(d, fields) -> dict:
    return {l: {f: str(((d or {}).get(l) or {}).get(f) or "").strip() for f in fields if str(((d or {}).get(l) or {}).get(f) or "").strip()} for l in LANGS}

def _num(v):
    if v in (None, ""): return None
    try: return float(str(v).replace(" ", "").replace(",", "."))
    except ValueError: raise ValueError(f"Рақам нотўғри: {v}")

def _int(v):
    n = _num(v); return int(n) if n is not None else None

def _date(v):
    v = str(v or "").strip()
    if not v: return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v): raise ValueError(f"Сана нотўғри: {v}")
    return v

def save_company(con, b: dict) -> dict:
    inn = inn_str(b.get("inn"))
    old = con.execute("SELECT * FROM catalog_companies WHERE inn=?", (inn,)).fetchone()
    if not old: raise ValueError("Корхона каталогда йўқ")
    st = b.get("status") or old["status"]
    if st not in C_STATUS: raise ValueError("Ҳолат нотўғри")
    d = _clean_i18n(b.get("i18n"), C_FIELDS)
    if not any(d[l].get("name") for l in LANGS): raise ValueError("Корхона номи камида бир тилда бўлиши керак")
    slug = unique_slug(con, b.get("slug") or old["slug"] or d["en"].get("name") or d["uz"].get("name"), inn)
    lst = lambda k: jd([x for x in (b.get(k) or []) if x])
    with con:
        con.execute("""UPDATE catalog_companies SET status=?, slug=?, i18n=?, founded=?, employees=?, website=?, video=?, incoterms=?, payment=?, markets=?,
                       show_markets=?, featured=?, note=?, updated_at=?, published_at=CASE WHEN ?='published' AND published_at IS NULL THEN ? ELSE published_at END WHERE inn=?""",
                    (st, slug, jd(d), _int(b.get("founded")), _int(b.get("employees")), (b.get("website") or "").strip() or None, (b.get("video") or "").strip() or None,
                     lst("incoterms"), lst("payment"), lst("markets"), 1 if b.get("show_markets", True) else 0, 1 if b.get("featured") else 0,
                     (b.get("note") or "").strip() or None, now(), st, now(), inn))
        if st != old["status"]: db.event(con, inn, "catalog", f"Каталог ҳолати: {old['status']} → {st}")
    return {"ok": True, "slug": slug}

def set_company_status(con, inn: str, status: str) -> dict:
    if status not in C_STATUS: raise ValueError("Ҳолат нотўғри")
    inn = inn_str(inn)
    with con:
        con.execute("UPDATE catalog_companies SET status=?, updated_at=?, published_at=CASE WHEN ?='published' AND published_at IS NULL THEN ? ELSE published_at END WHERE inn=?",
                    (status, now(), status, now(), inn))
        db.event(con, inn, "catalog", f"Каталог ҳолати: {status}")
    return {"ok": True}

def delete_company(con, inn: str) -> dict:
    inn = inn_str(inn)
    with con:
        for m in con.execute("SELECT id FROM catalog_media WHERE inn=? AND deleted=0", (inn,)).fetchall(): _trash_media(con, m["id"])
        con.execute("DELETE FROM catalog_products WHERE inn=?", (inn,))
        con.execute("DELETE FROM catalog_companies WHERE inn=?", (inn,))
        db.event(con, inn, "catalog", "Каталогдан олиб ташланди"); db.log(con, "catalog_remove", inn=inn)
    return {"ok": True}

def save_product(con, b: dict) -> dict:
    inn = inn_str(b.get("inn"))
    if not con.execute("SELECT 1 FROM catalog_companies WHERE inn=?", (inn,)).fetchone(): raise ValueError("Аввал корхонани каталогга қўшинг")
    pid = _int(b.get("id"))
    st = b.get("status") or "draft"
    if st not in P_STATUS: raise ValueError("Ҳолат нотўғри")
    d = _clean_i18n(b.get("i18n"), P_FIELDS)
    if not any(d[l].get("name") for l in LANGS): raise ValueError("Маҳсулот номи камида бир тилда бўлиши керак")
    price, price_to = _num(b.get("price")), _num(b.get("price_to"))
    if price is not None and price < 0 or price_to is not None and price_to < 0: raise ValueError("Нарх манфий бўлмайди")
    if price is not None and price_to is not None and price_to < price: price, price_to = price_to, price
    hs = re.sub(r"\D", "", str(b.get("hs10") or "")) or None
    c1, c2 = (b.get("cat1") or None), (b.get("cat2") or None)
    if c1 and c1 not in i18n()["cat1"]: raise ValueError("Категория нотўғри")
    if c2 and (not c1 or c2 not in i18n()["cat2"]): c2 = None
    vals = (st, hs, (b.get("sku") or "").strip() or None, jd(d), price, price_to, (b.get("currency") or "USD").upper()[:3], b.get("unit") or None,
            b.get("incoterm") or None, _num(b.get("moq")), b.get("moq_unit") or None, _date(b.get("price_date")), _date(b.get("price_valid")),
            1 if b.get("featured") else 0, now(), c1, c2)
    with con:
        if pid:
            if not con.execute("SELECT 1 FROM catalog_products WHERE id=? AND inn=?", (pid, inn)).fetchone(): raise ValueError("Маҳсулот топилмади")
            con.execute("""UPDATE catalog_products SET status=?, hs10=?, sku=?, i18n=?, price=?, price_to=?, currency=?, unit=?, incoterm=?, moq=?, moq_unit=?,
                           price_date=?, price_valid=?, featured=?, updated_at=?, cat1=?, cat2=? WHERE id=?""", (*vals, pid))
        else:
            pos = (con.execute("SELECT max(position) FROM catalog_products WHERE inn=?", (inn,)).fetchone()[0] or 0) + 1
            cur = con.execute("""INSERT INTO catalog_products(status, hs10, sku, i18n, price, price_to, currency, unit, incoterm, moq, moq_unit, price_date, price_valid,
                                 featured, updated_at, cat1, cat2, inn, position, source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*vals, inn, pos, b.get("source") or "manual"))
            pid = cur.lastrowid
        con.execute("UPDATE catalog_companies SET updated_at=? WHERE inn=?", (now(), inn))
    return {"ok": True, "id": pid}

def delete_product(con, pid: int) -> dict:
    r = con.execute("SELECT inn FROM catalog_products WHERE id=?", (pid,)).fetchone()
    if not r: raise ValueError("Маҳсулот топилмади")
    with con:
        for m in con.execute("SELECT id FROM catalog_media WHERE product_id=? AND deleted=0", (pid,)).fetchall(): _trash_media(con, m["id"])
        con.execute("DELETE FROM catalog_products WHERE id=?", (pid,))
    return {"ok": True}

def reorder(con, b: dict) -> dict:
    """{"table": "products"|"media", "ids": [..]} — tartib (drag / ↑↓)."""
    t = {"products": "catalog_products", "media": "catalog_media", "companies": None}.get(b.get("table"))
    ids = b.get("ids") or []
    with con:
        if b.get("table") == "companies":
            for i, inn in enumerate(ids): con.execute("UPDATE catalog_companies SET position=? WHERE inn=?", (i, str(inn)))
        elif t:
            for i, x in enumerate(ids): con.execute(f"UPDATE {t} SET position=? WHERE id=?", (i, int(x)))
    return {"ok": True}

def bulk_products(con, b: dict) -> dict:
    """Бир нечта маҳсулот ҳолатини бирданига: {"ids": [...], "status": "published"} ёки {"inn":…, "all_templates": true, "status": "draft"}."""
    st = b.get("status")
    if st not in P_STATUS and st != "delete": raise ValueError("Ҳолат нотўғри")
    ids = [int(x) for x in (b.get("ids") or [])]
    if b.get("inn") and b.get("from_status"):
        ids = [r[0] for r in con.execute("SELECT id FROM catalog_products WHERE inn=? AND status=?", (inn_str(b["inn"]), b["from_status"]))]
    if st == "delete":
        for i in ids: delete_product(con, i)
    else:
        with con:
            for i in ids: con.execute("UPDATE catalog_products SET status=?, updated_at=? WHERE id=?", (st, now(), i))
    return {"ok": True, "n": len(ids)}

# ------------------------------------------------------------------ media
def _ext_of(raw: bytes) -> str:
    if raw[:3] == b"\xff\xd8\xff": return ".jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n": return ".png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP": return ".webp"
    raise ValueError("Фақат JPG, PNG ёки WEBP расм")

def _b64(s: str) -> bytes:
    s = str(s or "")
    if "," in s[:100]: s = s.split(",", 1)[1]
    return base64.b64decode(s)

def media_upload(con, b: dict) -> dict:
    """Brauzer kichraytirgan rasm: {inn, product_id?, kind, main (dataURL), thumb (dataURL), w, h, filename, title?}."""
    inn = inn_str(b.get("inn")); kind = b.get("kind") or "photo"
    if kind not in ("photo", "logo", "cover"): raise ValueError("Расм тури нотўғри")
    if not con.execute("SELECT 1 FROM catalog_companies WHERE inn=?", (inn,)).fetchone(): raise ValueError("Корхона каталогда йўқ")
    pid = _int(b.get("product_id"))
    if pid and not con.execute("SELECT 1 FROM catalog_products WHERE id=? AND inn=?", (pid, inn)).fetchone(): raise ValueError("Маҳсулот топилмади")
    raw = _b64(b.get("main")); ext = _ext_of(raw)
    if len(raw) > 8 * 1024 * 1024: raise ValueError("Расм жуда катта")
    th = _b64(b.get("thumb")) if b.get("thumb") else None
    if th is not None and _ext_of(th) != ".jpg": raise ValueError("Эскиз JPG бўлиши керак")
    d = store() / inn; d.mkdir(parents=True, exist_ok=True)
    with con:
        pos = (con.execute("SELECT max(position) FROM catalog_media WHERE inn=? AND coalesce(product_id,0)=?", (inn, pid or 0)).fetchone()[0] or 0) + 1
        cur = con.execute("INSERT INTO catalog_media(inn, product_id, kind, title, filename, mime, size, w, h, position) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (inn, pid, kind, (b.get("title") or "").strip() or None, (b.get("filename") or "")[:150], {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[ext],
                           len(raw), _int(b.get("w")), _int(b.get("h")), pos))
        mid = cur.lastrowid
        (d / f"{mid}{ext}").write_bytes(raw)
        if th: (d / f"{mid}_t.jpg").write_bytes(th)
        con.execute("UPDATE catalog_media SET stored=?, thumb=? WHERE id=?", (f"{inn}/{mid}{ext}", f"{inn}/{mid}_t.jpg" if th else None, mid))
        if kind in ("logo", "cover"):
            old = con.execute(f"SELECT {kind} FROM catalog_companies WHERE inn=?", (inn,)).fetchone()[0]
            con.execute(f"UPDATE catalog_companies SET {kind}=?, updated_at=? WHERE inn=?", (mid, now(), inn))
            if old: _trash_media(con, old)
        con.execute("UPDATE catalog_companies SET updated_at=? WHERE inn=?", (now(), inn))
    return {"ok": True, "id": mid}

def doc_upload(con, inn: str, filename: str, raw: bytes, title: str, doc_type: str, valid_until: str | None, product_id=None, is_public=True) -> dict:
    inn = inn_str(inn)
    if not con.execute("SELECT 1 FROM catalog_companies WHERE inn=?", (inn,)).fetchone(): raise ValueError("Корхона каталогда йўқ")
    if not raw: raise ValueError("Файл бўш")
    ext = Path(filename or "").suffix.lower()
    if ext not in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx", ".xls", ".xlsx"): raise ValueError("PDF, расм, Word ёки Excel файл")
    if doc_type not in i18n()["doc_types"]: doc_type = "other"
    d = store() / inn; d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(filename).name)[:150]
    with con:
        cur = con.execute("INSERT INTO catalog_media(inn, product_id, kind, doc_type, title, filename, size, valid_until, is_public) VALUES(?,?,?,?,?,?,?,?,?)",
                          (inn, _int(product_id), "doc", doc_type, (title or "").strip() or Path(safe).stem, safe, len(raw), _date(valid_until), 1 if is_public else 0))
        mid = cur.lastrowid; ext = ".jpg" if ext == ".jpeg" else ext
        (d / f"{mid}{ext}").write_bytes(raw)
        con.execute("UPDATE catalog_media SET stored=?, mime=? WHERE id=?", (f"{inn}/{mid}{ext}", ext, mid))
        con.execute("UPDATE catalog_companies SET updated_at=? WHERE inn=?", (now(), inn))
    return {"ok": True, "id": mid}

def media_update(con, b: dict) -> dict:
    mid = int(b["id"])
    r = con.execute("SELECT * FROM catalog_media WHERE id=? AND deleted=0", (mid,)).fetchone()
    if not r: raise ValueError("Файл топилмади")
    doc_type = b.get("doc_type", r["doc_type"])
    if r["kind"] == "doc" and doc_type not in i18n()["doc_types"]: doc_type = "other"
    with con:
        con.execute("UPDATE catalog_media SET title=?, doc_type=?, valid_until=?, is_public=? WHERE id=?",
                    ((b.get("title", r["title"]) or "").strip() or None, doc_type, _date(b.get("valid_until", r["valid_until"])), 1 if b.get("is_public", r["is_public"]) else 0, mid))
        if b.get("as_cover") and r["kind"] == "photo" and r["product_id"]:   # маҳсулот муқоваси — биринчи ўрин
            ids = [x[0] for x in con.execute("SELECT id FROM catalog_media WHERE product_id=? AND kind='photo' AND deleted=0 ORDER BY position, id", (r["product_id"],))]
            ids.remove(mid); ids.insert(0, mid)
            for i, x in enumerate(ids): con.execute("UPDATE catalog_media SET position=? WHERE id=?", (i, x))
    return {"ok": True}

def _trash_media(con, mid: int):
    r = con.execute("SELECT * FROM catalog_media WHERE id=?", (mid,)).fetchone()
    if not r: return
    tr = store() / "_olib_tashlangan"; tr.mkdir(exist_ok=True)
    for rel in (r["stored"], r["thumb"]):
        if rel and (store() / rel).exists(): shutil.move(str(store() / rel), str(tr / rel.replace("/", "__")))
    con.execute("UPDATE catalog_media SET deleted=1 WHERE id=?", (mid,))
    con.execute("UPDATE catalog_companies SET logo=CASE WHEN logo=? THEN NULL ELSE logo END, cover=CASE WHEN cover=? THEN NULL ELSE cover END WHERE inn=?", (mid, mid, r["inn"]))

def media_delete(con, mid: int) -> dict:
    with con: _trash_media(con, int(mid))
    return {"ok": True}

def media_path(con, name: str) -> tuple[Path, str] | None:
    """/catalog/media/12.jpg | 12_t.jpg  ·  /catalog/docs/12.pdf"""
    m = re.fullmatch(r"(\d+)(_t)?\.(jpg|png|webp|pdf|docx?|xlsx?)", name or "")
    if not m: return None
    r = con.execute("SELECT * FROM catalog_media WHERE id=? AND deleted=0", (int(m.group(1)),)).fetchone()
    if not r: return None
    rel = r["thumb"] if m.group(2) else r["stored"]
    if not rel: return None
    p = store() / rel
    return (p, r["filename"] or p.name) if p.exists() else None

# ------------------------------------------------------------------ site settings
DEFAULT_SITE = {
    "title": {"en": "Bukhara Export Catalog", "ru": "Экспортный каталог Бухарской области", "uz": "Buxoro viloyati eksport katalogi"},
    "org": {"en": "Department of Investments, Industry and Trade of Bukhara Region", "ru": "Управление инвестиций, промышленности и торговли Бухарской области",
            "uz": "Buxoro viloyati investitsiyalar, sanoat va savdo boshqarmasi"},
    "address": {"en": "Bukhara, Republic of Uzbekistan", "ru": "г. Бухара, Республика Узбекистан", "uz": "Buxoro shahri, Oʻzbekiston Respublikasi"},
    "email": "", "phone": "", "telegram": "", "whatsapp": "", "form_url": "", "site_url": "", "show_tin": True,
}
def site_settings(con) -> dict:
    s = jl(db.get_setting(con, "catalog_site"), {}) or {}
    out = json.loads(json.dumps(DEFAULT_SITE))
    for k, v in s.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict): out[k].update({l: v.get(l, out[k].get(l, "")) for l in LANGS})
        else: out[k] = v
    return out

def save_settings(con, b: dict) -> dict:
    cur = site_settings(con)
    for k in DEFAULT_SITE:
        if k not in b: continue
        v = b[k]
        if isinstance(DEFAULT_SITE[k], dict): cur[k] = {l: str((v or {}).get(l) or "").strip() for l in LANGS}
        elif isinstance(DEFAULT_SITE[k], bool): cur[k] = bool(v)
        else: cur[k] = str(v or "").strip()
    with con: db.set_setting(con, "catalog_site", jd(cur))
    return {"ok": True, "settings": cur}

# ------------------------------------------------------------------ public payload (site)
def public(con, admin: bool = False) -> dict:
    """Сайт маълумоти. admin=True — қоралама ҳам (витринани олдиндан кўриш), draft белгиси билан."""
    cst = ("published", "draft") if admin else ("published",)
    pst = ("published", "draft") if admin else ("published",)
    I = i18n()
    comps, prods, used1, used2, dists = [], [], set(), set(), set()
    media_by = {}
    for r in con.execute("SELECT * FROM catalog_media WHERE deleted=0 ORDER BY position, id"): media_by.setdefault(r["inn"], []).append(dict(r))
    def img(m):
        ext = Path(m["stored"]).suffix
        return {"src": f"media/{m['id']}{ext}", "thumb": f"media/{m['id']}_t.jpg" if m["thumb"] else f"media/{m['id']}{ext}", "w": m["w"], "h": m["h"], "title": m["title"] or ""}
    for c in con.execute(f"""SELECT cc.*, c.district_code, c.name AS reg_name, c.full_name FROM catalog_companies cc LEFT JOIN companies c USING(inn)
                             WHERE cc.status IN ({','.join('?' * len(cst))}) ORDER BY cc.featured DESC, cc.position, cc.published_at""", cst).fetchall():
        c = dict(c); t = _pick(jl(c["i18n"], {}), C_FIELDS); inn = c["inn"]
        ps = [dict(p) for p in con.execute(f"SELECT * FROM catalog_products WHERE inn=? AND status IN ({','.join('?' * len(pst))}) ORDER BY featured DESC, position, id", (inn, *pst))]
        if not ps: continue   # маҳсулотсиз корхона сайтда ҳам, олдиндан кўришда ҳам чиқмайди
        md = media_by.get(inn, [])
        byid = {m["id"]: m for m in md}
        gallery = [img(m) for m in md if m["kind"] == "photo" and not m["product_id"]]
        docs = [{"title": m["title"] or m["filename"], "type": m["doc_type"] or "other", "valid_until": m["valid_until"],
                 "src": f"docs/{m['id']}{Path(m['stored']).suffix}", "product": m["product_id"]}
                for m in md if m["kind"] == "doc" and m["is_public"] and not (m["valid_until"] and m["valid_until"] < today())]
        cust = customs(con, inn) if c["show_markets"] else {"countries": [], "years": {}}
        dists.add(c["district_code"])
        cats = set()
        for p in ps:
            ti = _pick(jl(p["i18n"], {}), P_FIELDS); cat = hs_cat(con, p["hs10"])
            if p.get("cat1"): cat = {"cat1": p["cat1"], "cat2": p.get("cat2")}
            if cat.get("cat1"): used1.add(cat["cat1"]); cats.add(cat["cat1"])
            if cat.get("cat2"): used2.add(cat["cat2"])
            photos = [img(m) for m in md if m["product_id"] == p["id"] and m["kind"] == "photo"]
            prods.append({"id": p["id"], "c": c["slug"], "hs": p["hs10"], "sku": p["sku"], "cat1": cat.get("cat1"), "cat2": cat.get("cat2"),
                          **{f: {l: ti[l][f] for l in LANGS} for f in P_FIELDS},
                          "price": p["price"], "price_to": p["price_to"], "cur": p["currency"], "unit": p["unit"], "inc": p["incoterm"],
                          "moq": p["moq"], "moq_unit": p["moq_unit"], "price_date": p["price_date"], "price_valid": p["price_valid"],
                          "expired": bool(p["price_valid"] and p["price_valid"] < today()), "img": photos, "featured": p["featured"],
                          "docs": [d["src"] for d in docs if d["product"] == p["id"]], "draft": p["status"] != "published", "updated": p["updated_at"]})
        comps.append({"id": c["slug"], "tin": inn if len(inn) == 9 else None, "inn": inn if admin else None, **{f: {l: t[l][f] for l in LANGS} for f in C_FIELDS},
                      "district": c["district_code"], "founded": c["founded"], "employees": c["employees"], "website": c["website"], "video": c["video"],
                      "logo": img(byid[c["logo"]]) if c["logo"] in byid else None, "cover": img(byid[c["cover"]]) if c["cover"] in byid else None,
                      "gallery": gallery, "docs": docs, "incoterms": jl(c["incoterms"], []), "payment": jl(c["payment"], []), "markets": jl(c["markets"], []),
                      "export": {"countries": [{"iso": x["iso"], "name": x["name"]} for x in cust["countries"]], "years": sorted(cust["years"])},
                      "cats": sorted(cats), "featured": c["featured"], "draft": c["status"] != "published", "n": len(ps)})
    s = site_settings(con)
    if not s.get("show_tin"):
        for c in comps: c["tin"] = None
    return {"v": 1, "generated": now(), "admin": admin, "site": s,
            "i18n": {"countries": _iso_names(),
                     "cat1": {k: v for k, v in I["cat1"].items() if k in used1}, "cat2": {k: v for k, v in I["cat2"].items() if k in used2},
                     "districts": {k: v for k, v in I["districts"].items() if k in dists}, "units": I["units"], "payment": I["payment"], "doc_types": I["doc_types"]},
            "companies": comps, "products": prods}

def _iso_names() -> dict:
    from . import geo
    out = {}
    for nm, iso in {**geo.ISO, **ISO_EXTRA}.items():
        out.setdefault(iso, nm.strip())
    return out

def data_js(con, admin=False) -> bytes:
    return ("window.CATALOG=" + json.dumps(public(con, admin), ensure_ascii=False, separators=(",", ":")) + ";").encode("utf-8")

def build_site(con) -> tuple[Path, dict]:
    """Статик сайт пакети: index.html + site.css/js + data.js + media/ + docs/ + fonts/ -> zip (истаган хостингга)."""
    d = public(con, False)
    if not d["products"]: raise ValueError("Каталогда эълон қилинган маҳсулот йўқ — аввал корхона ва маҳсулотларни «Эълон қилинган» ҳолатига ўтказинг")
    stamp = dt.date.today().isoformat()
    out = db.BASE / "exports" / f"Buxoro_eksport_katalogi_{stamp}.zip"; out.parent.mkdir(parents=True, exist_ok=True)
    need = set()
    for c in d["companies"]:
        for im in [c["logo"], c["cover"], *c["gallery"]]:
            if im: need.update({im["src"], im["thumb"]})
        need.update(x["src"] for x in c["docs"])
    for p in d["products"]:
        for im in p["img"]: need.update({im["src"], im["thumb"]})
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("index.html", "site.css", "site.js"): z.write(SITE / f, f)
        for f in FONTS.glob("*"): z.write(f, f"fonts/{f.name}")
        z.writestr("data.js", "window.CATALOG=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";")
        for rel in sorted(need):
            kind, name = rel.split("/", 1)
            p = media_path(con, name)
            if p: z.write(p[0], rel, compress_type=zipfile.ZIP_STORED); n += 1
        z.writestr("README.txt", "Buxoro viloyati eksport katalogi — statik sayt.\r\n"
                   "Ochish: index.html (internet shart emas). Hostingga (GitHub Pages, Netlify, istalgan server) papkani to'liq joylang.\r\n"
                   f"Tayyorlangan: {now()}. Korxona: {len(d['companies'])}, mahsulot: {len(d['products'])}.\r\n")
    with con: db.log(con, "catalog_site_build", file=out.name, companies=len(d["companies"]), products=len(d["products"]), files=n)
    return out, {"companies": len(d["companies"]), "products": len(d["products"]), "files": n}

# ------------------------------------------------------------------ inquiries (lids)
def inquiries(con, q: dict | None = None) -> dict:
    rows = [dict(r) for r in con.execute("""SELECT q.*, cc.i18n AS c_i18n, c.name AS reg_name FROM catalog_inquiries q
                                            LEFT JOIN catalog_companies cc ON cc.inn=q.inn LEFT JOIN companies c ON c.inn=q.inn ORDER BY q.at DESC, q.id DESC""")]
    pn = {r["id"]: _pick(jl(r["i18n"], {}), P_FIELDS) for r in con.execute("SELECT id, i18n FROM catalog_products")}
    for r in rows:
        ci = _pick(jl(r.pop("c_i18n"), {}), C_FIELDS)
        r["company"] = _txt(ci, "uz", "name") or _txt(ci, "en", "name") or r.pop("reg_name", None)
        r.pop("reg_name", None)
        r["product_ids"] = jl(r["product_ids"], [])
        r["products"] = [{"id": i, "name": _txt(pn[i], "uz", "name") or _txt(pn[i], "ru", "name") or _txt(pn[i], "en", "name")} for i in r["product_ids"] if i in pn]
    st = {s: 0 for s in Q_STATUS}
    for r in rows: st[r["status"]] = st.get(r["status"], 0) + 1
    return {"rows": rows, "status": st, "amount_deal": round(sum(r["amount"] or 0 for r in rows if r["status"] == "deal"), 1)}

def inquiry_save(con, b: dict) -> dict:
    iid = _int(b.get("id")); st = b.get("status") or "new"
    if st not in Q_STATUS: raise ValueError("Ҳолат нотўғри")
    if not (b.get("buyer") or b.get("contact") or b.get("email") or b.get("phone")): raise ValueError("Харидор ёки алоқа маълумоти керак")
    inn = re.sub(r"\D", "", str(b.get("inn") or "")) or None
    pids = [int(x) for x in (b.get("product_ids") or [])]
    f = lambda k: (str(b.get(k) or "")).strip() or None
    vals = (_date(b.get("at")) or today(), f("channel"), f("source"), f("country"), f("buyer"), f("contact"), f("email"), f("phone"), inn, jd(pids),
            f("volume"), f("message"), st, _num(b.get("amount")), f("next_step"), _date(b.get("due")), f("notes"), now())
    with con:
        if iid:
            old = con.execute("SELECT status FROM catalog_inquiries WHERE id=?", (iid,)).fetchone()
            if not old: raise ValueError("Сўров топилмади")
            con.execute("""UPDATE catalog_inquiries SET at=?, channel=?, source=?, country=?, buyer=?, contact=?, email=?, phone=?, inn=?, product_ids=?, volume=?,
                           message=?, status=?, amount=?, next_step=?, due=?, notes=?, updated_at=?, closed_at=CASE WHEN ? IN ('deal','lost') THEN coalesce(closed_at, ?) ELSE NULL END
                           WHERE id=?""", (*vals, st, now(), iid))
        else:
            cur = con.execute("""INSERT INTO catalog_inquiries(at, channel, source, country, buyer, contact, email, phone, inn, product_ids, volume, message, status,
                                 amount, next_step, due, notes, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals)
            iid = cur.lastrowid
        if inn: db.event(con, inn, "catalog", f"Каталог сўрови №{iid}: {f('buyer') or f('contact') or ''} ({f('country') or ''}) — {st}")
    return {"ok": True, "id": iid}

def inquiry_delete(con, iid: int) -> dict:
    with con: con.execute("DELETE FROM catalog_inquiries WHERE id=?", (int(iid),))
    return {"ok": True}

def inquiry_public(con, b: dict) -> dict:
    """Сайт формаси (локал олдиндан кўриш ёки келажакдаги сервер): {name, company, country, email, phone, message, items:[{id, qty}]}."""
    items = [x for x in (b.get("items") or []) if isinstance(x, dict) and x.get("id")]
    pids = [int(x["id"]) for x in items]
    inns = {r[0] for r in con.execute(f"SELECT inn FROM catalog_products WHERE id IN ({','.join('?' * len(pids)) or 'NULL'})", pids)} if pids else set()
    lines = [f"- #{x['id']}: {x.get('qty') or ''}" for x in items]
    return inquiry_save(con, {"channel": "site", "source": b.get("source") or "Сайт", "country": b.get("country"), "buyer": b.get("company"),
                              "contact": b.get("name"), "email": b.get("email"), "phone": b.get("phone"), "inn": next(iter(inns)) if len(inns) == 1 else None,
                              "product_ids": pids, "message": ((b.get("message") or "") + ("\n" + "\n".join(lines) if lines else "")).strip(), "status": "new"})

def inquiries_xlsx(con, out: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    d = inquiries(con)
    wb = Workbook(); ws = wb.active; ws.title = "Сўровлар"
    hdr = ["№", "Сана", "Канал", "Манба (элчихона, кўргазма…)", "Давлат", "Харидор", "Алоқа шахси", "Email", "Телефон", "Корхона", "ИНН", "Маҳсулотлар",
           "Ҳажм", "Ҳолат", "Сумма (минг $)", "Кейинги қадам", "Муддат", "Изоҳ"]
    SN = {"new": "Янги", "sent": "Корхонага юборилди", "talks": "Музокара", "deal": "Шартнома", "lost": "Натижасиз"}
    CH = {"embassy": "Элчихона", "exhibition": "Кўргазма", "site": "Сайт", "direct": "Тўғридан-тўғри", "b2b": "B2B учрашув", "other": "Бошқа"}
    ws.append(hdr)
    for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0F6E63"); c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in d["rows"]:
        ws.append([r["id"], r["at"], CH.get(r["channel"], r["channel"]), r["source"], r["country"], r["buyer"], r["contact"], r["email"], r["phone"],
                   r["company"], r["inn"], "; ".join(p["name"] for p in r["products"]), r["volume"], SN.get(r["status"], r["status"]), r["amount"],
                   r["next_step"], r["due"], r["notes"]])
    for i, w in enumerate([5, 11, 13, 30, 14, 26, 20, 24, 16, 28, 11, 40, 14, 18, 12, 28, 11, 30], 1): ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "A2"
    wb.save(out); return out

# ------------------------------------------------------------------ price list (Excel) for embassies
def pricelist_xlsx(con, out: Path, lang: str = "en") -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    lang = lang if lang in LANGS else "en"
    d = public(con, False); I = i18n()
    L = {"en": ["Category", "Company", "District", "Product", "HS code", "Price", "Currency", "Unit", "Incoterms", "Min. order", "Packaging", "Price valid until"],
         "ru": ["Категория", "Компания", "Район", "Продукция", "Код ТН ВЭД", "Цена", "Валюта", "Ед.", "Инкотермс", "Мин. партия", "Упаковка", "Цена действительна до"],
         "uz": ["Kategoriya", "Korxona", "Tuman", "Mahsulot", "TN VED kodi", "Narx", "Valyuta", "Birlik", "Inkoterms", "Min. partiya", "Qadoqlash", "Narx amal qiladi"]}[lang]
    title = d["site"]["title"][lang]
    wb = Workbook(); ws = wb.active; ws.title = "Price list"[:31]
    ws.append([title]); ws["A1"].font = Font(bold=True, size=14)
    ws.append([d["site"]["org"][lang] + (" · " + d["site"]["email"] if d["site"].get("email") else "") + (" · " + d["site"]["phone"] if d["site"].get("phone") else "")])
    ws.append([]); ws.append(L)
    for c in ws[4]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0F6E63"); c.alignment = Alignment(wrap_text=True, vertical="center")
    comp = {c["id"]: c for c in d["companies"]}
    pick = lambda o: (o or {}).get(lang) or (o or {}).get("en") or (o or {}).get("ru") or (o or {}).get("uz") or ""
    rows = sorted(d["products"], key=lambda p: (pick(I["cat1"].get(p["cat1"] or "", {})), pick(comp[p["c"]]["name"]), pick(p["name"])))
    for p in rows:
        c = comp[p["c"]]
        onreq = {"en": "on request", "ru": "по запросу", "uz": "soʻrov boʻyicha"}[lang]
        price = (p["price"] if not p["price_to"] else f"{p['price']:g}–{p['price_to']:g}" if p["price"] else p["price_to"]) if (p["price"] or p["price_to"]) else onreq
        ws.append([pick(I["cat1"].get(p["cat1"] or "", {})), pick(c["name"]), pick(I["districts"].get(c["district"] or "", {})), pick(p["name"]), p["hs"],
                   price, p["cur"], pick(I["units"].get(p["unit"] or "", {})) or p["unit"], p["inc"],
                   (f"{p['moq']:g} " + (pick(I["units"].get(p["moq_unit"] or "", {})) or p["moq_unit"] or "")) if p["moq"] else "", pick(p["pack"]), p["price_valid"]])
    for i, w in enumerate([24, 32, 20, 46, 13, 12, 8, 10, 11, 14, 34, 14], 1): ws.column_dimensions[ws.cell(4, i).column_letter].width = w
    ws.freeze_panes = "A5"
    wb.save(out); return out

# ------------------------------------------------------------------ seed package (Drive -> catalog), one time
def seed_dir() -> Path: return db.BASE / "catalog_seed"

def seed_status(con) -> dict | None:
    p = seed_dir() / "seed.json"
    if not p.exists(): return None
    s = json.loads(p.read_text(encoding="utf-8"))
    applied = db.get_setting(con, "catalog_seed_applied") == s.get("id")
    return {"id": s.get("id"), "title": s.get("title"), "companies": len(s.get("companies", [])),
            "products": sum(len(c.get("products", [])) for c in s.get("companies", [])), "applied": applied}

def seed_apply(con) -> dict:
    """seed.json: {"id","title","companies":[{inn, status, i18n, founded, …, logo:"file", cover:"file", gallery:[{file,title}], docs:[{file,title,type,valid_until,public}],
    contacts:{director, phone, email, address}, products:[{…product fields…, photos:["file"]}]}]} — fayllar seed_dir ichida.
    Mavjud korxona bo'lsa: bo'sh maydonlar to'ldiriladi, mahsulotlar hs10+nom bo'yicha qayta qo'shilmaydi."""
    base = seed_dir(); s = json.loads((base / "seed.json").read_text(encoding="utf-8"))
    if db.get_setting(con, "catalog_seed_applied") == s.get("id"): raise ValueError("Бу пакет аллақачон юкланган")
    db.backup("catalog_seed")
    res = {"companies": 0, "products": 0, "photos": 0, "docs": 0, "contacts": 0, "skipped": []}
    dims = s.get("dims") or {}
    def img(path: Path) -> dict:
        raw = path.read_bytes(); th = (path.with_name(path.stem + "_t.jpg")); wh = dims.get(path.name) or [None, None]
        return {"main": base64.b64encode(raw).decode(), "thumb": base64.b64encode(th.read_bytes()).decode() if th.exists() else None, "filename": path.name, "w": wh[0], "h": wh[1]}
    for c in s["companies"]:
        inn = c["inn"]
        if not con.execute("SELECT 1 FROM companies WHERE inn=?", (inn,)).fetchone(): res["skipped"].append(inn); continue
        add_company(con, inn, templates=False)
        cur = detail(con, inn)["company"]
        tx = {l: dict(cur["i18n"][l]) for l in LANGS}
        for l in LANGS:   # пакет матни бўш майдонларни тўлдиради; ном — пакетдагиси (реестрдан олинган автоматик ном ўрнига)
            for k, v in ((c.get("i18n") or {}).get(l) or {}).items():
                if v and (k == "name" or not tx[l].get(k)): tx[l][k] = v
        body = {**cur, "inn": inn, "i18n": tx}
        for k in ("founded", "employees", "website", "video", "incoterms", "payment", "markets", "note", "featured"):
            if c.get(k) not in (None, "", []) and cur.get(k) in (None, "", []): body[k] = c[k]
        body["status"] = c.get("status") or cur["status"]
        save_company(con, body); res["companies"] += 1
        for k in ("logo", "cover"):
            if c.get(k) and not cur.get(k): media_upload(con, {"inn": inn, "kind": k, **img(base / c[k])}); res["photos"] += 1
        for g in c.get("gallery", []):
            media_upload(con, {"inn": inn, "kind": "photo", "title": g.get("title"), **img(base / g["file"])}); res["photos"] += 1
        for dd in c.get("docs", []):
            f = base / dd["file"]
            doc_upload(con, inn, dd.get("filename") or f.name, f.read_bytes(), dd.get("title"), dd.get("type") or "other", dd.get("valid_until"), None, dd.get("public", True)); res["docs"] += 1
        ct = c.get("contacts") or {}
        if ct:
            old = con.execute("SELECT * FROM company_contacts WHERE inn=?", (inn,)).fetchone()
            vals = {k: (ct.get(k) or "").strip() for k in ("director", "phone", "email", "address")}
            with con:
                if not old:
                    con.execute("INSERT INTO company_contacts(inn, director, phone, phones, email, address, updated_at) VALUES(?,?,?,?,?,?,?)",
                                (inn, vals["director"] or None, (ct.get("phones") or [vals["phone"]])[0] or None, jd(ct.get("phones") or ([vals["phone"]] if vals["phone"] else [])),
                                 vals["email"] or None, vals["address"] or None, now()))
                    res["contacts"] += 1
                else:
                    upd = {k: v for k, v in vals.items() if v and not (old[k] or "").strip()}
                    if upd.get("phone") and (old["phones"] or "") in ("", "[]"): upd["phones"] = jd(ct.get("phones") or [upd["phone"]])
                    if upd:
                        con.execute(f"UPDATE company_contacts SET {', '.join(k + '=?' for k in upd)}, updated_at=? WHERE inn=?", (*upd.values(), now(), inn)); res["contacts"] += 1
                if ct.get("note"): db.event(con, inn, "catalog", "Каталог манбаси: " + ct["note"])
        have = {(r["hs10"], json.loads(r["i18n"] or "{}").get("en", {}).get("name")) for r in con.execute("SELECT hs10, i18n FROM catalog_products WHERE inn=?", (inn,))}
        for p in c.get("products", []):
            if (p.get("hs10"), (p.get("i18n", {}).get("en") or {}).get("name")) in have: continue
            r = save_product(con, {**p, "inn": inn, "source": "seed"}); res["products"] += 1
            for ph in p.get("photos", []):
                media_upload(con, {"inn": inn, "kind": "photo", "product_id": r["id"], **img(base / ph)}); res["photos"] += 1
        if c.get("templates"): add_products_from_templates(con, inn)
    with con:
        db.set_setting(con, "catalog_seed_applied", s.get("id")); db.log(con, "catalog_seed", **{k: v for k, v in res.items()})
    return {"ok": True, **res}

# ------------------------------------------------------------------ HTTP (server.py delegates here)
def http_get(con, path: str, q: dict):
    """-> dict (json) | ("file", Path, download_name)"""
    if path == "/api/catalog/overview": return overview(con, q)
    if path == "/api/catalog/company": return detail(con, q["inn"])
    if path == "/api/catalog/public": return public(con, q.get("admin") == "1")
    if path == "/api/catalog/inquiries": return inquiries(con, q)
    if path == "/api/catalog/candidates":   # каталогга қўшиш учун реестрдан қидирув
        qq = q.get("q") or ""
        have = {r[0] for r in con.execute("SELECT inn FROM catalog_companies")}
        y = int(db.get_setting(con, "year") or dt.date.today().year)
        ex = {r[0]: r[1] for r in con.execute("SELECT inn, sum(value) FROM items WHERE regime='ЭК' AND year>=? GROUP BY 1", (y - 1,))}
        out = []
        for r in con.execute("SELECT inn, name, full_name, district_code FROM companies"):
            if qq and not smart.match(qq, r["inn"], r["name"], r["full_name"]): continue
            if not qq and r["inn"] not in ex: continue
            out.append({"inn": r["inn"], "name": r["name"], "district_code": r["district_code"], "export": round(ex.get(r["inn"], 0), 1), "in_catalog": r["inn"] in have})
        out.sort(key=lambda x: (x["in_catalog"], -x["export"]))
        return out[:60]
    if path == "/api/catalog/site.zip":
        p, _ = build_site(con); return ("file", p, p.name)
    if path == "/api/catalog/pricelist.xlsx":
        lang = q.get("lang") or "en"
        out = db.BASE / "exports" / f"Bukhara_export_price_list_{lang}_{dt.date.today():%Y-%m-%d}.xlsx"; out.parent.mkdir(parents=True, exist_ok=True)
        return ("file", pricelist_xlsx(con, out, lang), out.name)
    if path == "/api/catalog/inquiries.xlsx":
        out = db.BASE / "exports" / f"Каталог сўровлари {dt.date.today():%d.%m.%Y}.xlsx"; out.parent.mkdir(parents=True, exist_ok=True)
        return ("file", inquiries_xlsx(con, out), out.name)
    raise ValueError("Каталог: номаълум сўров " + path)

def http_post(con, path: str, body: dict | None, raw: bytes | None, headers) -> dict:
    import urllib.parse as up
    if path == "/api/catalog/doc/upload":
        h = lambda k: up.unquote(headers.get(k) or "")
        return doc_upload(con, h("X-Inn"), h("X-Filename"), raw, h("X-Title"), h("X-Type") or "certificate", h("X-Valid") or None, h("X-Product") or None, h("X-Public") != "0")
    b = body or {}
    if path == "/api/catalog/company/add": return add_company(con, b.get("inn"), b.get("templates", True))
    if path == "/api/catalog/company/save": return save_company(con, b)
    if path == "/api/catalog/company/status": return set_company_status(con, b.get("inn"), b.get("status"))
    if path == "/api/catalog/company/delete": return delete_company(con, b.get("inn"))
    if path == "/api/catalog/templates/add":
        with con: n = add_products_from_templates(con, inn_str(b.get("inn")), b.get("hs") or None, b.get("status") or "draft")
        return {"ok": True, "n": n}
    if path == "/api/catalog/templates/bulk": return bulk_templates(con, b)
    if path == "/api/catalog/product/save": return save_product(con, b)
    if path == "/api/catalog/product/delete": return delete_product(con, int(b["id"]))
    if path == "/api/catalog/products/bulk": return bulk_products(con, b)
    if path == "/api/catalog/reorder": return reorder(con, b)
    if path == "/api/catalog/media/upload": return media_upload(con, b)
    if path == "/api/catalog/media/update": return media_update(con, b)
    if path == "/api/catalog/media/delete": return media_delete(con, b["id"])
    if path == "/api/catalog/settings": return save_settings(con, b)
    if path == "/api/catalog/inquiry/save": return inquiry_save(con, b)
    if path == "/api/catalog/inquiry/delete": return inquiry_delete(con, b["id"])
    if path == "/api/catalog/inquiry/public": return inquiry_public(con, b)
    if path == "/api/catalog/seed/apply": return seed_apply(con)
    raise ValueError("Каталог: номаълум амал " + path)
