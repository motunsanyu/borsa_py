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

def format_change_value(change_value) -> str:
    change = parse_tr_number(change_value)
    if change is None:
        return safe_text(change_value)

    absolute_change = format_tr_number(abs(change))
    if change > 0:
        return f"{absolute_change}% ▲"
    if change < 0:
        return f"{absolute_change}% ▼"
    return f"{absolute_change}%"

def price_icon_for_change(change_value) -> str:
    direction = change_direction(change_value)
    if direction == "up":
        return "🟢"
    if direction == "down":
        return "🔴"
    return "⚪"

def change_icon_for_change(change_value) -> str:
    direction = change_direction(change_value)
    if direction == "up":
        return "📈"
    if direction == "down":
        return "📉"
    return "📊"

def stock_line(icon: str, label: str, value, width: int = 9) -> str:
    return f"{icon} <code>{escape(label.ljust(width))}: {safe_text(value)}</code>"

def detail_number(details: dict, label: str):
    return parse_tr_number(details.get(label))

def tv_number(indicators: dict, label: str):
    return parse_tr_number(indicators.get(label))

def indicator_line(label: str, value, comment: str) -> str:
    return f"• <b>{escape(label)}</b>: {safe_text(value)} - {escape(comment)}"

def technical_row(label: str, value, comment: str) -> str:
    if comment and comment != "-":
        return f"🔹 <code>{escape(label.ljust(15))}: {safe_text(value)}</code> {escape(comment)}"
    return f"🔹 <code>{escape(label.ljust(15))}: {safe_text(value)}</code>"

def support_resistance_table(s1, s2, r1, r2) -> str:
    rows = [
        ("Destek 1", format_tr_number(s1)),
        ("Destek 2", format_tr_number(s2)),
        ("Direnç 1", format_tr_number(r1)),
        ("Direnç 2", format_tr_number(r2)),
    ]

    table = [
        "┌──────────┬──────────┐",
        *[f"│ {label.ljust(8)} │ {value.ljust(8)} │" for label, value in rows],
        "└──────────┴──────────┘",
    ]
    return "\n".join(table)

def change_report_value(change_value) -> str:
    change = parse_tr_number(change_value)
    if change is None:
        return safe_text(change_value)
    if change > 0:
        return f"(▲ +{format_tr_number(abs(change))}%)"
    if change < 0:
        return f"(▼ {format_tr_number(abs(change))}%)"
    return f"({format_tr_number(change)}%)"

def trend_summary(score: int) -> str:
    if score >= 2:
        return "Pozitif (orta vade) / Kısa vadede alıcı güçlü"
    if score <= -2:
        return "Negatif (orta vade) / Kısa vadede baskı sürüyor"
    return "Kararsız / Bant hareketi izleniyor"

def tradingview_signal_lines(indicators: dict, price: float | None) -> tuple[list[str], int]:
    lines = []
    score = 0

    rsi = tv_number(indicators, "RSI")
    rsi_previous = tv_number(indicators, "RSI[1]")
    macd = tv_number(indicators, "MACD.macd")
    macd_signal = tv_number(indicators, "MACD.signal")
    adx = tv_number(indicators, "ADX")
    bb_upper = tv_number(indicators, "BB.upper")
    bb_lower = tv_number(indicators, "BB.lower")
    sma5 = tv_number(indicators, "SMA5")
    sma20 = tv_number(indicators, "SMA20")

    if rsi is not None:
        if rsi >= 70:
            comment = "aşırı alım bölgesi; kar satışı riski izlenir"
        elif rsi > 55:
            comment = "alım iştahı güçleniyor"
            score += 1
        elif rsi <= 30:
            comment = "aşırı satım bölgesi; tepki ihtimali artar"
        elif rsi < 45:
            comment = "momentum zayıf"
            score -= 1
        else:
            comment = "nötr bölgede"

        if rsi_previous is not None:
            comment += ", RSI yükseliyor" if rsi > rsi_previous else ", RSI geriliyor"

        lines.append(indicator_line("RSI", format_tr_number(rsi), comment))

    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            score += 1
            comment = "MACD sinyal çizgisinin üzerinde; pozitif momentum"
        else:
            score -= 1
            comment = "MACD sinyal çizgisinin altında; zayıf momentum"
        lines.append(indicator_line("MACD", f"{format_tr_number(macd)} / {format_tr_number(macd_signal)}", comment))

    if adx is not None:
        if adx >= 25:
            comment = "trend gücü yüksek; yönlü hareket potansiyeli artıyor"
            score += 1
        else:
            comment = "trend gücü sınırlı; yatay hareket riski var"
        lines.append(indicator_line("ADX", format_tr_number(adx), comment))

    if price is not None and bb_upper is not None and bb_lower is not None and bb_upper > bb_lower:
        band_position = ((price - bb_lower) / (bb_upper - bb_lower)) * 100
        if band_position >= 80:
            comment = "üst banda yakın; kısa vadede yorulma izlenebilir"
        elif band_position <= 20:
            comment = "alt banda yakın; tepki alanı oluşabilir"
        else:
            comment = "bandın orta bölgesinde; yön teyidi beklenir"
        lines.append(indicator_line("Bollinger", f"{format_tr_number(bb_lower)} - {format_tr_number(bb_upper)}", comment))

    if sma5 is not None and sma20 is not None:
        if sma5 > sma20:
            score += 1
            comment = "SMA5, SMA20 üzerinde; kısa vadeli kesişim pozitif"
        else:
            score -= 1
            comment = "SMA5, SMA20 altında; kısa vadeli kesişim negatif"
        lines.append(indicator_line("SMA5/20", f"{format_tr_number(sma5)} / {format_tr_number(sma20)}", comment))

    return lines, score

