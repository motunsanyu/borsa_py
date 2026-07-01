import requests
import os
import re
import time
from datetime import datetime
from html import escape, unescape
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

COMPANY_NAMES = {
    "ASELS": "ASELSAN",
}

DETAIL_LABELS = [
    "Son İşlem Fiyatı",
    "Alış",
    "Satış",
    "Günlük Değişim",
    "Günlük Değişim (%)",
    "Günlük Hacim (Lot)",
    "Günlük Hacim (TL)",
    "Günlük Ortalama",
    "Gün İçi En Düşük",
    "Gün İçi En Yüksek",
    "Açılış Fiyatı",
    "Önceki Kapanış Fiyatı",
    "Alt Marj Fiyatı",
    "Üst Marj Fiyatı",
    "20 Günlük Ortalama",
    "52 Günlük Ortalama",
    "Haftalık En Düşük",
    "Haftalık En Yüksek",
    "Aylık En Düşük",
    "Aylık En Yüksek",
    "Yıllık En Düşük",
    "Yıllık En Yüksek",
    "Baz Fiyatı",
]

TRADINGVIEW_COLUMNS = [
    "close",
    "RSI",
    "RSI[1]",
    "MACD.macd",
    "MACD.signal",
    "ADX",
    "BB.upper",
    "BB.lower",
    "SMA5",
    "SMA20",
    "SMA50",
    "EMA20",
    "EMA50",
    "Stoch.K",
    "Stoch.D",
    "High.1M",
    "Low.1M",
    "High.3M",
    "Low.3M",
    "volume",
    "Recommend.All",
]

MONTHS_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

SEP = "━━━━━━━━━━━━━━━━━━━━"

# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────────────────

