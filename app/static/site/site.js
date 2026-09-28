/* Bukhara Export Catalog — public site.
   One code base: served by the local app at /catalog/ (preview, ?admin=1 shows drafts + edit buttons) and exported as a
   static package (index.html + data.js + media/) that works from any hosting or straight from disk. No external requests. */
(function () {
"use strict";
const D = window.CATALOG || { companies: [], products: [], i18n: {}, site: {} };
const ADMIN = /[?&]admin=1/.test(location.search);
const LOCAL = /^https?:$/.test(location.protocol) && /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
const LANGS = ["en", "ru", "uz"];

// ------------------------------------------------------------------ UI strings
const T = {
  en: { brandSub: "Bukhara region · Uzbekistan", search: "Search products, companies, HS codes…", inquiry: "Inquiry list", pdf: "PDF catalog",
    heroEyebrow: "Made in Bukhara · Uzbekistan", heroTitle: "Export-ready products from manufacturers of Bukhara region",
    heroText: "Prices, specifications and certificates in one place. Send a single inquiry — the regional Department of Investments, Industry and Trade will connect you with the producer.",
    browse: "Browse products", sendInquiry: "Send inquiry", stProducts: "products", stCompanies: "manufacturers", stCategories: "categories", stMarkets: "export markets",
    products: "Products", companies: "Manufacturers", sort: { featured: "Recommended", priceAsc: "Price: low to high", priceDesc: "Price: high to low", name: "Name A–Z", newest: "Newest" },
    filters: "Filters", category: "Category", all: "All categories", district: "Location", allDistricts: "All districts", options: "Options", withPrice: "With price", certified: "With certificates",
    incoterms: "Delivery terms", clear: "Clear filters", onRequest: "Price on request", indicative: "Indicative price", validUntil: "Price valid until {d}", asOf: "as of {d}",
    moq: "Min. order", hs: "HS code", packaging: "Packaging", capacity: "Supply capacity", lead: "Lead time", sku: "Model / code", incoterm: "Delivery terms",
    description: "Description", specs: "Specifications", documents: "Certificates & documents", more: "More from this manufacturer", viewCompany: "View manufacturer",
    addList: "Add to inquiry list", inList: "In inquiry list", requestQuote: "Request a quote", share: "Copy link", copied: "Link copied",
    about: "About the company", facts: "Key facts", founded: "Founded", employees: "Employees", tin: "TIN", location: "Location",
    markets: "Export experience", marketsNote: "Countries this manufacturer has exported to (customs data, 2024–2026)", targetMarkets: "Target markets", payment: "Payment terms",
    gallery: "Production & facilities", contactVia: "Contact through the regional department",
    contactViaText: "Buyer inquiries are handled by the {org}. The department verifies each request and connects you with the manufacturer.",
    productsN: "{n} products", productN1: "1 product", certifiedTag: "Certified", draft: "Draft", missing: "Translation missing — shown from another language",
    emptyList: "Your inquiry list is empty. Open a product and press “Add to inquiry list”.", yourDetails: "Your details", name: "Full name", company: "Company",
    country: "Country", email: "Email", phone: "Phone / WhatsApp", message: "Message", qty: "Quantity (e.g. 5 t)", send: "Send inquiry",
    sent: "Thank you! Your inquiry has been received. The regional department will contact you shortly.", orSendVia: "Send directly:",
    viaEmail: "Email", viaWhatsApp: "WhatsApp", viaTelegram: "Telegram", msgCopied: "Message copied — paste it into the chat",
    required: "Please enter your name and an email or phone number", remove: "Remove", noResults: "No products match your filters.", updated: "Updated",
    catalogBy: "Catalog maintained by", contacts: "Contacts", printBtn: "Print / Save as PDF", back: "Back", photoSoon: "Photo coming soon", home: "Catalog",
    aboutInquiry: "Inquiry about {c}", generalInquiry: "General inquiry", inquiryIntro: "List the products and quantities you are interested in. We forward your request to the manufacturers.",
    subject: "Inquiry — Bukhara Export Catalog", preview: "Preview", previewText: "drafts are shown with a label; published site shows only published items",
    edit: "Edit", noContact: "Contact details of the department will be published soon.", perUnit: "per {u}", fromPrice: "from", priceList: "Price list",
    nothingYet: "The catalog is being prepared.", validTo: "valid until {d}", tinShort: "TIN", est: "est. {y}", people: "{n} employees" },
  ru: { brandSub: "Бухарская область · Узбекистан", search: "Поиск товаров, компаний, кодов ТН ВЭД…", inquiry: "Список запроса", pdf: "PDF-каталог",
    heroEyebrow: "Сделано в Бухаре · Узбекистан", heroTitle: "Экспортная продукция производителей Бухарской области",
    heroText: "Цены, характеристики и сертификаты в одном месте. Отправьте один запрос — Управление инвестиций, промышленности и торговли области свяжет вас с производителем.",
    browse: "Смотреть товары", sendInquiry: "Отправить запрос", stProducts: "товаров", stCompanies: "производителей", stCategories: "категорий", stMarkets: "стран экспорта",
    products: "Товары", companies: "Производители", sort: { featured: "Рекомендуемые", priceAsc: "Цена: по возрастанию", priceDesc: "Цена: по убыванию", name: "По названию", newest: "Новые" },
    filters: "Фильтры", category: "Категория", all: "Все категории", district: "Район", allDistricts: "Все районы", options: "Параметры", withPrice: "С ценой", certified: "С сертификатами",
    incoterms: "Условия поставки", clear: "Сбросить фильтры", onRequest: "Цена по запросу", indicative: "Ориентировочная цена", validUntil: "Цена действительна до {d}", asOf: "на {d}",
    moq: "Мин. партия", hs: "Код ТН ВЭД", packaging: "Упаковка", capacity: "Объём поставок", lead: "Срок поставки", sku: "Модель / код", incoterm: "Условия поставки",
    description: "Описание", specs: "Характеристики", documents: "Сертификаты и документы", more: "Другие товары производителя", viewCompany: "О производителе",
    addList: "Добавить в запрос", inList: "В списке запроса", requestQuote: "Запросить цену", share: "Скопировать ссылку", copied: "Ссылка скопирована",
    about: "О компании", facts: "Основные данные", founded: "Год основания", employees: "Сотрудники", tin: "ИНН", location: "Расположение",
    markets: "Опыт экспорта", marketsNote: "Страны, куда производитель экспортировал продукцию (таможенные данные, 2024–2026)", targetMarkets: "Целевые рынки", payment: "Условия оплаты",
    gallery: "Производство", contactVia: "Связь через областное управление",
    contactViaText: "Запросы покупателей обрабатывает {org}. Управление проверяет каждый запрос и связывает вас с производителем.",
    productsN: "{n} товаров", productN1: "1 товар", certifiedTag: "Сертифицировано", draft: "Черновик", missing: "Нет перевода — показан другой язык",
    emptyList: "Список запроса пуст. Откройте товар и нажмите «Добавить в запрос».", yourDetails: "Ваши данные", name: "Имя и фамилия", company: "Компания",
    country: "Страна", email: "E-mail", phone: "Телефон / WhatsApp", message: "Сообщение", qty: "Количество (напр. 5 т)", send: "Отправить запрос",
    sent: "Спасибо! Ваш запрос получен. Специалисты областного управления свяжутся с вами.", orSendVia: "Отправить напрямую:",
    viaEmail: "E-mail", viaWhatsApp: "WhatsApp", viaTelegram: "Telegram", msgCopied: "Текст скопирован — вставьте его в чат",
    required: "Укажите имя и e-mail или телефон", remove: "Убрать", noResults: "Нет товаров по выбранным фильтрам.", updated: "Обновлено",
    catalogBy: "Каталог ведёт", contacts: "Контакты", printBtn: "Печать / Сохранить в PDF", back: "Назад", photoSoon: "Фото скоро", home: "Каталог",
    aboutInquiry: "Запрос: {c}", generalInquiry: "Общий запрос", inquiryIntro: "Укажите интересующие товары и объёмы. Мы передадим запрос производителям.",
    subject: "Запрос — Экспортный каталог Бухарской области", preview: "Предпросмотр", previewText: "черновики отмечены; на сайте видны только опубликованные",
    edit: "Изменить", noContact: "Контакты управления будут опубликованы в ближайшее время.", perUnit: "за {u}", fromPrice: "от", priceList: "Прайс-лист",
    nothingYet: "Каталог готовится.", validTo: "действует до {d}", tinShort: "ИНН", est: "с {y} г.", people: "{n} сотрудников" },
  uz: { brandSub: "Buxoro viloyati · Oʻzbekiston", search: "Mahsulot, korxona, TN VED kodi boʻyicha qidiruv…", inquiry: "Soʻrov roʻyxati", pdf: "PDF katalog",
    heroEyebrow: "Buxoroda ishlab chiqarilgan · Oʻzbekiston", heroTitle: "Buxoro viloyati ishlab chiqaruvchilarining eksportbop mahsulotlari",
    heroText: "Narxlar, tavsiflar va sertifikatlar bir joyda. Bitta soʻrov yuboring — viloyat investitsiyalar, sanoat va savdo boshqarmasi sizni ishlab chiqaruvchi bilan bogʻlaydi.",
    browse: "Mahsulotlarni koʻrish", sendInquiry: "Soʻrov yuborish", stProducts: "mahsulot", stCompanies: "ishlab chiqaruvchi", stCategories: "kategoriya", stMarkets: "eksport davlati",
    products: "Mahsulotlar", companies: "Ishlab chiqaruvchilar", sort: { featured: "Tavsiya etilgan", priceAsc: "Narx: arzonidan", priceDesc: "Narx: qimmatidan", name: "Nomi boʻyicha", newest: "Yangilari" },
    filters: "Filtrlar", category: "Kategoriya", all: "Barcha kategoriyalar", district: "Hudud", allDistricts: "Barcha tumanlar", options: "Parametrlar", withPrice: "Narxi bor", certified: "Sertifikati bor",
    incoterms: "Yetkazib berish shartlari", clear: "Filtrlarni tozalash", onRequest: "Narx soʻrov boʻyicha", indicative: "Taxminiy narx", validUntil: "Narx {d} gacha amal qiladi", asOf: "{d} holatiga",
    moq: "Min. partiya", hs: "TN VED kodi", packaging: "Qadoqlash", capacity: "Yetkazib berish hajmi", lead: "Yetkazish muddati", sku: "Model / kod", incoterm: "Yetkazib berish shartlari",
    description: "Tavsif", specs: "Xususiyatlari", documents: "Sertifikat va hujjatlar", more: "Ishlab chiqaruvchining boshqa mahsulotlari", viewCompany: "Ishlab chiqaruvchi haqida",
    addList: "Soʻrovga qoʻshish", inList: "Soʻrov roʻyxatida", requestQuote: "Narx soʻrash", share: "Havolani nusxalash", copied: "Havola nusxalandi",
    about: "Korxona haqida", facts: "Asosiy maʼlumotlar", founded: "Tashkil etilgan", employees: "Xodimlar", tin: "STIR", location: "Joylashuvi",
    markets: "Eksport tajribasi", marketsNote: "Korxona eksport qilgan davlatlar (bojxona maʼlumoti, 2024–2026)", targetMarkets: "Maqsadli bozorlar", payment: "Toʻlov shartlari",
    gallery: "Ishlab chiqarish", contactVia: "Viloyat boshqarmasi orqali bogʻlanish",
    contactViaText: "Xaridor soʻrovlari bilan {org} shugʻullanadi. Boshqarma har bir soʻrovni tekshirib, sizni ishlab chiqaruvchi bilan bogʻlaydi.",
    productsN: "{n} ta mahsulot", productN1: "1 ta mahsulot", certifiedTag: "Sertifikatlangan", draft: "Qoralama", missing: "Tarjima yoʻq — boshqa tildan koʻrsatilgan",
    emptyList: "Soʻrov roʻyxati boʻsh. Mahsulotni oching va «Soʻrovga qoʻshish» tugmasini bosing.", yourDetails: "Maʼlumotlaringiz", name: "Ism-sharif", company: "Kompaniya",
    country: "Davlat", email: "E-mail", phone: "Telefon / WhatsApp", message: "Xabar", qty: "Miqdor (masalan, 5 t)", send: "Soʻrov yuborish",
    sent: "Rahmat! Soʻrovingiz qabul qilindi. Viloyat boshqarmasi mutaxassislari siz bilan bogʻlanadi.", orSendVia: "Toʻgʻridan-toʻgʻri yuborish:",
    viaEmail: "E-mail", viaWhatsApp: "WhatsApp", viaTelegram: "Telegram", msgCopied: "Matn nusxalandi — uni chatga joylang",
    required: "Ism va e-mail yoki telefon raqamini kiriting", remove: "Olib tashlash", noResults: "Filtrlarga mos mahsulot yoʻq.", updated: "Yangilangan",
    catalogBy: "Katalogni yuritadi", contacts: "Aloqa", printBtn: "Chop etish / PDF saqlash", back: "Orqaga", photoSoon: "Rasm tez orada", home: "Katalog",
    aboutInquiry: "Soʻrov: {c}", generalInquiry: "Umumiy soʻrov", inquiryIntro: "Qiziqtirgan mahsulotlar va hajmni koʻrsating. Soʻrovingizni ishlab chiqaruvchilarga yetkazamiz.",
    subject: "Soʻrov — Buxoro viloyati eksport katalogi", preview: "Oldindan koʻrish", previewText: "qoralamalar belgi bilan; saytda faqat eʼlon qilinganlar koʻrinadi",
    edit: "Tahrirlash", noContact: "Boshqarma aloqa maʼlumotlari tez orada eʼlon qilinadi.", perUnit: "{u} uchun", fromPrice: "dan", priceList: "Prays-list",
    nothingYet: "Katalog tayyorlanmoqda.", validTo: "{d} gacha amal qiladi", tinShort: "STIR", est: "{y} yildan", people: "{n} nafar xodim" },
};

// ------------------------------------------------------------------ helpers
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const typo = s => String(s ?? "").replace(/ʻ/g, "‘").replace(/ʼ/g, "’");   // o‘/g‘: U+02BB shriftda keng ko'rinadi
const esc = s => typo(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = { get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} } };
function pickLang() {
  const q = (location.search.match(/[?&]lang=(en|ru|uz)/) || [])[1]; if (q) return q;
  const s = store.get("bec-lang", null); if (LANGS.includes(s)) return s;
  const n = (navigator.language || "en").slice(0, 2).toLowerCase();
  return n === "ru" || n === "kk" || n === "ky" || n === "tg" ? "ru" : n === "uz" ? "uz" : "en";
}
let L = pickLang();
const t = (k, v) => { let s = k.split(".").reduce((o, x) => o && o[x], T[L]) ?? k.split(".").reduce((o, x) => o && o[x], T.en) ?? k; if (v) for (const [a, b] of Object.entries(v)) s = String(s).replace("{" + a + "}", b); return s; };
const tv = o => typo(!o ? "" : typeof o === "string" ? o : (o[L] || o.en || o.ru || o.uz || ""));
function tx(o) {   // html; admin sees fallback marked
  if (!o) return ""; if (typeof o === "string") return esc(o);
  if (o[L]) return esc(o[L]);
  const f = o.en || o.ru || o.uz || "";
  return f && ADMIN ? `<span class="fb" title="${esc(t("missing"))}">${esc(f)}</span>` : esc(f);
}
const _CYR = { а:"a",б:"b",в:"v",г:"g",д:"d",е:"e",ё:"yo",ж:"j",з:"z",и:"i",й:"y",к:"k",л:"l",м:"m",н:"n",о:"o",п:"p",р:"r",с:"s",т:"t",у:"u",ф:"f",х:"x",ц:"ts",ч:"ch",ш:"sh",щ:"sh",ъ:"",ы:"i",ь:"",э:"e",ю:"yu",я:"ya",ў:"o",қ:"q",ғ:"g",ҳ:"h" };
const snorm = s => String(s ?? "").toLowerCase().replace(/[а-яёўқғҳ]/g, c => _CYR[c] ?? c).replace(/kh/g, "x").replace(/[’'`ʻʼ]/g, "").replace(/[^a-z0-9]+/g, "");
const locale = () => ({ en: "en-US", ru: "ru-RU", uz: "uz-Latn-UZ" }[L]);
const numf = (v, d = 2, mn = 0) => { try { return new Intl.NumberFormat(L === "uz" ? "ru-RU" : locale(), { minimumFractionDigits: mn, maximumFractionDigits: d }).format(v); } catch (_) { return String(v); } };
const pnum = v => v < 100 ? numf(v, 2, 2) : numf(v, 0);   // narx: 0.90, 2.30, 1 550
const dfmt = iso => iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : "";
const UZL = { ў: "o‘", ғ: "g‘", қ: "q", ҳ: "h", ш: "sh", ч: "ch", ё: "yo", ю: "yu", я: "ya", ц: "ts", х: "x", ъ: "’", ь: "", й: "y", ж: "j" };
function uzLat(s) {   // o'zbek kirill -> lotin (davlat nomlari bojxona bazasida kirillda)
  let out = "", prev = " ";
  for (const ch of String(s || "")) { const lo = ch.toLowerCase(); let r = lo === "е" && !/[а-яёўқғҳa-z]/i.test(prev) ? "ye" : (UZL[lo] ?? _CYR[lo] ?? ch);
    if (ch !== lo && r) r = r[0].toUpperCase() + r.slice(1); out += r; prev = ch; }
  return out;
}
let DN = null;
function country(iso, fallback) {
  const uzc = ((D.i18n || {}).countries || {})[iso];
  if (L === "uz" && (uzc || fallback)) return uzLat(uzc || fallback);
  if (!iso) return fallback || "";
  try { DN = DN && DN.l === L ? DN : Object.assign(new Intl.DisplayNames([L], { type: "region" }), { l: L }); const n = DN.of(iso); return n && n !== iso ? n : (fallback || iso); } catch (_) { return fallback || iso; }
}
const CUR = { USD: "$", EUR: "€", RUB: "₽", UZS: "soʻm", CNY: "¥" };
function money(v, cur) { const c = CUR[cur] || (cur || ""); const n = pnum(v); return c === "$" || c === "€" || c === "¥" ? c + n : n + " " + c; }
const unitName = u => tv((D.i18n.units || {})[u]) || u || "";
const catName = k => tv((D.i18n.cat1 || {})[k]) || k || "";
const subName = k => tv((D.i18n.cat2 || {})[k]) || k || "";
const distName = k => tv((D.i18n.districts || {})[k]) || "";
const catIcon = k => ((D.i18n.cat1 || {})[k] || {}).icon || "box";
function priceHTML(p, big) {
  if (p.price == null && p.price_to == null) return `<span class="price req">${esc(t("onRequest"))}</span>`;
  const a = p.price != null ? p.price : p.price_to;
  let s = money(a, p.cur);
  if (p.price != null && p.price_to != null && p.price_to !== p.price) s += "–" + pnum(p.price_to);
  const u = p.unit ? ` <small>/ ${esc(unitName(p.unit))}</small>` : "";
  const inc = p.inc && !big ? ` <small>${esc(p.inc)}</small>` : "";
  return `<span class="price">${esc(s)}${u}${inc}</span>`;
}

// ------------------------------------------------------------------ icons (original line icons)
const IC = {
  textile: "M8 3L3 6l2 4 3-1v12h8V9l3 1 2-4-5-3c-1 2-2.4 3-4 3S9 5 8 3z",
  yarn: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M5 9c4 1.2 10 1.2 14 0M3.6 13c5 1.6 11.8 1.6 16.8 0M6.5 18c3.2-1 7.8-1 11 0",
  food: "M6 8h12v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2zM8 4h8v4H8zM9 13h6",
  oil: "M12 3c3 4 6 7.5 6 11a6 6 0 0 1-12 0c0-3.5 3-7 6-11z",
  fruit: "M12 7.5c-1-2-3-3-5-2.2-3 1.2-4 5-2 9 1.5 3.5 4 5.2 5.5 5.2s1.5-.8 1.5-.8.1.8 1.5.8 4-1.7 5.5-5.2c2-4 1-7.8-2-9-2-.8-4 .2-5 2.2zM12 7.5c0-2 1-3.5 3-4.5",
  chem: "M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3M7.5 15h9",
  metal: "M3 17l3-8h12l3 8zM6 9l2-4h8l2 4",
  machine: "M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1",
  electric: "M13 2L4 14h7l-1 8 9-12h-7z",
  transport: "M2 6h11v10H2zM13 10h4l4 3v3h-8zM6 17a2 2 0 1 0 0 4a2 2 0 1 0 0-4M17 17a2 2 0 1 0 0 4a2 2 0 1 0 0-4",
  furniture: "M7 3h10v8H7zM5 11h14v3H5zM7 14v7M17 14v7",
  wood: "M12 3l6 8h-3l4 6H5l4-6H6zM12 17v4",
  box: "M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10",
  plastic: "M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10", paper: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7",
  glass: "M7 3h10l-1 8a4 4 0 0 1-8 0zM12 15v6M8 21h8", drink: "M7 3h10l-1 8a4 4 0 0 1-8 0zM12 15v6M8 21h8",
  pharma: "M9 3h6v6h6v6h-6v6H9v-6H3V9h6z", mineral: "M3 18l5-9 4 5 3-4 6 8z", stone: "M3 18l5-9 4 5 3-4 6 8z",
  leather: "M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2", hygiene: "M12 3c3 4 6 7.5 6 11a6 6 0 0 1-12 0c0-3.5 3-7 6-11zM10 15a2 2 0 0 0 2 2",
  animal: "M8 13c2-2 6-2 8 0s1 6-4 6-6-4-4-6zM6 8.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3M18 8.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3M10 4.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3M14 4.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3",
  toy: "M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z", home: "M3 11l9-7 9 7v10H3zM9 21v-6h6v6",
  plant: "M12 21V11M12 11c0-4 3-7 8-7 0 5-3 7-8 7zM12 14c0-3-2-5-7-5 0 4 2 5 7 5z", agro: "M12 21V11M12 11c0-4 3-7 8-7 0 5-3 7-8 7zM12 14c0-3-2-5-7-5 0 4 2 5 7 5z",
  shoe: "M3 16c0-2 1-6 2-8l4 2c2 1 4 2 7 2 3 0 5 1.5 5 4v2H3z", rubber: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  cotton: "M12 5.5a3 3 0 0 1 3 3 3 3 0 0 1 0 6 3 3 0 0 1-6 0 3 3 0 0 1 0-6 3 3 0 0 1 3-3zM12 14.5V21",
  oilp: "M12 3c3 4 6 7.5 6 11a6 6 0 0 1-12 0c0-3.5 3-7 6-11z",
  search: "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14M21 21l-5-5", list: "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
  plus: "M12 5v14M5 12h14", check: "M5 12l5 5L20 7", doc: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5", pin: "M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11zM12 7.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5",
  cal: "M4 5h16v16H4zM4 10h16M8 3v4M16 3v4", users: "M9 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8M2 21c0-4 3-6 7-6s7 2 7 6M17 11a3 3 0 1 0 0-6M22 21c0-3-2-5-5-5.5",
  globe: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M3 12h18M12 3c2.6 3 4 5.9 4 9s-1.4 6-4 9c-2.6-3-4-5.9-4-9s1.4-6 4-9z",
  print: "M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z", link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  filter: "M3 5h18l-7 8v6l-4 2v-8z", mail: "M3 5h18v14H3zM3 6l9 7 9-7", send: "M4 12l16-8-6 16-2-7z", shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4",
  factory: "M3 21V10l6 4V10l6 4V6h6v15z", ship: "M3 17l2 4h14l2-4zM5 17V9h14v8M9 9V5h6v4",
};
const svg = (k, cls = "") => `<svg viewBox="0 0 24 24" class="${cls}" aria-hidden="true" stroke-linecap="round" stroke-linejoin="round"><path d="${IC[k] || IC.box}"/></svg>`;
const MARK = `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 4l3.4 7.6L27 15l-7.6 3.4L16 26l-3.4-7.6L5 15l7.6-3.4z" fill="#E2B84F"/><path d="M16 10l1.6 3.6L21 15l-3.4 1.6L16 20l-1.6-3.4L11 15l3.4-1.4z" fill="#0E5C54"/></svg>`;

// ------------------------------------------------------------------ data index
const CO = {}, PR = {}, MARKETS = new Set();
const certified = c => (c.docs || []).some(d => ["certificate", "sanitary", "test"].includes(d.type));
function index() {
  Object.keys(CO).forEach(k => delete CO[k]); Object.keys(PR).forEach(k => delete PR[k]); MARKETS.clear();
  D.companies.forEach(c => CO[c.id] = c);
  D.products.forEach(p => { PR[p.id] = p; p._c = CO[p.c]; });
  D.products = D.products.filter(p => p._c);
  D.products.forEach(p => {
    const c = p._c;
    p._hay = snorm([...["name", "desc", "specs", "pack"].flatMap(f => LANGS.map(l => (p[f] || {})[l])), ...LANGS.map(l => (c.name || {})[l]), p.hs, p.sku,
      ...LANGS.map(l => ((D.i18n.cat1 || {})[p.cat1] || {})[l]), ...LANGS.map(l => ((D.i18n.cat2 || {})[p.cat2] || {})[l])].join(" "));
    p._cert = certified(c);
  });
  D.companies.forEach(c => ((c.export || {}).countries || []).forEach(x => x.iso && MARKETS.add(x.iso)));
}
index();

// ------------------------------------------------------------------ state
const S = { view: "products", cat1: "", cat2: "", dist: "", q: "", withPrice: false, cert: false, inc: "", sort: "featured", side: false };
let CART = store.get("bec-cart", []).filter(x => PR[x.id]);
const saveCart = () => { store.set("bec-cart", CART); const n = $("#cart-n"); if (n) { n.textContent = CART.length; n.hidden = !CART.length; } };
const inCart = id => CART.some(x => x.id === id);
function toggleCart(id, on) {
  const has = inCart(id);
  if (on === undefined ? has : !on) CART = CART.filter(x => x.id !== id); else if (!has) CART.push({ id, qty: "" });
  saveCart();
}
function toast(msg) { const el = document.createElement("div"); el.className = "toast"; el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2600); }

// ------------------------------------------------------------------ render: shell
function shell() {
  document.documentElement.lang = L === "uz" ? "uz-Latn" : L;
  document.title = tv(D.site.title) || "Bukhara Export Catalog";
  $("#app").innerHTML = `
  ${ADMIN ? `<div class="admin-bar"><div class="wrap"><b>${esc(t("preview"))}</b><span>${esc(t("previewText"))}</span></div></div>` : ""}
  <header class="hd"><div class="wrap">
    <button class="logo" id="go-home" aria-label="${esc(t("home"))}"><span class="mk">${MARK}</span><span><b>${esc(tv(D.site.title))}</b><span>${esc(t("brandSub"))}</span></span></button>
    <label class="hsearch">${svg("search")}<input id="q" type="search" placeholder="${esc(t("search"))}" value="${esc(S.q)}" autocomplete="off"></label>
    <div class="hact">
      <div class="lang" role="group" aria-label="Language">${LANGS.map(l => `<button data-l="${l}" class="${l === L ? "on" : ""}">${l.toUpperCase()}</button>`).join("")}</div>
      <button class="ibtn noprint" id="pdf" title="${esc(t("pdf"))}">${svg("print")}<span class="lbl">PDF</span></button>
      <button class="ibtn" id="cart">${svg("list")}<span class="lbl">${esc(t("inquiry"))}</span><span class="cnt" id="cart-n" ${CART.length ? "" : "hidden"}>${CART.length}</span></button>
    </div></div></header>
  <div id="page"></div>
  ${footer()}`;
  $("#go-home").onclick = () => { S.cat1 = S.cat2 = S.q = ""; nav("#/"); };
  $$(".lang button").forEach(b => b.onclick = () => { L = b.dataset.l; store.set("bec-lang", L); shell(); route(); });
  $("#pdf").onclick = () => nav("#/print");
  $("#cart").onclick = () => openInquiry();
  let tm; $("#q").addEventListener("input", e => { clearTimeout(tm); tm = setTimeout(() => { S.q = e.target.value; if (!/^#\/?$/.test(location.hash || "#/")) nav("#/"); else renderList(); }, 180); });
}
function footer() {
  const s = D.site, tel = s.phone ? s.phone.replace(/[^\d+]/g, "") : "";
  const lines = [s.email && `<a href="mailto:${esc(s.email)}">${esc(s.email)}</a>`, s.phone && `<a href="tel:${esc(tel)}">${esc(s.phone)}</a>`,
    s.telegram && `<a href="https://t.me/${esc(s.telegram.replace(/^@|https?:\/\/t\.me\//g, ""))}" target="_blank" rel="noopener">Telegram ${esc(s.telegram)}</a>`,
    s.whatsapp && `<a href="https://wa.me/${esc(s.whatsapp.replace(/\D/g, ""))}" target="_blank" rel="noopener">WhatsApp ${esc(s.whatsapp)}</a>`].filter(Boolean);
  return `<footer class="ftr noprint"><div class="wrap">
    <div><b>${esc(tv(s.title))}</b><div>${esc(t("catalogBy"))}: ${esc(tv(s.org))}</div><div class="small">${esc(t("updated"))}: ${dfmt((D.generated || "").slice(0, 10))}</div></div>
    <div><b>${esc(t("contacts"))}</b><div class="ln">${lines.length ? lines.join("") : `<span>${esc(t("noContact"))}</span>`}</div></div>
    <div><b>${esc(t("location"))}</b><div>${esc(tv(s.address))}</div></div>
  </div></footer>`;
}
function nav(h) { if (location.hash === h) route(); else location.hash = h; }

// ------------------------------------------------------------------ home + list
function home() {
  const cats = {}; D.products.forEach(p => { if (p.cat1) cats[p.cat1] = (cats[p.cat1] || 0) + 1; });
  const catKeys = Object.keys(cats).sort((a, b) => cats[b] - cats[a]);
  $("#page").innerHTML = `
  <section class="hero noprint"><div class="pat"></div><div class="wrap">
    <div><span class="eyebrow">${svg("globe", "")}${esc(t("heroEyebrow"))}</span>
      <h1>${esc(t("heroTitle"))}</h1><p>${esc(t("heroText"))}</p>
      <div class="cta"><a class="btn gold" href="#list">${esc(t("browse"))}</a><button class="btn" id="hero-inq">${svg("send")}${esc(t("sendInquiry"))}</button></div></div>
    <div class="stats">
      <div class="stat"><b>${D.products.length}</b><span>${esc(t("stProducts"))}</span></div>
      <div class="stat"><b>${D.companies.length}</b><span>${esc(t("stCompanies"))}</span></div>
      <div class="stat"><b>${catKeys.length}</b><span>${esc(t("stCategories"))}</span></div>
      <div class="stat"><b>${MARKETS.size}</b><span>${esc(t("stMarkets"))}</span></div>
    </div></div></section>
  ${catKeys.length ? `<div class="cats noprint"><div class="wrap"><div class="row">${catKeys.map(k => `<button class="cat ${S.cat1 === k ? "on" : ""}" data-c="${esc(k)}"><span class="ci">${svg(catIcon(k))}</span><span><b>${esc(catName(k))}</b><span>${esc(cats[k] === 1 ? t("productN1") : t("productsN", { n: cats[k] }))}</span></span></button>`).join("")}</div></div></div>` : ""}
  <main class="main" id="list"><div class="wrap">
    <div class="bar noprint">
      <div class="tabs" role="tablist"><button data-v="products" class="${S.view === "products" ? "on" : ""}">${esc(t("products"))}</button><button data-v="companies" class="${S.view === "companies" ? "on" : ""}">${esc(t("companies"))}</button></div>
      <button class="btn sm fbtn" id="fbtn">${svg("filter")}${esc(t("filters"))}</button>
      <span class="res" id="res"></span><span class="sp"></span>
      <select class="sel" id="sort" aria-label="Sort">${Object.entries(T[L].sort).map(([k, v]) => `<option value="${k}" ${S.sort === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
    </div>
    <div class="layout"><aside class="side ${S.side ? "open" : ""}" id="side"></aside><div id="results"></div></div>
  </div></main>`;
  $("#hero-inq").onclick = () => openInquiry();
  $$(".cat").forEach(b => b.onclick = () => { S.cat1 = S.cat1 === b.dataset.c ? "" : b.dataset.c; S.cat2 = ""; $$(".cat").forEach(x => x.classList.toggle("on", x.dataset.c === S.cat1)); renderList(); $("#list").scrollIntoView({ behavior: "smooth" }); });
  $$(".tabs button").forEach(b => b.onclick = () => { S.view = b.dataset.v; $$(".tabs button").forEach(x => x.classList.toggle("on", x === b)); $("#sort").hidden = S.view !== "products"; renderList(); });
  $("#sort").onchange = e => { S.sort = e.target.value; renderList(); };
  $("#sort").hidden = S.view !== "products";
  $("#fbtn").onclick = () => { S.side = !S.side; $("#side").classList.toggle("open", S.side); };
  renderList();
}
function filtered(ignore) {
  const qs = String(S.q || "").split(/\s+/).map(snorm).filter(Boolean);
  return D.products.filter(p => (ignore === "cat" || !S.cat1 || p.cat1 === S.cat1) && (ignore === "cat" || !S.cat2 || p.cat2 === S.cat2)
    && (ignore === "dist" || !S.dist || p._c.district === S.dist) && (!S.withPrice || p.price != null || p.price_to != null) && (!S.cert || p._cert)
    && (!S.inc || p.inc === S.inc || (!p.inc && (p._c.incoterms || []).includes(S.inc))) && qs.every(w => p._hay.includes(w)));
}
function renderSide() {
  const base = filtered("cat"), c1 = {}, c2 = {};
  base.forEach(p => { if (p.cat1) { c1[p.cat1] = (c1[p.cat1] || 0) + 1; if (p.cat1 === S.cat1 && p.cat2) c2[p.cat2] = (c2[p.cat2] || 0) + 1; } });
  const dl = {}; filtered("dist").forEach(p => { if (p._c.district) dl[p._c.district] = (dl[p._c.district] || 0) + 1; });
  const incs = [...new Set(D.products.flatMap(p => p.inc ? [p.inc] : (p._c.incoterms || [])))].sort();
  const act = S.cat1 || S.dist || S.withPrice || S.cert || S.inc || S.q;
  $("#side").innerHTML = `
  <div class="fgroup"><h4>${esc(t("category"))}</h4>
    <button class="fitem ${!S.cat1 ? "on" : ""}" data-c1="">${esc(t("all"))}<span class="n">${base.length}</span></button>
    ${Object.keys(c1).sort((a, b) => c1[b] - c1[a]).map(k => `<button class="fitem ${S.cat1 === k && !S.cat2 ? "on" : ""}" data-c1="${esc(k)}">${esc(catName(k))}<span class="n">${c1[k]}</span></button>
      ${S.cat1 === k ? Object.keys(c2).sort((a, b) => c2[b] - c2[a]).map(s => `<button class="fitem sub ${S.cat2 === s ? "on" : ""}" data-c2="${esc(s)}">${esc(subName(s))}<span class="n">${c2[s]}</span></button>`).join("") : ""}`).join("")}
  </div>
  ${Object.keys(dl).length > 1 || S.dist ? `<div class="fgroup"><h4>${esc(t("district"))}</h4>
    <button class="fitem ${!S.dist ? "on" : ""}" data-d="">${esc(t("allDistricts"))}</button>
    ${Object.keys(dl).sort((a, b) => distName(a).localeCompare(distName(b))).map(k => `<button class="fitem ${S.dist === k ? "on" : ""}" data-d="${k}">${esc(distName(k))}<span class="n">${dl[k]}</span></button>`).join("")}</div>` : ""}
  <div class="fgroup"><h4>${esc(t("options"))}</h4>
    <label class="chk"><input type="checkbox" id="f-price" ${S.withPrice ? "checked" : ""}>${esc(t("withPrice"))}</label>
    <label class="chk"><input type="checkbox" id="f-cert" ${S.cert ? "checked" : ""}>${esc(t("certified"))}</label></div>
  ${incs.length ? `<div class="fgroup"><h4>${esc(t("incoterms"))}</h4>${incs.map(i => `<button class="fitem ${S.inc === i ? "on" : ""}" data-i="${i}">${i}</button>`).join("")}</div>` : ""}
  ${act ? `<button class="clear" id="f-clear">✕ ${esc(t("clear"))}</button>` : ""}`;
  $$("#side [data-c1]").forEach(b => b.onclick = () => { S.cat1 = b.dataset.c1; S.cat2 = ""; $$(".cat").forEach(x => x.classList.toggle("on", x.dataset.c === S.cat1)); renderList(); });
  $$("#side [data-c2]").forEach(b => b.onclick = () => { S.cat2 = S.cat2 === b.dataset.c2 ? "" : b.dataset.c2; renderList(); });
  $$("#side [data-d]").forEach(b => b.onclick = () => { S.dist = b.dataset.d; renderList(); });
  $$("#side [data-i]").forEach(b => b.onclick = () => { S.inc = S.inc === b.dataset.i ? "" : b.dataset.i; renderList(); });
  $("#f-price").onchange = e => { S.withPrice = e.target.checked; renderList(); };
  $("#f-cert").onchange = e => { S.cert = e.target.checked; renderList(); };
  const cl = $("#f-clear"); if (cl) cl.onclick = () => { Object.assign(S, { cat1: "", cat2: "", dist: "", withPrice: false, cert: false, inc: "", q: "" }); $("#q").value = ""; $$(".cat").forEach(x => x.classList.remove("on")); renderList(); };
}
function sortP(arr) {
  const pv = p => p.price ?? p.price_to;
  const by = { featured: (a, b) => (b.featured - a.featured) || (b._c.featured - a._c.featured) || ((b.img.length > 0) - (a.img.length > 0)),
    priceAsc: (a, b) => (pv(a) == null) - (pv(b) == null) || (pv(a) - pv(b)), priceDesc: (a, b) => (pv(a) == null) - (pv(b) == null) || (pv(b) - pv(a)),
    name: (a, b) => tv(a.name).localeCompare(tv(b.name)), newest: (a, b) => String(b.updated || "").localeCompare(String(a.updated || "")) }[S.sort];
  return arr.slice().sort(by);
}
function renderList() {
  if (!$("#results")) return;
  renderSide();
  if (!D.products.length) { $("#results").innerHTML = `<div class="empty">${esc(t("nothingYet"))}</div>`; $("#res").textContent = ""; return; }
  if (S.view === "companies") {
    const ps = filtered(); const ids = new Set(ps.map(p => p.c));
    const cs = D.companies.filter(c => ids.has(c.id) || (!S.q && !S.cat1 && !S.dist && !S.withPrice && !S.cert && !S.inc));
    $("#res").textContent = `${cs.length} · ${t("companies")}`;
    $("#results").innerHTML = cs.length ? `<div class="cgrid">${cs.map(companyCard).join("")}</div>` : `<div class="empty">${esc(t("noResults"))}</div>`;
    $$("#results .cc").forEach(el => el.onclick = e => { if (e.target.closest(".edit")) return; nav("#/c/" + el.dataset.id); });
  } else {
    const ps = sortP(filtered());
    $("#res").textContent = ps.length === 1 ? t("productN1") : t("productsN", { n: ps.length });
    $("#results").innerHTML = ps.length ? `<div class="grid">${ps.map(productCard).join("")}</div>` : `<div class="empty">${esc(t("noResults"))}</div>`;
    wireCards($("#results"));
  }
  wireEdit($("#results"));
}
const phHTML = k => `<div class="ph">${svg(catIcon(k))}<span>${esc(t("photoSoon"))}</span></div>`;
function productCard(p) {
  const im = p.img[0];
  return `<article class="pc" data-id="${p.id}" tabindex="0">
    <div class="badges">${p.draft ? `<span class="tag dark">${esc(t("draft"))}</span>` : ""}${p._cert ? `<span class="tag teal">${svg("shield")}${esc(t("certifiedTag"))}</span>` : ""}</div>
    <button class="add ${inCart(p.id) ? "on" : ""}" data-add="${p.id}" title="${esc(inCart(p.id) ? t("inList") : t("addList"))}" aria-label="${esc(t("addList"))}">${svg(inCart(p.id) ? "check" : "plus")}</button>
    <div class="im">${im ? `<img loading="lazy" src="${esc(im.thumb)}" alt="${esc(tv(p.name))}">` : phHTML(p.cat1)}</div>
    <div class="bd"><div class="nm">${tx(p.name)}</div>
      <div class="co">${svg("factory")}<span>${tx(p._c.name)}</span></div>
      <div class="pr">${priceHTML(p)}</div>
      <div class="meta">${p.moq ? `<span class="tag">${esc(t("moq"))}: ${numf(p.moq)} ${esc(unitName(p.moq_unit || p.unit))}</span>` : ""}${p.expired ? `<span class="tag gold">${esc(t("indicative"))}</span>` : ""}</div>
    </div>${ADMIN ? `<button class="edit" data-edit-p="${p.id}" data-inn="${esc(p._c.inn || "")}">✎ ${esc(t("edit"))}</button>` : ""}</article>`;
}
const initials = c => (tv(c.name).replace(/[«»"“”]|LLC|ООО|MChJ/g, "").trim().split(/\s+/).slice(0, 2).map(w => w[0]).join("") || "•").toUpperCase();
function companyCard(c) {
  const ps = D.products.filter(p => p.c === c.id);
  return `<article class="cc" data-id="${esc(c.id)}" tabindex="0">
    <div class="cv ${c.cover ? "" : "pat"}" ${c.cover ? `style="background-image:url('${esc(c.cover.src)}')"` : ""}><div class="lg">${c.logo ? `<img src="${esc(c.logo.thumb)}" alt="">` : `<span class="ini">${esc(initials(c))}</span>`}</div></div>
    <div class="bd"><h3>${tx(c.name)} ${c.draft ? `<span class="tag dark">${esc(t("draft"))}</span>` : ""}</h3>
      <div class="tl">${tx(c.tagline) || tx(c.about)}</div>
      <div class="ft">${c.district ? `<span class="tag">${svg("pin")}${esc(distName(c.district))}</span>` : ""}<span class="tag">${esc(ps.length === 1 ? t("productN1") : t("productsN", { n: ps.length }))}</span>${certified(c) ? `<span class="tag teal">${svg("shield")}${esc(t("certifiedTag"))}</span>` : ""}</div>
      <div class="thumbs">${ps.filter(p => p.img[0]).slice(0, 5).map(p => `<img loading="lazy" src="${esc(p.img[0].thumb)}" alt="">`).join("")}</div>
    </div>${ADMIN ? `<button class="edit" data-edit-c="${esc(c.inn || "")}">✎ ${esc(t("edit"))}</button>` : ""}</article>`;
}
function wireCards(root) {
  $$(".pc", root).forEach(el => {
    el.onclick = e => { if (e.target.closest(".add,.edit")) return; nav("#/p/" + el.dataset.id); };
    el.onkeydown = e => { if (e.key === "Enter") nav("#/p/" + el.dataset.id); };
  });
  $$("[data-add]", root).forEach(b => b.onclick = e => { e.stopPropagation(); const id = +b.dataset.add; toggleCart(id); const on = inCart(id);
    b.classList.toggle("on", on); b.innerHTML = svg(on ? "check" : "plus"); b.title = on ? t("inList") : t("addList"); if (on) toast(t("inList")); });
}
function wireEdit(root) {
  if (!ADMIN) return;
  $$("[data-edit-p]", root).forEach(b => b.onclick = e => { e.stopPropagation(); parent.postMessage({ type: "bec-edit", inn: b.dataset.inn, product: +b.dataset.editP }, "*"); });
  $$("[data-edit-c]", root).forEach(b => b.onclick = e => { e.stopPropagation(); parent.postMessage({ type: "bec-edit", inn: b.dataset.editC }, "*"); });
}

// ------------------------------------------------------------------ product page
function specRows(txt) {
  return String(txt || "").split(/\n+/).map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(/^([^:]{1,60}):\s*(.+)$/); return m ? `<tr><th>${esc(m[1])}</th><td>${esc(m[2])}</td></tr>` : `<tr><td colspan="2">${esc(s)}</td></tr>`; }).join("");
}
function docCards(docs) {
  return docs.map(d => `<a class="doc" href="${esc(d.src)}" target="_blank" rel="noopener"><span class="di">${svg("doc")}</span><span><b>${esc(d.title)}</b><span>${esc(tv((D.i18n.doc_types || {})[d.type]))}${d.valid_until ? " · " + esc(t("validTo", { d: dfmt(d.valid_until) })) : ""}</span></span></a>`).join("");
}
function productPage(id) {
  const p = PR[id]; if (!p || !p._c) return nav("#/");
  const c = p._c, imgs = p.img;
  const note = p.expired ? `${t("indicative")} · ${t("asOf", { d: dfmt(p.price_date || p.price_valid) })}` : p.price_valid ? t("validUntil", { d: dfmt(p.price_valid) }) : p.price_date ? t("asOf", { d: dfmt(p.price_date) }) : "";
  const facts = [[t("hs"), p.hs && `<span class="mono">${esc(p.hs)}</span>`], [t("moq"), p.moq && `${numf(p.moq)} ${esc(unitName(p.moq_unit || p.unit))}`], [t("incoterm"), esc(p.inc || (c.incoterms || []).join(", "))],
    [t("packaging"), tx(p.pack)], [t("capacity"), tx(p.capacity)], [t("lead"), tx(p.lead)], [t("sku"), esc(p.sku || "")], [t("payment"), esc((c.payment || []).map(x => tv((D.i18n.payment || {})[x])).join(", "))]].filter(x => x[1]);
  const docs = (c.docs || []).filter(d => !d.product || d.product === p.id);
  const more = D.products.filter(x => x.c === c.id && x.id !== p.id);
  $("#page").innerHTML = `<main class="main"><div class="wrap">
    <nav class="crumbs noprint"><button data-h="#/">${esc(t("home"))}</button>${p.cat1 ? `<span>›</span><button data-cat="${esc(p.cat1)}">${esc(catName(p.cat1))}</button>` : ""}${p.cat2 ? `<span>›</span><button data-cat="${esc(p.cat1)}" data-sub="${esc(p.cat2)}">${esc(subName(p.cat2))}</button>` : ""}</nav>
    <div class="pd">
      <div class="gal"><div class="big" id="big">${imgs[0] ? `<img src="${esc(imgs[0].src)}" alt="${esc(tv(p.name))}">` : phHTML(p.cat1)}</div>
        ${imgs.length > 1 ? `<div class="th">${imgs.map((m, i) => `<button data-i="${i}" class="${i ? "" : "on"}"><img src="${esc(m.thumb)}" alt=""></button>`).join("")}</div>` : ""}</div>
      <div class="pinfo">
        <div style="display:flex;gap:6px;flex-wrap:wrap">${p.cat2 ? `<span class="tag teal">${esc(subName(p.cat2))}</span>` : ""}${p.draft ? `<span class="tag dark">${esc(t("draft"))}</span>` : ""}${p._cert ? `<span class="tag teal">${svg("shield")}${esc(t("certifiedTag"))}</span>` : ""}</div>
        <h1>${tx(p.name)}</h1>
        <button class="by" data-h="#/c/${esc(c.id)}"><span class="lg">${c.logo ? `<img src="${esc(c.logo.thumb)}" alt="">` : `<span class="ini">${esc(initials(c))}</span>`}</span><span><b>${tx(c.name)}</b><span>${esc(distName(c.district))}${c.district ? ", " : ""}${esc(L === "ru" ? "Бухарская обл." : L === "uz" ? "Buxoro vil." : "Bukhara region")}</span></span></button>
        <div class="pbox">${priceHTML(p, true)}${p.inc ? ` <span class="tag">${esc(p.inc)}</span>` : ""}
          ${note ? `<div class="note">${esc(note)}</div>` : ""}
          <div class="acts noprint"><button class="btn pri" id="rq">${svg("send")}${esc(t("requestQuote"))}</button><button class="btn" id="al">${svg(inCart(p.id) ? "check" : "plus")}<span>${esc(inCart(p.id) ? t("inList") : t("addList"))}</span></button><button class="btn" id="sh" title="${esc(t("share"))}">${svg("link")}</button>
          ${ADMIN ? `<button class="btn" data-edit-p="${p.id}" data-inn="${esc(c.inn || "")}">✎ ${esc(t("edit"))}</button>` : ""}</div></div>
        ${facts.length ? `<dl class="facts">${facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>` : ""}
      </div></div>
    ${tv(p.desc) ? `<section class="sec"><h2>${esc(t("description"))}</h2><div class="prose">${tx(p.desc)}</div></section>` : ""}
    ${tv(p.specs) ? `<section class="sec"><h2>${esc(t("specs"))}</h2><table class="spec">${specRows(tv(p.specs))}</table></section>` : ""}
    ${docs.length ? `<section class="sec"><h2>${esc(t("documents"))}</h2><div class="docs">${docCards(docs)}</div></section>` : ""}
    ${more.length ? `<section class="sec"><h2>${esc(t("more"))}</h2><div class="grid">${more.slice(0, 8).map(productCard).join("")}</div></section>` : ""}
  </div></main>`;
  $$("[data-h]").forEach(b => b.onclick = () => nav(b.dataset.h));
  $$("[data-cat]").forEach(b => b.onclick = () => { S.cat1 = b.dataset.cat; S.cat2 = b.dataset.sub || ""; S.view = "products"; nav("#/"); });
  $$(".th button").forEach(b => b.onclick = () => { $$(".th button").forEach(x => x.classList.toggle("on", x === b)); $("#big").innerHTML = `<img src="${esc(imgs[+b.dataset.i].src)}" alt="">`; $("#big").dataset.i = b.dataset.i; });
  if (imgs[0]) $("#big").onclick = () => lightbox(imgs, +($("#big").dataset.i || 0));
  $("#rq").onclick = () => { toggleCart(p.id, true); openInquiry(); };
  $("#al").onclick = () => { toggleCart(p.id); const on = inCart(p.id); $("#al").innerHTML = `${svg(on ? "check" : "plus")}<span>${esc(on ? t("inList") : t("addList"))}</span>`; };
  $("#sh").onclick = () => copy(location.href, t("copied"));
  wireCards($("#page")); wireEdit($("#page"));
  document.title = tv(p.name) + " — " + tv(c.name);
}

// ------------------------------------------------------------------ company page
function companyPage(slug) {
  const c = CO[slug]; if (!c) return nav("#/");
  const ps = D.products.filter(p => p.c === c.id);
  const kv = [[t("location"), esc(distName(c.district))], [t("founded"), c.founded], [t("employees"), c.employees && numf(c.employees, 0)], [t("tin"), c.tin && `<span class="mono">${esc(c.tin)}</span>`],
    [t("capacity"), tx(c.capacity)], [t("incoterms"), esc((c.incoterms || []).join(", "))], [t("payment"), esc((c.payment || []).map(x => tv((D.i18n.payment || {})[x])).join(", "))]].filter(x => x[1]);
  const exp = (c.export.countries || []), tgt = c.markets || [];
  $("#page").innerHTML = `<main class="main"><div class="wrap">
    <nav class="crumbs noprint"><button data-h="#/">${esc(t("home"))}</button><span>›</span><button data-v="companies">${esc(t("companies"))}</button></nav>
    <section class="chero"><div class="cv ${c.cover ? "" : "pat"}" ${c.cover ? `style="background-image:url('${esc(c.cover.src)}')"` : ""}></div>
      <div class="in"><div class="lg">${c.logo ? `<img src="${esc(c.logo.src)}" alt="${esc(tv(c.name))}">` : `<span class="ini">${esc(initials(c))}</span>`}</div>
        <div><h1>${tx(c.name)} ${c.draft ? `<span class="tag dark">${esc(t("draft"))}</span>` : ""}</h1><div class="tl">${tx(c.tagline)}</div>
          <div class="chips">${c.district ? `<span class="tag">${svg("pin")}${esc(distName(c.district))}</span>` : ""}${c.founded ? `<span class="tag">${svg("cal")}${esc(t("est", { y: c.founded }))}</span>` : ""}${c.employees ? `<span class="tag">${svg("users")}${esc(t("people", { n: numf(c.employees, 0) }))}</span>` : ""}${certified(c) ? `<span class="tag teal">${svg("shield")}${esc(t("certifiedTag"))}</span>` : ""}${exp.length ? `<span class="tag gold">${svg("ship")}${exp.length} ${esc(t("stMarkets"))}</span>` : ""}</div></div>
        <div class="noprint" style="display:flex;gap:8px"><button class="btn pri" id="c-inq">${svg("send")}${esc(t("sendInquiry"))}</button>${ADMIN ? `<button class="btn" data-edit-c="${esc(c.inn || "")}">✎ ${esc(t("edit"))}</button>` : ""}</div></div></section>
    <div class="cbody"><div>
      ${tv(c.about) ? `<section class="sec" style="margin-top:0"><h2>${esc(t("about"))}</h2><div class="prose">${tx(c.about)}</div></section>` : ""}
      <section class="sec"><h2>${esc(t("products"))} <span class="faint" style="font-weight:400;font-size:15px">· ${ps.length}</span></h2><div class="grid">${ps.map(productCard).join("")}</div></section>
      ${c.gallery.length ? `<section class="sec"><h2>${esc(t("gallery"))}</h2><div class="ggrid">${c.gallery.map((m, i) => `<button data-g="${i}" title="${esc(m.title)}"><img loading="lazy" src="${esc(m.thumb)}" alt="${esc(m.title)}"></button>`).join("")}</div></section>` : ""}
      ${c.docs.length ? `<section class="sec"><h2>${esc(t("documents"))}</h2><div class="docs">${docCards(c.docs)}</div></section>` : ""}
    </div><aside style="display:flex;flex-direction:column;gap:14px">
      ${kv.length ? `<div class="card"><h3>${esc(t("facts"))}</h3><dl class="kv">${kv.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl></div>` : ""}
      ${exp.length ? `<div class="card"><h3>${esc(t("markets"))}</h3><div class="flags">${exp.map(x => `<span class="flag"><i>${esc(x.iso || "··")}</i>${esc(country(x.iso, x.name))}</span>`).join("")}</div><p class="faint" style="font-size:12px;margin:10px 0 0">${esc(t("marketsNote"))}</p></div>` : ""}
      ${tgt.length ? `<div class="card"><h3>${esc(t("targetMarkets"))}</h3><div class="flags">${tgt.map(x => `<span class="flag"><i>${esc(x)}</i>${esc(country(x, x))}</span>`).join("")}</div></div>` : ""}
      <div class="ctabox noprint"><h3>${esc(t("contactVia"))}</h3><p>${esc(t("contactViaText", { org: tv(D.site.org) }))}</p><button class="btn gold" id="c-inq2">${svg("send")}${esc(t("sendInquiry"))}</button></div>
    </aside></div>
  </div></main>`;
  $$("[data-h]").forEach(b => b.onclick = () => nav(b.dataset.h));
  $$("[data-v]").forEach(b => b.onclick = () => { S.view = b.dataset.v; nav("#/"); });
  $$("[data-g]").forEach(b => b.onclick = () => lightbox(c.gallery, +b.dataset.g));
  const inq = () => openInquiry(c); $("#c-inq").onclick = inq; $("#c-inq2").onclick = inq;
  wireCards($("#page")); wireEdit($("#page"));
  document.title = tv(c.name) + " — " + tv(D.site.title);
}

// ------------------------------------------------------------------ inquiry drawer
function inquiryText(f, about) {
  const lines = [t("subject"), "", about ? t("aboutInquiry", { c: tv(about.name) }) : "", `${t("name")}: ${f.name}`, f.company && `${t("company")}: ${f.company}`, f.country && `${t("country")}: ${f.country}`,
    f.email && `${t("email")}: ${f.email}`, f.phone && `${t("phone")}: ${f.phone}`, ""];
  CART.forEach((x, i) => { const p = PR[x.id]; if (p) lines.push(`${i + 1}. ${tv(p.name)} — ${tv(p._c.name)}${p.hs ? " (HS " + p.hs + ")" : ""}${x.qty ? " — " + x.qty : ""} [#${p.id}]`); });
  if (f.message) lines.push("", f.message);
  return lines.filter(x => x !== false && x !== undefined && x !== null).join("\n").replace(/\n{3,}/g, "\n\n");
}
function openInquiry(about) {
  const f0 = store.get("bec-buyer", {});
  const o = document.createElement("div"); o.className = "ovl"; o.innerHTML = `<div class="drawer" role="dialog" aria-modal="true" aria-label="${esc(t("inquiry"))}">
    <header><h2>${esc(about ? t("aboutInquiry", { c: tv(about.name) }) : t("inquiry"))}</h2><button class="x" aria-label="Close">×</button></header>
    <div class="body"><p class="muted" style="margin-top:0">${esc(t("inquiryIntro"))}</p><div id="qlist"></div>
      <h3 style="margin:20px 0 0;font-size:15px">${esc(t("yourDetails"))}</h3>
      <div class="form">
        <label>${esc(t("name"))} *<input name="name" value="${esc(f0.name || "")}" autocomplete="name"></label>
        <label>${esc(t("company"))}<input name="company" value="${esc(f0.company || "")}" autocomplete="organization"></label>
        <label>${esc(t("country"))}<input name="country" value="${esc(f0.country || "")}" autocomplete="country-name"></label>
        <label>${esc(t("email"))}<input name="email" type="email" value="${esc(f0.email || "")}" autocomplete="email"></label>
        <label class="w">${esc(t("phone"))}<input name="phone" value="${esc(f0.phone || "")}" autocomplete="tel"></label>
        <label class="w">${esc(t("message"))}<textarea name="message"></textarea></label>
      </div><div id="qres" style="margin-top:14px"></div></div>
    <footer><button class="btn pri" id="qsend">${svg("send")}${esc(t("send"))}</button><span class="via" id="qvia"></span></footer></div>`;
  document.body.appendChild(o);
  const close = () => { o.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = e => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  o.onclick = e => { if (e.target === o) close(); }; $(".x", o).onclick = close;
  const drawList = () => {
    $("#qlist", o).innerHTML = CART.length ? CART.map(x => { const p = PR[x.id]; const im = p.img[0];
      return `<div class="qitem">${im ? `<img src="${esc(im.thumb)}" alt="">` : `<div class="ph">${svg(catIcon(p.cat1))}</div>`}<div><b>${tx(p.name)}</b><span>${tx(p._c.name)}</span><br><button class="rm" data-rm="${p.id}">${esc(t("remove"))}</button></div>
        <input data-q="${p.id}" value="${esc(x.qty || "")}" placeholder="${esc(t("qty"))}"></div>`; }).join("") : `<div class="empty" style="padding:24px">${esc(t("emptyList"))}</div>`;
    $$("[data-rm]", o).forEach(b => b.onclick = () => { toggleCart(+b.dataset.rm, false); drawList(); });
    $$("[data-q]", o).forEach(i => i.oninput = () => { const it = CART.find(x => x.id === +i.dataset.q); if (it) { it.qty = i.value; saveCart(); } });
  };
  drawList();
  const s = D.site;
  const vals = () => Object.fromEntries($$(".form input, .form textarea", o).map(i => [i.name, i.value.trim()]));
  const via = [];
  if (s.email) via.push(`<a href="#" data-via="mail">${esc(t("viaEmail"))}</a>`);
  if (s.whatsapp) via.push(`<a href="#" data-via="wa">${esc(t("viaWhatsApp"))}</a>`);
  if (s.telegram) via.push(`<a href="#" data-via="tg">${esc(t("viaTelegram"))}</a>`);
  $("#qvia", o).innerHTML = via.length ? `${esc(t("orSendVia"))} ${via.join(" · ")}` : "";
  const check = f => { if (!f.name || !(f.email || f.phone)) { $("#qres", o).innerHTML = `<div class="tag bad" style="padding:8px 12px;font-size:13px">${esc(t("required"))}</div>`; return false; } store.set("bec-buyer", { ...f, message: "" }); return true; };
  $$("[data-via]", o).forEach(a => a.onclick = e => {
    e.preventDefault(); const f = vals(); if (!check(f)) return; const txt = inquiryText(f, about);
    if (a.dataset.via === "mail") location.href = `mailto:${encodeURIComponent(s.email)}?subject=${encodeURIComponent(t("subject"))}&body=${encodeURIComponent(txt)}`;
    if (a.dataset.via === "wa") window.open(`https://wa.me/${s.whatsapp.replace(/\D/g, "")}?text=${encodeURIComponent(txt)}`, "_blank", "noopener");
    if (a.dataset.via === "tg") { copy(txt, t("msgCopied")); window.open(`https://t.me/${s.telegram.replace(/^@|https?:\/\/t\.me\//g, "")}`, "_blank", "noopener"); }
  });
  $("#qsend", o).onclick = async () => {
    const f = vals(); if (!check(f)) return;
    const payload = { ...f, lang: L, source: about ? tv(about.name) : "", items: CART.map(x => ({ id: x.id, qty: x.qty })), text: inquiryText(f, about) };
    const btn = $("#qsend", o); btn.disabled = true;
    try {
      if (LOCAL) { const r = await fetch("/api/catalog/inquiry/public", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); if (!r.ok) throw new Error((await r.json()).error || r.status); }
      else if (s.form_url) { const r = await fetch(s.form_url, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) }); if (!r.ok) throw new Error(r.status); }
      else if (s.email) { location.href = `mailto:${encodeURIComponent(s.email)}?subject=${encodeURIComponent(t("subject"))}&body=${encodeURIComponent(payload.text)}`; }
      else { copy(payload.text, t("msgCopied")); btn.disabled = false; return; }
      $("#qres", o).innerHTML = `<div class="okmsg">${esc(t("sent"))}</div>`; CART = []; saveCart(); drawList();
    } catch (e) { $("#qres", o).innerHTML = `<div class="tag bad" style="padding:8px 12px;font-size:13px">${esc(String(e.message || e))}</div>`; }
    btn.disabled = false;
  };
  setTimeout(() => { const i = $(".form input[name=name]", o); if (i && !i.value) i.focus(); }, 60);
}

// ------------------------------------------------------------------ print (PDF catalog)
function printPage() {
  const byC = D.companies.map(c => ({ c, ps: D.products.filter(p => p.c === c.id) })).filter(x => x.ps.length);
  $("#page").innerHTML = `<main class="main"><div class="wrap">
    <div class="noprint" style="display:flex;gap:10px;margin-bottom:16px"><button class="btn" data-h="#/">← ${esc(t("back"))}</button><button class="btn pri" id="pp">${svg("print")}${esc(t("printBtn"))}</button></div>
    <div class="pcover"><h1>${esc(tv(D.site.title))}</h1><div class="muted">${esc(tv(D.site.org))}</div>
      <div class="faint" style="margin-top:6px">${[D.site.email, D.site.phone, D.site.site_url].filter(Boolean).map(esc).join(" · ")} · ${esc(t("updated"))}: ${dfmt((D.generated || "").slice(0, 10))}</div></div>
    ${byC.map(({ c, ps }) => `<section class="pcomp"><div class="ph1">${c.logo ? `<img src="${esc(c.logo.thumb)}" alt="">` : ""}<div><h2>${tx(c.name)}</h2><div class="muted">${esc(distName(c.district))}${c.founded ? " · " + esc(t("est", { y: c.founded })) : ""}${(c.export.countries || []).length ? " · " + esc(t("markets")) + ": " + esc(c.export.countries.slice(0, 8).map(x => country(x.iso, x.name)).join(", ")) : ""}</div></div></div>
      ${tv(c.about) ? `<p class="prose" style="font-size:13px">${esc(tv(c.about).slice(0, 700))}${tv(c.about).length > 700 ? "…" : ""}</p>` : ""}
      <div class="pgrid">${ps.map(p => `<div class="pcard">${p.img[0] ? `<img src="${esc(p.img[0].thumb)}" alt="">` : ""}<b>${tx(p.name)}</b><div>${priceHTML(p)}</div><div class="faint" style="font-size:11px">${[p.hs && "HS " + p.hs, p.moq && t("moq") + ": " + numf(p.moq) + " " + unitName(p.moq_unit || p.unit)].filter(Boolean).map(esc).join(" · ")}</div></div>`).join("")}</div></section>`).join("")}
  </div></main>`;
  $$("[data-h]").forEach(b => b.onclick = () => nav(b.dataset.h));
  $("#pp").onclick = () => window.print();
}

// ------------------------------------------------------------------ misc
function lightbox(list, i) {
  const o = document.createElement("div"); o.className = "lb";
  const draw = () => { o.innerHTML = `<img src="${esc(list[i].src)}" alt="${esc(list[i].title || "")}"><button class="x" aria-label="Close">×</button>${list.length > 1 ? `<button class="nav l">‹</button><button class="nav r">›</button>` : ""}`;
    $(".x", o).onclick = close; const l = $(".nav.l", o), r = $(".nav.r", o);
    if (l) { l.onclick = e => { e.stopPropagation(); i = (i + list.length - 1) % list.length; draw(); }; r.onclick = e => { e.stopPropagation(); i = (i + 1) % list.length; draw(); }; } };
  const close = () => { o.remove(); document.removeEventListener("keydown", key); };
  const key = e => { if (e.key === "Escape") close(); if (e.key === "ArrowRight" && list.length > 1) { i = (i + 1) % list.length; draw(); } if (e.key === "ArrowLeft" && list.length > 1) { i = (i + list.length - 1) % list.length; draw(); } };
  o.onclick = e => { if (e.target === o) close(); };
  document.addEventListener("keydown", key); draw(); document.body.appendChild(o);
}
function copy(text, msg) {
  const done = () => toast(msg);
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback); else fallback();
  function fallback() { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (_) {} ta.remove(); }
}
function route() {
  const h = location.hash || "#/";
  let m;
  if ((m = h.match(/^#\/p\/(\d+)/))) productPage(+m[1]);
  else if ((m = h.match(/^#\/c\/([\w-]+)/))) companyPage(m[1]);
  else if (h.startsWith("#/print")) printPage();
  else { home(); document.title = tv(D.site.title) || "Bukhara Export Catalog"; }
  window.scrollTo(0, 0);
}
async function boot() {
  if (ADMIN && LOCAL) {   // preview inside the app: drafts too
    try { const r = await fetch("/api/catalog/public?admin=1", { cache: "no-store" }); if (r.ok) { Object.assign(D, await r.json()); index(); } } catch (_) {}
  }
  CART = CART.filter(x => PR[x.id]);
  shell(); route();
  window.addEventListener("hashchange", route);
  window.addEventListener("message", e => { if (e.data && e.data.type === "bec-reload") location.reload(); });
}
boot();
})();