def build_technical_analysis(stock: dict) -> str:
    details = fetch_stock_details(stock)
    indicators = fetch_tradingview_indicators(stock.get("symbol", ""))

    price = parse_tr_number(stock.get("price"))
    change = parse_tr_number(stock.get("change_percentage"))
    high = parse_tr_number(stock.get("high"))
    low = parse_tr_number(stock.get("low"))

    open_price = detail_number(details, "Açılış Fiyatı")
    previous_close = detail_number(details, "Önceki Kapanış Fiyatı")
    sma20 = detail_number(details, "20 Günlük Ortalama")
    sma52 = detail_number(details, "52 Günlük Ortalama")

    if price is None:
        return "\n\n📈 <b>TEKNİK GÖRÜNÜM (ÖZET)</b>\n━━━━━━━━━━━━━━━━━━━━\nVeri yetersiz."

    score = 0

    if change is not None:
        if change > 0:
            score += 1
        elif change < 0:
            score -= 1

    if sma20 is not None:
        if price > sma20:
            score += 1
        else:
            score -= 1

    if sma20 is not None and sma52 is not None:
        if sma20 > sma52:
            score += 1
        else:
            score -= 1

    open_performance = None
    if open_price is not None and open_price:
        open_performance = ((price - open_price) / open_price) * 100

    previous_performance = None
    if previous_close is not None and previous_close:
        previous_performance = ((price - previous_close) / previous_close) * 100

    if high is not None and low is not None and high > low:
        day_range = high - low
        position = ((price - low) / day_range) * 100
        fib_s1 = high - day_range * 0.618
        fib_s2 = high - day_range * 0.786
        fib_r1 = low + day_range * 0.618
        fib_r2 = high

        if position >= 70:
            score += 1
        elif position <= 30:
            score -= 1
    else:
        fib_s1 = fib_s2 = fib_r1 = fib_r2 = None

    tv_lines, tv_score = tradingview_signal_lines(indicators, price)
    score += tv_score

    rsi = tv_number(indicators, "RSI")
    rsi_previous = tv_number(indicators, "RSI[1]")
    macd = tv_number(indicators, "MACD.macd")
    macd_signal = tv_number(indicators, "MACD.signal")
    adx = tv_number(indicators, "ADX")
    bb_upper = tv_number(indicators, "BB.upper")
    bb_lower = tv_number(indicators, "BB.lower")
    tv_sma5 = tv_number(indicators, "SMA5")
    tv_sma20 = tv_number(indicators, "SMA20")

    rsi_comment = "-"
    if rsi is not None:
        if rsi > 55:
            rsi_comment = "(pozitif, yükseliş eğiliminde)" if rsi_previous is None or rsi >= rsi_previous else "(pozitif, ivme zayıflıyor)"
        elif rsi < 45:
            rsi_comment = "(zayıf, satış baskısı sürüyor)" if rsi_previous is None or rsi <= rsi_previous else "(zayıf, tepki arayışı var)"
        else:
            rsi_comment = "(nötr, yükseliş eğiliminde)" if rsi_previous is not None and rsi > rsi_previous else "(nötr)"

    macd_comment = "-"
    if macd is not None and macd_signal is not None:
        macd_comment = "(sinyal üstünde, pozitif momentum)" if macd > macd_signal else "(sinyal altında, zayıf momentum)"

    adx_comment = "-"
    if adx is not None:
        adx_comment = "(trend gücü yüksek, yönlü hareket gelebilir)" if adx >= 25 else "(trend gücü düşük, yatay bant riski)"

    bb_comment = "-"
    if price is not None and bb_upper is not None and bb_lower is not None and bb_upper > bb_lower:
        band_position = ((price - bb_lower) / (bb_upper - bb_lower)) * 100
        if band_position > 75:
            bb_comment = "(üst banda yakın, kar satışı izlenir)"
        elif band_position < 25:
            bb_comment = "(alt banda yakın, tepki bölgesi)"
        else:
            bb_comment = "(orta bant, yön bekleniyor)"

    sma_comment = "-"
    if tv_sma5 is not None and tv_sma20 is not None:
        sma_comment = "(kısa vade SMA20 üstünde, pozitif kesişim)" if tv_sma5 > tv_sma20 else "(kısa vade SMA20 altında, negatif kesişim)"

    resistance_target = fib_r2 if fib_r2 is not None else high
    support_break = fib_s2 if fib_s2 is not None else low
    upper_probability = "Yüksek" if score >= 2 else "Orta" if score >= 0 else "Düşük"
    range_probability = "Yüksek" if -1 <= score <= 1 or (adx is not None and adx < 25) else "Orta"
    lower_probability = "Yüksek" if score <= -2 else "Orta" if score < 0 else "Düşük"

    table = support_resistance_table(fib_s1, fib_s2, fib_r1, fib_r2)
    trend_text = trend_summary(score)

    analysis = [
        "",
        "",
        "📈 <b>TEKNİK GÖRÜNÜM (ÖZET)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        technical_row("Trend Yönü", trend_text, ""),
        technical_row("RSI (14)", format_tr_number(rsi) if rsi is not None else "-", rsi_comment),
        technical_row("MACD", f"{format_tr_number(macd)} / {format_tr_number(macd_signal)}" if macd is not None and macd_signal is not None else "-", macd_comment),
        technical_row("ADX", format_tr_number(adx) if adx is not None else "-", adx_comment),
        technical_row("Bollinger Band", f"{format_tr_number(bb_lower)} - {format_tr_number(bb_upper)}" if bb_lower is not None and bb_upper is not None else "-", bb_comment),
        technical_row("SMA 5/20", f"{format_tr_number(tv_sma5)} / {format_tr_number(tv_sma20)}" if tv_sma5 is not None and tv_sma20 is not None else "-", sma_comment),
        "",
        "📌 <b>DESTEK & DİRENÇ</b>",
        f"<code>{escape(table)}</code>",
        "",
        "🧭 <b>KISA VADE SENARYOLARI</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"✅ <b>YUKARI KIRILMA</b> (Olasılık: {upper_probability})",
        f"   – {format_tr_number(fib_r1)} üzerinde hacimli kapanış → {format_tr_number(resistance_target)} hedef.",
        "   – RSI yükselişi ve MACD sinyal geçişi görünümü güçlendirir.",
        "",
        f"⚠️ <b>YATAY BANT</b> (Olasılık: {range_probability})",
        f"   – {format_tr_number(fib_s1)} – {format_tr_number(fib_r1)} aralığında sıkışma izlenebilir.",
        "   – ADX düşük kalırsa hacimsiz hareketler sürebilir.",
        "",
        f"🔻 <b>AŞAĞI KIRILMA</b> (Olasılık: {lower_probability})",
        f"   – {format_tr_number(support_break)} altında kapanış → {format_tr_number(low)} ve altı test edilebilir.",
        "   – MACD zayıf kalırsa satış baskısı artar.",
    ]

    if previous_performance is not None or open_performance is not None:
        momentum_parts = []
        if previous_performance is not None:
            momentum_parts.append(f"Önceki kapanış: {format_tr_number(previous_performance)}%")
        if open_performance is not None:
            momentum_parts.append(f"Açılış: {format_tr_number(open_performance)}%")
        analysis.insert(11, technical_row("Momentum", " | ".join(momentum_parts), ""))

    return "\n".join(analysis)

