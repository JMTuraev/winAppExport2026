"""Korxonalar aloqa ma'lumotlarini Excel'dan yuklash (Korxonalar → «Алоқа Excel юклаш»).

Har qanday jadval qabul qilinadi: sarlavha qatori «ИНН/СТИР» va «Корхона номи» ustunlari bo'lgan qator deb topiladi,
qolgan ustunlar sarlavha matni bo'yicha taniladi (Раҳбар, Тел рақами, Бош ҳисобчи, Масъул шахс, Лавозими, Email, Манзил,
Изоҳ, Банк, Маҳсулот). Bizning «Корхоналар алоқа маълумотлари (тўлдириш учун).xlsx» shabloni ham, boshqarma
ro'yxatlari («Жами корхоналар») ham o'qiladi. Barcha varaqlar ko'riladi; INN bazada bo'lmasa — qator o'tkazib yuboriladi.

Qoida: bo'sh katak mavjud ma'lumotni o'chirmaydi; telefonlar birlashtiriladi (takror yo'q); shaxslar ism bo'yicha
topilib yangilanadi, yo'q bo'lsa qo'shiladi.
"""
from __future__ import annotations
import re, json
from pathlib import Path
from . import db, companies
from .xl import read_sheet, sheet_names, inn_str

# header patterns (lower-cased, spaces collapsed); order matters for «Тел рақами» which belongs to the previous name column
H = {
    "inn": r"^(инн|стир|inn|stir)\b",
    "name": r"корхона\s*номи|^корхона$|^номи$",
    "director": r"раҳбар|рахбар|директор|rahbar",
    "accountant": r"ҳисобчи|хисобчи|hisobchi|бухгалтер",
    "person": r"масъул\s*шахс|масьул\s*шахс|мас.ул\s*шахс|шахс\s*\(",
    "role": r"лавозим",
    "email": r"e-?mail|почта",
    "address": r"манзил|адрес",
    "note": r"изоҳ|изох|примеч",
    "bank": r"банк",
    "product": r"маҳсулот|махсулот|махссулот|продукц",
    "phone": r"тел|телефон|phone|рақам",
}

