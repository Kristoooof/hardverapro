import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import time
import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
]

BASE_URL = 'https://hardverapro.hu/aprok/notebook/pc/index.html'
MAX_PAGES = 3 # Javasolt csökkenteni a hosszú várakozási idők miatt!

def extract_specs(text_to_scan):
    t_lower = text_to_scan.lower().replace('\xa0', ' ').replace('\t', ' ')
    
    s = {
        'brand': 'Egyéb',
        'screenSize': None,
        'cpuMfr': 'Ismeretlen',
        'cpuModel': '',
        'ramSize': None,
        'ssdSize': None,
    }

    # Márka
    brands = ['lenovo', 'dell', 'hp', 'asus', 'acer', 'apple', 'msi']
    for b in brands:
        if b in t_lower:
            s['brand'] = b.capitalize() if b != 'hp' else 'HP'
            break

    # Kijelző (10-21" között)
    screen_matches = re.finditer(r'(\d{2}(?:[.,]\d)?)\s*(?:"|col|''|\'|-as|-es|-os)', t_lower)
    for m in screen_matches:
        try:
            val = float(m.group(1).replace(',', '.'))
            if 10.0 <= val <= 21.0:
                s['screenSize'] = val
                break
        except: continue

    # CPU (Ultra, Ryzen AI/PRO, i-széria)
    if 'ultra' in t_lower:
        s['cpuMfr'] = 'Intel'
        m = re.search(r'ultra\s*([579])\s*([\w\d]+)', t_lower)
        if m: s['cpuModel'] = f"Core Ultra {m.group(1)} {m.group(2).upper()}"
    elif 'ryzen' in t_lower:
        s['cpuMfr'] = 'AMD'
        m = re.search(r'ryzen\s*(ai\s*)?([3579])\s*(pro\s*)?([\w\d]+)', t_lower)
        if m:
            p = ["Ryzen"]
            if m.group(1): p.append("AI")
            p.append(m.group(2))
            if m.group(3): p.append("PRO")
            p.append(m.group(4).upper())
            s['cpuModel'] = " ".join(p)
    elif re.search(r'i[3579][\s\-]*\d', t_lower):
        s['cpuMfr'] = 'Intel'
        m = re.search(r'(i[3579])[\s\-]*(\d{4,5}[a-z0-9]*)', t_lower)
        if m: s['cpuModel'] = f"{m.group(1).upper()}-{m.group(2).upper()}"

    # RAM
    ram_m = re.search(r'(\d+)\s*gb', t_lower)
    if ram_m: s['ramSize'] = int(ram_m.group(1))

    # SSD
    ssd_m = re.search(r'(\d+)\s*(gb|tb)\s*(ssd|nvme|m\.2)', t_lower)
    if ssd_m:
        size = int(ssd_m.group(1))
        s['ssdSize'] = size * 1024 if ssd_m.group(2) == 'tb' else size

    return s

def scrape():
    # Cloudscraper példány létrehozása
    scraper = cloudscraper.create_scraper()
    selected_ua = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': selected_ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/'
    }
    
    all_items = []
    seen_links = set()

    # 1. Google -> Főoldal látogatás
    print("Indítás: Google.com -> Hardverapro.hu...")
    try:
        scraper.get("https://hardverapro.hu", headers=headers, timeout=30)
        time.sleep(random.uniform(5, 10))
    except Exception as e:
        print(f"Hiba a kezdéskor: {e}")

    for page in range(MAX_PAGES):
        offset = page * 100
        current_list_url = f"{BASE_URL}?offset={offset}"
        
        print(f"Lista oldal betöltése: {current_list_url}")
        headers['Referer'] = "https://hardverapro.hu"
        resp = scraper.get(current_list_url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            print(f"Hiba: {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        ads = soup.select('li.media')

        for ad in ads:
            title_el = ad.select_one('.uad-col-title a')
            if not title_el: continue
            
            link = title_el['href']
            if not link.startswith('http'): link = 'https://hardverapro.hu' + link
            if link in seen_links: continue
            seen_links.add(link)

            # --- BELÉPÉS A HIRDETÉSBE ---
            print(f"Hirdetés elemzése: {link}")
            headers['Referer'] = current_list_url
            
            try:
                # Véletlenszerű várakozás a kattintás ELŐTT
                time.sleep(random.uniform(2, 5))
                ad_resp = scraper.get(link, headers=headers, timeout=30)
                ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
                
                # Adatok kinyerése a teljes oldalból
                full_text = ad_soup.get_text()
                specs = extract_specs(full_text)
                
                price_text = ad_soup.select_one('.uad-price').get_text(strip=True) if ad_soup.select_one('.uad-price') else "0 Ft"
                
                all_items.append({
                    'title': title_el.get_text(strip=True),
                    'link': link,
                    'price_text': price_text,
                    **specs
                })

                # IDŐZÉS A HIRDETÉSBEN (25-70 mp)
                wait_in_ad = random.uniform(25, 70)
                print(f"Olvasási idő szimulálása: {wait_in_ad:.1f} mp...")
                time.sleep(wait_in_ad)
                
            except Exception as e:
                print(f"Hiba a hirdetésnél: {e}")
                continue

        # VISSZATÉRÉS ÉS VÁRAKOZÁS A KÖVETKEZŐ OLDAL ELŐTT (5-20 mp)
        if page < MAX_PAGES - 1:
            list_wait = random.uniform(5, 20)
            print(f"Visszatérés a listához, várakozás: {list_wait:.1f} mp...")
            time.sleep(list_wait)

    with open('hirdetesek.json', 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"Kész! Mentve: {len(all_items)} db.")

if __name__ == "__main__":
    scrape()
