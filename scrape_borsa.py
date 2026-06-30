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
        response = requests.get(detail_link, headers=HEADERS, timeout=15)
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
        return "🟢"
    if direction == "down":
        return "🔴"
    return "⚪"

def stock_line(icon: str, label: str, value, width: int = 9) -> str:
    return f"{icon} <code>{escape(label.ljust(width))}: {safe_text(value)}</code>"

def detail_number(details: dict, label: str):
    return parse_tr_number(details.get(label))

def build_technical_analysis(stock: dict) -> str:
    details = fetch_stock_details(stock)
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
        return "\n\n🤖 <b>AI Yorum</b>\nVeri yetersiz olduğu için teknik yorum üretilemedi."

    direction = change_direction(stock.get("change_percentage"))
    if direction == "up":
        mood = "alım ağırlıklı"
        bias = "pozitif"
        action = "yukarı yönlü denemeler öne çıkabilir"
    elif direction == "down":
        mood = "satış ağırlıklı"
        bias = "negatif"
        action = "tepki alımı gelmedikçe baskı sürebilir"
    else:
        mood = "dengeli"
        bias = "nötr"
        action = "yatay-sıkışık seyir izlenebilir"

    notes = []
    score = 0

    if change is not None:
        if change > 0:
            score += 1
        elif change < 0:
            score -= 1

    if sma20 is not None:
        if price > sma20:
            score += 1
            notes.append(f"Fiyat 20 günlük ortalamanın üzerinde ({format_tr_number(sma20)}); kısa vadede toparlanma eğilimi destekleniyor.")
        else:
            score -= 1
            notes.append(f"Fiyat 20 günlük ortalamanın altında ({format_tr_number(sma20)}); kısa vadeli baskı devam ediyor.")

    if sma20 is not None and sma52 is not None:
        if sma20 > sma52:
            score += 1
            notes.append("20 günlük ortalama 52 günlük ortalamanın üzerinde; orta vadeli trend yapısı görece güçlü.")
        else:
            score -= 1
            notes.append("20 günlük ortalama 52 günlük ortalamanın altında; orta vadeli görünüm zayıf.")

    if previous_close is not None:
        gap = ((price - previous_close) / previous_close) * 100 if previous_close else None
        if gap is not None:
            notes.append(f"Önceki kapanışa göre momentum {format_tr_number(gap)}% seviyesinde.")

    if open_price is not None:
        intraday = ((price - open_price) / open_price) * 100 if open_price else None
        if intraday is not None:
            notes.append(f"Açılışa göre gün içi performans {format_tr_number(intraday)}%.")

    if high is not None and low is not None and high > low:
        day_range = high - low
        position = ((price - low) / day_range) * 100
        fib_s1 = high - day_range * 0.618
        fib_s2 = high - day_range * 0.786
        fib_r1 = low + day_range * 0.618
        fib_r2 = high

        if position >= 70:
            score += 1
            notes.append("Fiyat gün içi bandın üst bölgesinde; alıcılar kapanışa yakın daha dirençli.")
        elif position <= 30:
            score -= 1
            notes.append("Fiyat gün içi bandın alt bölgesinde; satıcı baskısı belirgin.")

        fib_line = (
            f"Fibonacci S1/S2: {format_tr_number(fib_s1)} / {format_tr_number(fib_s2)}; "
            f"R1/R2: {format_tr_number(fib_r1)} / {format_tr_number(fib_r2)}."
        )
    else:
        fib_line = "Fibonacci destek/direnç için gün içi dip-tepe verisi yetersiz."

    range_lines = []
    if weekly_low is not None and weekly_high is not None:
        range_lines.append(f"Haftalık bant: {format_tr_number(weekly_low)} - {format_tr_number(weekly_high)}")
    if monthly_low is not None and monthly_high is not None:
        range_lines.append(f"Aylık bant: {format_tr_number(monthly_low)} - {format_tr_number(monthly_high)}")
    if yearly_low is not None and yearly_high is not None:
        range_lines.append(f"Yıllık bant: {format_tr_number(yearly_low)} - {format_tr_number(yearly_high)}")

    if score >= 2:
        forecast = "Kısa vadeli teknik görünüm pozitif tarafa dönmüş görünüyor."
    elif score <= -2:
        forecast = "Kısa vadeli teknik görünüm zayıf; desteklerin korunması önemli."
    else:
        forecast = "Teknik görünüm kararsız; teyit için hacim ve kapanış yönü izlenmeli."

    change_text = format_change_value(stock.get("change_percentage"))
    analysis = [
        "",
        "",
        "🤖 <b>AI Yorum</b>",
        f"{company_name} ({symbol}) bugün {mood} bir seyir izliyor. Hisse {change_text} hareketle {safe_text(stock.get('price', '-'))} TL seviyesinde.",
        "",
        f"📌 <b>Yön</b>: {bias}. {action}.",
    ]

    if notes:
        analysis.append("📊 <b>Teknik özet</b>:")
        analysis.extend(f"• {escape(note)}" for note in notes[:5])

    analysis.append(f"🧭 <b>Destek/Direnç</b>: {escape(fib_line)}")

    if range_lines:
        analysis.append("📐 " + escape(" | ".join(range_lines[:2])))

    analysis.append(f"🔎 <b>Tahmin</b>: {escape(forecast)}")
    analysis.append("⚠️ Yatırım tavsiyesi değildir.")

    if not details:
        analysis.append("Not: Detay sayfası okunamadığı için yorum sınırlı canlı veriyle üretildi.")
    else:
        analysis.append("Not: RSI, MACD ve Bollinger için kapanış serisi gerekir; bu yorum Mynet detay verileri ve ortalama/momentum sinyalleriyle üretilmiştir.")

    return "\n".join(analysis)

def format_stock_message(stock: dict) -> str:
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))
    separator = "————————————————"
    change_value = stock.get("change_percentage", "-")

    return (
        f"<b>{symbol} - {company_name}</b>\n"
        f"{separator}\n"
        f"{stock_line(price_icon_for_change(change_value), 'Fiyat', stock.get('price', '-'))}\n\n"
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