def _h(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()

def _find_header(rows):
    for i, row in enumerate(rows[:40]):
        hs = [_h(v) for v in row]
        if any(re.search(H["inn"], h) for h in hs) and any(re.search(H["name"], h) for h in hs):
            return i
    return None

def _map_columns(row) -> dict:
    """column index per field; a «Тел рақами» column belongs to the person column just before it
    (Раҳбар / Бош ҳисобчи / Масъул шахс); any other recognised or unknown column ends that ownership."""
    m, owner = {}, None
    keys = ("inn", "product", "name", "director", "accountant", "person", "role", "email", "address", "note", "bank")
    for i, v in enumerate(row):
        h = _h(v)
        if not h: continue
        is_phone = bool(re.search(H["phone"], h))
        who = next((k for k in ("director", "accountant", "person") if re.search(H[k], h)), None)
        if is_phone and not who:
            if owner: m.setdefault(f"{owner}_phone", []).append(i)
            continue
        hit = next((k for k in keys if re.search(H[k], h)), None)
        if hit in ("director", "accountant", "person"):
            owner = hit
            if is_phone: m.setdefault(f"{hit}_phone", []).append(i)
            else: m.setdefault(hit, i)
        elif hit == "role":
            m.setdefault("role", i); owner = "person"
        elif hit:
            m.setdefault(hit, i); owner = None
        else:
            owner = None
    return m

def _phones_from(row, idxs) -> list[str]:
    out = []
    for i in idxs or []:
        raw = str(row[i] if i < len(row) and row[i] is not None else "")
        for piece in re.split(r"[,;\n/]+|\s{2,}", raw):
            p = companies.norm_phone(piece)
            if p and p not in out: out.append(p)
    return out

def _cell(row, i):
    if i is None or i >= len(row) or row[i] is None: return ""
    v = row[i]
    if isinstance(v, float) and v.is_integer(): v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()

def import_xlsx(con, filename: str, data: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in (".xls", ".xlsx"): raise ValueError("Faqat .xls yoki .xlsx fayl")
    p = Path("upload" + ext)
    names = sheet_names(p, data=data)
    rep = {"sheets": [], "rows": 0, "updated": 0, "persons": 0, "phones": 0, "skipped": [], "no_inn": 0, "unchanged": 0}
    known = {r["inn"]: r["name"] for r in con.execute("SELECT inn, name FROM companies")}
    db.backup_if_stale("before_contacts_import")
    for si, sname in enumerate(names):
        rows = read_sheet(p, si, data=data)
        hi = _find_header(rows)
        if hi is None: continue
        cm = _map_columns(rows[hi])
        # a second header line (e.g. «Миқдори / Нархи») directly under — skip rows without an INN anyway
        rep["sheets"].append({"name": sname, "columns": sorted(k for k in cm if not k.endswith("_phone")) + [k for k in cm if k.endswith("_phone")]})
        for row in rows[hi + 1:]:
            inn = inn_str(_cell(row, cm.get("inn")))
            if not inn or not inn.isdigit(): rep["no_inn"] += (1 if any(_cell(row, i) for i in range(len(row))) else 0); continue
            rep["rows"] += 1
            if inn not in known:
                rep["skipped"].append({"inn": inn, "name": _cell(row, cm.get("name")), "sheet": sname}); continue
            changed = _apply_row(con, inn, row, cm, rep)
            if changed: rep["updated"] += 1
            else: rep["unchanged"] += 1
    if not rep["sheets"]: raise ValueError("Файлда «ИНН» ва «Корхона номи» устунли сарлавҳа топилмади")
    db.log(con, "contacts_import", file=filename, rows=rep["rows"], updated=rep["updated"], persons=rep["persons"], skipped=len(rep["skipped"]))
    rep["skipped_n"] = len(rep["skipped"]); rep["skipped"] = rep["skipped"][:200]
    return rep

def _apply_row(con, inn: str, row, cm: dict, rep: dict) -> bool:
    old = companies._contact_row(con.execute("SELECT * FROM company_contacts WHERE inn=?", (inn,)).fetchone())
    director = _cell(row, cm.get("director")) or old.get("director") or ""
    phones = list(old.get("phones") or [])
    for ph in _phones_from(row, cm.get("director_phone")):
        if ph not in phones: phones.append(ph); rep["phones"] += 1
    email = _cell(row, cm.get("email")) or old.get("email") or ""
    address = _cell(row, cm.get("address")) or old.get("address") or ""
    note = old.get("note") or ""
    extra = _cell(row, cm.get("note"))
    if extra and extra not in note: note = (note + "\n" if note else "") + extra
    bank = _cell(row, cm.get("bank"))
    if bank and ("Банк: " + bank) not in note: note = (note + "\n" if note else "") + "Банк: " + bank
    new = {"director": director, "phones": phones, "email": email, "address": address, "note": note}
    changed = False
    if (new["director"] or "") != (old.get("director") or "") or phones != (old.get("phones") or []) or (email or "") != (old.get("email") or "") \
            or (address or "") != (old.get("address") or "") or (note or "") != (old.get("note") or ""):
        companies.save_contacts(con, inn, new); changed = True
    product = _cell(row, cm.get("product"))
    if product:
        cur = con.execute("SELECT product FROM companies WHERE inn=?", (inn,)).fetchone()
        if cur and not (cur[0] or "").strip():
            with con: con.execute("UPDATE companies SET product=? WHERE inn=?", (product, inn))
            changed = True
    for key, default_role in (("accountant", "Бош ҳисобчи"), ("person", None)):
        name = _cell(row, cm.get(key))
        if not name or len(name) < 2: continue
        role = _cell(row, cm.get("role")) if key == "person" else ""
        role = role or default_role or "Масъул шахс"
        ph = _phones_from(row, cm.get(f"{key}_phone"))
        ex = next((p for p in companies.persons_list(con, inn) if p["name"].casefold() == name.casefold()), None)
        if ex:
            merged = list(ex["phones"]) + [x for x in ph if x not in ex["phones"]]
            if merged != ex["phones"] or (ex.get("role") or "") != role:
                companies.save_person(con, {"id": ex["id"], "inn": inn, "name": name, "role": role, "phones": merged, "note": ex.get("note") or ""}); changed = True
        else:
            companies.save_person(con, {"inn": inn, "name": name, "role": role, "phones": ph, "note": ""}); rep["persons"] += 1; changed = True
        rep["phones"] += len(ph)
    return changed
