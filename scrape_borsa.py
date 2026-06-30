import requests
import os
import time
from html import escape
from urllib.parse import urlparse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

COMPANY_NAMES = {
    "ASELS": "ASELSAN",
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
                link = parts[15].strip()
                
                if not link.startswith("http"):
                    link = "https://finans.mynet.com/" + link.lstrip("/")
                    
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

def format_stock_message(stock: dict) -> str:
    symbol = safe_text(stock.get("symbol", "-"))
    company_name = safe_text(get_company_name(stock))
    separator = "————————————————"

    return (
        f"<b>{symbol} - {company_name}</b>\n"
        f"{separator}\n"
        f"💰 <b>Fiyat</b>     : {safe_text(stock.get('price', '-'))}\n\n"
        f"📉 <b>Degisim</b>   : {safe_text(stock.get('change_percentage', '-'))}\n"
        f"📈 <b>En yuksek</b> : {safe_text(stock.get('high', '-'))}\n"
        f"📉 <b>En dusuk</b>  : {safe_text(stock.get('low', '-'))}\n"
        f"⚖️ <b>AOF</b>       : {safe_text(stock.get('aof', '-'))}\n"
        f"📦 <b>Hacim lot</b> : {safe_text(stock.get('volume_lot', '-'))}\n"
        f"💵 <b>Hacim TL</b>  : {safe_text(stock.get('volume_tl', '-'))}\n"
        f"🕒 <b>Saat</b>      : {safe_text(stock.get('time', '-'))}\n"
        f"{separator}"
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