def format_stock_message(stock: dict) -> str:
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))
    separator = "————————————————————"
    change_value = stock.get("change_percentage", "-")
    time_text = safe_text(stock.get("time", "-"))
    price_text = f"{stock.get('price', '-')} TL"

    return (
        f"📊 <b>{company_name} ({symbol})</b>\n"
        f"📅 {format_report_date()} – {time_text}\n"
        f"{separator}\n"
        f"{stock_line('💰', 'Fiyat', price_text, width=11)}\n\n"
        f"{stock_line(change_icon_for_change(change_value), 'Değişim', change_report_value(change_value), width=11)}\n\n"
        f"{stock_line('📈', 'Günlük Max', stock.get('high', '-'), width=11)}\n"
        f"{stock_line('📉', 'Min', stock.get('low', '-'), width=11)}\n"
        f"{stock_line('⚖️', 'AOF (Ort.)', stock.get('aof', '-'), width=11)}\n"
        f"{stock_line('📦', 'Hacim Lot', format_compact_tr(stock.get('volume_lot', '-')), width=11)}\n"
        f"{stock_line('💵', 'Hacim TL', format_compact_tr(stock.get('volume_tl', '-')), width=11)}\n"
        f"{separator}"
        f"{build_technical_analysis(stock)}"
    )

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