def normalize_detail_link(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""

    if not link.startswith("http"):
        link = "https://finans.mynet.com/" + link.lstrip("/")

    parsed = urlparse(link)
    path_parts = [part for part in parsed.path.split("/") if part]

    if "hisseler" in path_parts:
        slug = path_parts[-1]
        return f"https://finans.mynet.com/borsa/hisseler/{slug}/"

    return link


def parse_tr_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip().replace("%", "")
    value = re.sub(r"[^0-9,\.\-]", "", value)
    if not value:
        return None

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    elif value.count(".") > 1:
        value = value.replace(".", "")

    try:
        return float(value)
    except ValueError:
        return None


def format_tr_number(value, digits: int = 2) -> str:
    if value is None:
        return "-"

    formatted = f"{value:,.{digits}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_report_date() -> str:
    if ZoneInfo:
        now = datetime.now(ZoneInfo("Europe/Istanbul"))
    else:
        now = datetime.now()

    return f"{now.day:02d} {MONTHS_TR[now.month]} {now.year}"


def format_report_time() -> str:
    if ZoneInfo:
        now = datetime.now(ZoneInfo("Europe/Istanbul"))
    else:
        now = datetime.now()

    return f"{now.hour:02d}:{now.minute:02d}"


def format_compact_tr(value) -> str:
    number = parse_tr_number(value)
    if number is None:
        return safe_text(value)

    absolute_number = abs(number)
    if absolute_number >= 1_000_000_000:
        return f"{format_tr_number(number / 1_000_000_000)} B"
    if absolute_number >= 1_000_000:
        return f"{format_tr_number(number / 1_000_000)} M"
    if absolute_number >= 1_000:
        return f"{format_tr_number(number / 1_000)} B"
    return format_tr_number(number)


def strip_html_to_lines(html: str) -> list[str]:
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"</(p|div|li|tr|td|th|span|strong|h1|h2|h3|h4)>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    text = unescape(html)
    lines = []

    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    return lines


def safe_text(value) -> str:
    if value is None:
        return "-"
    return escape(str(value))


def change_direction(change_value) -> str:
    change = parse_tr_number(change_value)
    if change is None:
        return "flat"
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"


def change_icon_for_change(change_value) -> str:
    direction = change_direction(change_value)
    if direction == "up":
        return "📈"
    if direction == "down":
        return "📉"
    return "📊"


def change_report_value(change_value) -> str:
    change = parse_tr_number(change_value)
    if change is None:
        return safe_text(change_value)
    if change > 0:
        return f"(▲ +{format_tr_number(abs(change))}%)"
    if change < 0:
        return f"(▼ {format_tr_number(abs(change))}%)"
    return f"({format_tr_number(change)}%)"


# ─── Veri Çekme ───────────────────────────────────────────────────────────────

def fetch_stock_details(stock: dict) -> dict:
    detail_link = stock.get("detail_link", "")
    if not detail_link.startswith("http"):
        return {}

    try:
        response = requests.get(detail_link, headers=HEADERS, timeout=8)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching detail page: {e}")
        return {}

    lines = strip_html_to_lines(response.text)
    details = {}

    for index, line in enumerate(lines):
        if line in DETAIL_LABELS and index + 1 < len(lines):
            details[line] = lines[index + 1]

    return details


def fetch_tradingview_indicators(symbol: str) -> dict:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    payload = {
        "symbols": {"tickers": [f"BIST:{symbol}"], "query": {"types": []}},
        "columns": TRADINGVIEW_COLUMNS,
    }

    try:
        response = requests.post(
            "https://scanner.tradingview.com/turkey/scan",
            headers={**HEADERS, "Content-Type": "application/json"},
            json=payload,
            timeout=8,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as e:
        print(f"Error fetching TradingView indicators: {e}")
        return {}

    if not data:
        return {}

    values = data[0].get("d", [])
    return {
        column: values[index]
        for index, column in enumerate(TRADINGVIEW_COLUMNS)
        if index < len(values)
    }


# ─── Borsa Scraper ────────────────────────────────────────────────────────────

def scrape_borsa():
    url = "https://finans.mynet.com/borsa/canliborsa/?plist=finans-canliborsa-button"

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

    text = response.text

    if '|_|' not in text:
        print("Could not find the data separator '|_|'. The page structure might have changed.")
        return []

    raw_items = text.split('|_|')
    data_list = []

    for item in raw_items:
        parts = item.split('|')
        if len(parts) >= 16:
            try:
                symbol = parts[13].strip()
                price = parts[1].strip()
                high = parts[2].strip()
                low = parts[3].strip()
                change = parts[4].strip()
                time_str = parts[5].strip()
                aof = parts[10].strip()
                vol_lot = parts[11].strip()
                vol_tl = parts[12].strip()
                link = normalize_detail_link(parts[15])

                if symbol and price:
                    # Borsa açılmadan önceki sıfırlanmış fiyatları veritabanına yazmamak için:
                    if price in ["0", "0,00", "0.00", "0.0", "0,0", "-", ""]:
                        continue

                    data_list.append({
                        "symbol": symbol,
                        "name": symbol,
                        "price": price,
                        "change_percentage": change,
                        "time": time_str,
                        "detail_link": link,
                        "high": high,
                        "low": low,
                        "aof": aof,
                        "volume_lot": vol_lot,
                        "volume_tl": vol_tl,
                        "updated_at": "now()"
                    })
            except Exception as e:
                print(f"Error parsing item: {e}")
                continue

    return data_list


def get_stock(symbol: str):
    wanted_symbol = symbol.strip().upper()
    if not wanted_symbol:
        return None

    for stock in scrape_borsa():
        if stock.get("symbol", "").upper() == wanted_symbol:
            return stock

    return None


def get_company_name(stock: dict) -> str:
    symbol = stock.get("symbol", "").upper()
    if symbol in COMPANY_NAMES:
        return COMPANY_NAMES[symbol]

    detail_link = stock.get("detail_link", "")
    slug = urlparse(detail_link).path.strip("/").split("/")[-1]
    parts = [part for part in slug.split("-") if part]

    if len(parts) > 1:
        return " ".join(parts[1:]).upper()

    return stock.get("name") or symbol


# ─── Teknik Analiz – Hesaplamalar ────────────────────────────────────────────

def tv_number(indicators: dict, label: str):
    return parse_tr_number(indicators.get(label))


def detail_number(details: dict, label: str):
    return parse_tr_number(details.get(label))


def trend_summary(score: int) -> str:
    if score >= 3:
        return "Güçlü Pozitif – Alıcılar kontrolde"
    if score >= 1:
        return "Orta Vadede Pozitif – Kısa vadede alıcı güçlü"
    if score <= -3:
        return "Güçlü Negatif – Satış baskısı ağır basıyor"
    if score <= -1:
        return "Orta Vadede Negatif – Kısa vadede baskı sürüyor"
    return "Kararsız – Yatay bant hareketi izleniyor"


def rsi_comment(rsi: float | None, rsi_prev: float | None) -> tuple[str, int]:
    """RSI yorumu ve skor katkısı döndürür."""
    if rsi is None:
        return "-", 0
    score = 0
    direction = ""
    if rsi_prev is not None:
        direction = ", RSI yükseliyor" if rsi > rsi_prev else ", RSI geriliyor"

    if rsi >= 70:
        return f"aşırı alım bölgesi; kar satışı riski{direction}", -1
    if rsi > 55:
        score = 1
        return f"pozitif momentum güçleniyor{direction}", score
    if rsi <= 30:
        return f"aşırı satım; tepki ihtimali artıyor{direction}", 1
    if rsi < 45:
        score = -1
        return f"zayıf, satış baskısı sürüyor{direction}", score
    return f"nötr bölgede{direction}", 0


def stoch_comment(k: float | None, d: float | None) -> tuple[str, int]:
    """Stochastic RSI yorumu ve skor katkısı."""
    if k is None or d is None:
        return "-", 0
    if k >= 80 and d >= 80:
        return "aşırı alım bölgesi; dikkat", -1
    if k <= 20 and d <= 20:
        return "aşırı satım bölgesi; tepki beklenebilir", 1
    if k > d and k < 50:
        return "K, D'yi yukarı kesti; olası alım sinyali", 1
    if k < d and k > 50:
        return "K, D'yi aşağı kesti; olası satış sinyali", -1
    return "nötr", 0


def macd_comment(macd: float | None, signal: float | None) -> tuple[str, int]:
    if macd is None or signal is None:
        return "-", 0
    if macd > signal:
        return "sinyal üstünde, pozitif momentum", 1
    return "sinyal altında, zayıf momentum", -1


def adx_comment(adx: float | None) -> tuple[str, int]:
    if adx is None:
        return "-", 0
    if adx >= 25:
        return "trend gücü yüksek, yönlü hareket gelebilir", 1
    return "Momentum düşük, yatay bant riski", 0


def bb_comment(price: float | None, bb_lower: float | None, bb_upper: float | None) -> tuple[str, int]:
    if price is None or bb_lower is None or bb_upper is None or bb_upper <= bb_lower:
        return "-", 0
    pos = ((price - bb_lower) / (bb_upper - bb_lower)) * 100
    if pos >= 80:
        return "üst banda yakın, kar satışı izlenir", -1
    if pos <= 20:
        return "alt banda yakın, tepki bölgesi", 1
    return "orta bantta, yön teyidi beklenir", 0


def sma_comment(sma5: float | None, sma20: float | None) -> tuple[str, int]:
    if sma5 is None or sma20 is None:
        return "-", 0
    if sma5 > sma20:
        return "kısa vade SMA20 üstünde, pozitif", 1
    return "kısa vade SMA20 altında, negatif", -1


def ema_comment(price: float | None, ema20: float | None, ema50: float | None) -> tuple[str, int]:
    if price is None or ema20 is None or ema50 is None:
        return "-", 0
    if price > ema20 > ema50:
        return "fiyat EMA20⟩EMA50 üstünde, güçlü yükseliş düzeni", 2
    if price < ema20 < ema50:
        return "fiyat EMA20⟨EMA50 altında, güçlü düşüş düzeni", -2
    if price > ema20:
        return "fiyat EMA20 üstünde, kısa vadeli pozitif", 1
    return "fiyat EMA20 altında, kısa vadeli negatif", -1


def fibonacci_levels(high: float, low: float) -> dict:
    """Fibonacci retracement seviyelerini hesaplar (yüksekten aşağı)."""
    diff = high - low
    return {
        "100.0": high,
        "78.6": high - diff * 0.214,
        "61.8": high - diff * 0.382,
        "50.0": high - diff * 0.500,
        "38.2": high - diff * 0.618,
        "23.6": high - diff * 0.764,
        "0.0": low,
    }


def fibonacci_position_label(price: float, fibs: dict) -> str:
    """Fiyatın fibonacci seviyeleri arasındaki konumunu açıklar."""
    levels = sorted(fibs.items(), key=lambda x: float(x[0]), reverse=True)
    for i in range(len(levels) - 1):
        upper_label, upper_val = levels[i]
        lower_label, lower_val = levels[i + 1]
        if lower_val <= price <= upper_val:
            return f"%{lower_label} – %{upper_label} aralığında"
    return "Fibonacci dışı"


def support_resistance_from_fibonacci(price: float, fibs: dict) -> tuple:
    """Fibonacci seviyelerinden en yakın destek ve dirençleri bulur.
    Eksik seviyeler için aylık düşük/yüksek sınırlarını kullanır.
    """
    sorted_levels = sorted(fibs.values())

    below = [v for v in sorted_levels if v < price]
    above = [v for v in sorted_levels if v > price]

    # Fibonacci seviyeleri yeterli değilse aylık low/high fallback
    min_level = sorted_levels[0]  # Low
    max_level = sorted_levels[-1]  # High

    s1 = below[-1] if len(below) >= 1 else min_level
    s2 = below[-2] if len(below) >= 2 else (min_level if s1 != min_level else None)
    r1 = above[0] if len(above) >= 1 else max_level
    r2 = above[1] if len(above) >= 2 else (max_level if r1 != max_level else None)

    return s1, s2, r1, r2


# ─── Mesaj Formatı ────────────────────────────────────────────────────────────

def tech_row(label: str, value: str, comment: str = "") -> str:
    """Teknik gösterge satırı: 🔹 Etiket  : Değer \\n   yorum"""
    label_padded = label.ljust(12)
    if not value:
        return f"🔹 {label_padded} :\n   {comment}\n"
    if comment and comment != "-":
        return f"🔹 {label_padded} : {value}\n   {comment}\n"
    return f"🔹 {label_padded} : {value}\n"


def support_resistance_table(s1, s2, r1, r2) -> str:
    rows = [
        ("Destek 1", format_tr_number(s1) if s1 is not None else "-"),
        ("Destek 2", format_tr_number(s2) if s2 is not None else "-"),
        ("Direnç 1", format_tr_number(r1) if r1 is not None else "-"),
        ("Direnç 2", format_tr_number(r2) if r2 is not None else "-"),
    ]
    table = [
        "┌──────────┬──────────┐",
        *[f"│ {label.ljust(8)} │ {value.ljust(8)} │" for label, value in rows],
        "└──────────┴──────────┘",
    ]
    return "\n".join(table)


def fibonacci_table(fibs: dict, price: float) -> str:
    """Fibonacci seviyelerini fiyata göre ↑/↓ işaretli gösterir."""
    display_levels = ["78.6", "61.8", "50.0", "38.2", "23.6"]
    lines = []
    for lvl in display_levels:
        val = fibs.get(lvl)
        if val is None:
            continue
        if price < val:
            marker = "▲ direnç"
        elif price > val:
            marker = "▼ destek"
        else:
            marker = "← burada"
        lines.append(f"  %{lvl:>5} → {format_tr_number(val):>8}  [{marker}]")
    return "\n".join(lines)


def build_technical_analysis(stock: dict) -> str:
    details = fetch_stock_details(stock)
    indicators = fetch_tradingview_indicators(stock.get("symbol", ""))

    price = parse_tr_number(stock.get("price"))
    change = parse_tr_number(stock.get("change_percentage"))
    high = parse_tr_number(stock.get("high"))
    low = parse_tr_number(stock.get("low"))

    open_price = detail_number(details, "Açılış Fiyatı")
    previous_close = detail_number(details, "Önceki Kapanış Fiyatı")

    if price is None:
        return f"\n\n📈 <b>TEKNİK GÖRÜNÜM (ÖZET)</b>\n{SEP}\nVeri yetersiz."

    # ── Göstergeler ──────────────────────────────────────────────────────────
    rsi = tv_number(indicators, "RSI")
    rsi_prev = tv_number(indicators, "RSI[1]")
    macd = tv_number(indicators, "MACD.macd")
    macd_sig = tv_number(indicators, "MACD.signal")
    adx = tv_number(indicators, "ADX")
    bb_upper = tv_number(indicators, "BB.upper")
    bb_lower = tv_number(indicators, "BB.lower")
    sma5 = tv_number(indicators, "SMA5")
    sma20 = tv_number(indicators, "SMA20")
    ema20 = tv_number(indicators, "EMA20")
    ema50 = tv_number(indicators, "EMA50")
    stoch_k = tv_number(indicators, "Stoch.K")
    stoch_d = tv_number(indicators, "Stoch.D")
    high_1m = tv_number(indicators, "High.1M")
    low_1m = tv_number(indicators, "Low.1M")

    # ── Skor Hesabı ──────────────────────────────────────────────────────────
    score = 0
    if change is not None:
        score += 1 if change > 0 else -1

    rsi_cmt, rsi_sc = rsi_comment(rsi, rsi_prev)
    score += rsi_sc

    stoch_cmt, stoch_sc = stoch_comment(stoch_k, stoch_d)
    score += stoch_sc

    macd_cmt, macd_sc = macd_comment(macd, macd_sig)
    score += macd_sc

    adx_cmt, _ = adx_comment(adx)

    bb_cmt, bb_sc = bb_comment(price, bb_lower, bb_upper)
    score += bb_sc

    sma_cmt, sma_sc = sma_comment(sma5, sma20)
    score += sma_sc

    ema_cmt, ema_sc = ema_comment(price, ema20, ema50)
    score += ema_sc

    # ── Fibonacci (Aylık Aralık) ──────────────────────────────────────────────
    fib_high = high_1m if high_1m is not None else high
    fib_low = low_1m if low_1m is not None else low
    fibs = None
    fib_label_str = "Aylık aralık" if high_1m is not None else "Günlük aralık"

    if fib_high is not None and fib_low is not None and fib_high > fib_low:
        fibs = fibonacci_levels(fib_high, fib_low)
        fib_pos = fibonacci_position_label(price, fibs)
        s1, s2, r1, r2 = support_resistance_from_fibonacci(price, fibs)
    else:
        fib_pos = "-"
        s1, s2 = low, None
        r1, r2 = high, None

    # ── Senaryo Olasılıkları ──────────────────────────────────────────────────
    upper_prob = "Yüksek" if score >= 3 else "Orta" if score >= 1 else "Düşük"
    range_prob = "Yüksek" if adx is not None and adx < 20 else "Orta" if -1 <= score <= 1 else "Düşük"
    lower_prob = "Yüksek" if score <= -3 else "Orta" if score <= -1 else "Düşük"

    # ── Mesaj Bölümleri ───────────────────────────────────────────────────────
    section_technical = [
        "",
        f"📈 <b>TEKNİK GÖRÜNÜM (ÖZET)</b>",
        SEP,
        tech_row("Trend", "", trend_summary(score)),
        tech_row("RSI (14)", format_tr_number(rsi) if rsi is not None else "-", rsi_cmt),
        tech_row("Stoch RSI", f"{format_tr_number(stoch_k)} / {format_tr_number(stoch_d)}" if stoch_k is not None else "-", stoch_cmt),
        tech_row("MACD", f"{format_tr_number(macd)} / {format_tr_number(macd_sig)}" if macd is not None else "-", macd_cmt),
        tech_row("ADX", format_tr_number(adx) if adx is not None else "-", adx_cmt),
        tech_row("Bollinger", f"{format_tr_number(bb_lower)} - {format_tr_number(bb_upper)}" if bb_lower is not None else "-", bb_cmt),
        tech_row("SMA 5/20", f"{format_tr_number(sma5)} / {format_tr_number(sma20)}" if sma5 is not None else "-", sma_cmt),
        tech_row("EMA 20/50", f"{format_tr_number(ema20)} / {format_tr_number(ema50)}" if ema20 is not None else "-", ema_cmt),
    ]

    section_technical.append(SEP)

    # ── Fibonacci Bölümü ─────────────────────────────────────────────────────
    section_fib = []
    if fibs is not None:
        section_fib = [
            "",
            f"📐 <b>FİBONACCİ SEVİYELERİ ({fib_label_str})</b>",
            SEP,
            f"<code>{escape(fibonacci_table(fibs, price))}</code>",
            f"  Konum: {fib_pos}",
            SEP,
        ]

    # ── Destek & Direnç (Kaldırıldı) ─────────────────────────────────────────
    section_sr = []

    # ── Senaryolar ───────────────────────────────────────────────────────────
    r1_str = format_tr_number(r1) if r1 is not None else format_tr_number(high)
    r2_str = format_tr_number(r2) if r2 is not None else format_tr_number(high)
    s1_str = format_tr_number(s1) if s1 is not None else format_tr_number(low)
    s2_str = format_tr_number(s2) if s2 is not None else format_tr_number(low)

    section_scenarios = [
        "",
        "🧭 <b>KISA VADE SENARYOLARI</b>",
        SEP,
    ]
    if score >= 3:
        section_scenarios.append(f"🟢 Kısa vadede yükseliş beklenmektedir.")
        if r1 is not None:
             section_scenarios.append(f"Hedef: {r1_str} TL")
    elif score >= 1:
        section_scenarios.append(f"🟢 Kısa vadede pozitif ayrışma izleniyor.")
        if r1 is not None:
            section_scenarios.append(f"İlk Hedef: {r1_str} TL")
    elif score <= -3:
        section_scenarios.append(f"🔴 Kısa vadede düşüş beklenmektedir.")
        if s1 is not None:
            section_scenarios.append(f"Destek: {s1_str} TL")
    elif score <= -1:
        section_scenarios.append(f"🔴 Kısa vadede negatif seyir izleniyor.")
        if s1 is not None:
            section_scenarios.append(f"Ana Destek: {s1_str} TL")
    else:
        section_scenarios.append(f"🟡 Kısa vadede yatay seyir beklenmektedir.")
        if s1 is not None and r1 is not None:
            section_scenarios.append(f"Bant: {s1_str} - {r1_str} TL")
    
    section_scenarios.append(SEP)

    all_lines = section_technical + section_fib + section_sr + section_scenarios
    return "\n".join(all_lines)


def format_stock_message(stock: dict) -> str:
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))
    change_value = stock.get("change_percentage", "-")
    change_icon = change_icon_for_change(change_value)
    price_text = f"{stock.get('price', '-')} TL"

    header = (
        f"📊 <b>{company_name} ({symbol})</b>\n\n"
        f"📅 {format_report_date()} – {format_report_time()}\n"
        f"{SEP}\n"
        f"Fiyat        : {price_text}\n"
        f"Değişim      : {change_report_value(change_value)}\n"
        f"Günlük Max   : {stock.get('high', '-')}\n"
        f"Min          : {stock.get('low', '-')}\n"
        f"AOF (Ort.)   : {stock.get('aof', '-')}\n"
        f"Hacim Lot    : {format_compact_tr(stock.get('volume_lot', '-'))}\n"
        f"Hacim TL     : {format_compact_tr(stock.get('volume_tl', '-'))}\n"
        f"{SEP}"
    )

    return header + build_technical_analysis(stock)


# ─── Supabase ─────────────────────────────────────────────────────────────────

def update_supabase(data_list: list):
    if not SUPABASE_URL or not SUPABASE_KEY or SUPABASE_URL == "YOUR_SUPABASE_URL":
        print("Please configure SUPABASE_URL and SUPABASE_KEY.")
        return

    try:
        from supabase import create_client, Client

        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Upsert in chunks
        chunk_size = 100
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i:i + chunk_size]
            supabase.table("borsa_data").upsert(
                chunk,
                on_conflict="symbol"
            ).execute()
            time.sleep(0.1)

        print(f"Successfully updated {len(data_list)} records in Supabase.")
    except Exception as e:
        print(f"Error updating Supabase: {e}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Borsa Scraper ===")

    if SUPABASE_URL == "YOUR_SUPABASE_URL":
        print("ERROR: Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
        exit(1)

    print("Step 1: Scraping Mynet Borsa data...")
    data = scrape_borsa()

    if not data:
        print("No data scraped. Exiting.")
        exit(1)

    print(f"  Scraped {len(data)} stocks.")

    print("Step 2: Updating Supabase database...")
    update_supabase(data)

    print("=== Done! ===")
