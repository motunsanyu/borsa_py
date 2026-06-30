import requests
import os
import re
import time
from html import escape, unescape
from urllib.parse import urlparse

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

    value = str(value).strip().replace("%", "")
    value = re.sub(r"[^0-9,\.\-]", "", value)
    if not value:
        return None

    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None

def format_tr_number(value, digits: int = 2) -> str:
    if value is None:
        return "-"

    formatted = f"{value:,.{digits}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

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
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))

    price = parse_tr_number(stock.get("price"))
    change = parse_tr_number(stock.get("change_percentage"))
    high = parse_tr_number(stock.get("high"))
    low = parse_tr_number(stock.get("low"))
    avg = parse_tr_number(stock.get("aof"))

    open_price = detail_number(details, "Açılış Fiyatı")
    previous_close = detail_number(details, "Önceki Kapanış Fiyatı")
    sma20 = detail_number(details, "20 Günlük Ortalama")
    sma52 = detail_number(details, "52 Günlük Ortalama")
    weekly_low = detail_number(details, "Haftalık En Düşük")
    weekly_high = detail_number(details, "Haftalık En Yüksek")
    monthly_low = detail_number(details, "Aylık En Düşük")
    monthly_high = detail_number(details, "Aylık En Yüksek")
    yearly_low = detail_number(details, "Yıllık En Düşük")
    yearly_high = detail_number(details, "Yıllık En Yüksek")

    if price is None:
        return "\n\n🤖 <b>AI Teknik Yorum</b>\nVeri yetersiz olduğu için teknik yorum üretilemedi."

    direction = change_direction(stock.get("change_percentage"))
    if direction == "up":
        mood = "alım ağırlıklı"
        bias = "pozitif"
        action = "yukarı yönlü denemelerde hacim teyidi aranmalı"
    elif direction == "down":
        mood = "satış ağırlıklı"
        bias = "negatif"
        action = "tepki alımı için destek bölgesinde kalıcılık izlenmeli"
    else:
        mood = "dengeli"
        bias = "nötr"
        action = "yatay-sıkışık seyir izlenebilir"

    trend_notes = []
    momentum_notes = []
    score = 0

    if change is not None:
        if change > 0:
            score += 1
        elif change < 0:
            score -= 1

    if sma20 is not None:
        if price > sma20:
            score += 1
            trend_notes.append(f"Fiyat 20 günlük ortalamanın üzerinde: {format_tr_number(sma20)}")
        else:
            score -= 1
            trend_notes.append(f"Fiyat 20 günlük ortalamanın altında: {format_tr_number(sma20)}")

    if sma20 is not None and sma52 is not None:
        if sma20 > sma52:
            score += 1
            trend_notes.append("20 günlük ortalama, 52 günlük ortalamanın üzerinde")
        else:
            score -= 1
            trend_notes.append("20 günlük ortalama, 52 günlük ortalamanın altında")

    if previous_close is not None:
        gap = ((price - previous_close) / previous_close) * 100 if previous_close else None
        if gap is not None:
            momentum_notes.append(f"Önceki kapanışa göre: {format_tr_number(gap)}%")

    if open_price is not None:
        intraday = ((price - open_price) / open_price) * 100 if open_price else None
        if intraday is not None:
            momentum_notes.append(f"Açılışa göre: {format_tr_number(intraday)}%")

    if high is not None and low is not None and high > low:
        day_range = high - low
        position = ((price - low) / day_range) * 100
        fib_s1 = high - day_range * 0.618
        fib_s2 = high - day_range * 0.786
        fib_r1 = low + day_range * 0.618
        fib_r2 = high

        if position >= 70:
            score += 1
            momentum_notes.append("Fiyat gün içi bandın üst bölgesinde")
        elif position <= 30:
            score -= 1
            momentum_notes.append("Fiyat gün içi bandın alt bölgesinde")

        fib_line = (
            f"S1 {format_tr_number(fib_s1)} | S2 {format_tr_number(fib_s2)}\n"
            f"R1 {format_tr_number(fib_r1)} | R2 {format_tr_number(fib_r2)}"
        )
    else:
        fib_line = "Gün içi dip-tepe verisi yetersiz"

    tv_lines, tv_score = tradingview_signal_lines(indicators, price)
    score += tv_score

    range_lines = []
    if weekly_low is not None and weekly_high is not None:
        range_lines.append(f"Haftalık: {format_tr_number(weekly_low)} - {format_tr_number(weekly_high)}")
    if monthly_low is not None and monthly_high is not None:
        range_lines.append(f"Aylık: {format_tr_number(monthly_low)} - {format_tr_number(monthly_high)}")
    if yearly_low is not None and yearly_high is not None:
        range_lines.append(f"Yıllık: {format_tr_number(yearly_low)} - {format_tr_number(yearly_high)}")

    if score >= 2:
        forecast = "pozitif eğilim güçleniyor; direnç üzeri kapanışlar takip edilmeli"
    elif score <= -2:
        forecast = "zayıf görünüm korunuyor; destek altında risk artar"
    else:
        forecast = "kararsız bölge; yön teyidi için hacim ve kapanış beklenmeli"

    change_text = format_change_value(stock.get("change_percentage"))
    separator = "━━━━━━━━━━━━━━━━"
    analysis = [
        "",
        "",
        "🤖 <b>AI TEKNİK YORUM</b>",
        separator,
        f"<b>{company_name} ({symbol})</b>",
        f"Bugün {mood} seyir var. Hisse {change_text} hareketle {safe_text(stock.get('price', '-'))} TL seviyesinde.",
        "",
        f"📌 <b>Yön / Senaryo</b>",
        f"• Ana eğilim: <b>{escape(bias.title())}</b>",
        f"• Stratejik izleme: {escape(action)}",
    ]

    if trend_notes or momentum_notes:
        analysis.extend(["", "📊 <b>Trend ve Momentum</b>"])
        analysis.extend(f"• {escape(note)}" for note in trend_notes[:3])
        analysis.extend(f"• {escape(note)}" for note in momentum_notes[:3])

    if tv_lines:
        analysis.extend(["", "📈 <b>İndikatörler</b>"])
        analysis.extend(tv_lines[:5])

    analysis.extend(["", "🧭 <b>Destek / Direnç</b>"])
    analysis.append(escape(fib_line).replace("\n", "\n"))

    if range_lines:
        analysis.extend(["", "📐 <b>Bantlar</b>", escape(" | ".join(range_lines[:2]))])

    analysis.extend(["", "🔎 <b>Kısa Vadeli Tahmin</b>", escape(forecast)])

    return "\n".join(analysis)

def format_stock_message(stock: dict) -> str:
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))
    separator = "————————————————"
    change_value = stock.get("change_percentage", "-")

    return (
        f"<b>{symbol} - {company_name}</b>\n"
        f"{separator}\n"
        f"{stock_line('💰', 'Fiyat', stock.get('price', '-'))}\n\n"
        f"{stock_line(change_icon_for_change(change_value), 'Degisim', format_change_value(change_value))}\n"
        f"{stock_line('📈', 'En yuksek', stock.get('high', '-'))}\n"
        f"{stock_line('📉', 'En dusuk', stock.get('low', '-'))}\n"
        f"{stock_line('⚖️', 'AOF', stock.get('aof', '-'))}\n"
        f"{stock_line('📦', 'Hacim lot', stock.get('volume_lot', '-'))}\n"
        f"{stock_line('💵', 'Hacim TL', stock.get('volume_tl', '-'))}\n"
        f"{stock_line('🕒', 'Saat', stock.get('time', '-'))}\n"
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
