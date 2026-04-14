import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import time
import random
import os

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Macintosh; Intel Mac X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
]

BASE_URL = 'https://hardverapro.hu/aprok/notebook/pc/index.html'
MAX_PAGES = 5

def extract_specs(text_to_scan):
    # Tisztítás és normalizálás
    t_lower = text_to_scan.lower().replace('\xa0', ' ').replace('\t', ' ')
    
    s = {
        'brand': 'Egyéb',
        'screenSize': None,
        'refreshRate': None,
        'cpuMfr': 'Ismeretlen',
        'cpuModel': '',
        'gpuModel': '',
        'ramSize': None,
        'ramType': None, # ÚJ: DDR3, DDR4, stb.
        'ssdSize': None,
    }

    # --- Márka ---
    brands = ['lenovo', 'dell', 'hp', 'asus', 'acer', 'apple', 'msi']
    for b in brands:
        if b in t_lower:
            s['brand'] = b.capitalize() if b != 'hp' else 'HP'
            break

    # --- Kijelző ---
    screen_matches = re.finditer(r'(\d{2}(?:[.,]\d)?)\s*(?:"|col|''|\'|-as|-es|-os)', t_lower)
    for m in screen_matches:
        try:
            val = float(m.group(1).replace(',', '.'))
            if 10.0 <= val <= 21.0:
                s['screenSize'] = val
                break
        except: continue
    
    hz_m = re.search(r'(\d{2,3})\s*hz', t_lower)
    if hz_m:
        s['refreshRate'] = int(hz_m.group(1))

    # --- GPU Keresés (Javítva: Intel, Quadro és integrált kártyákhoz is) ---
    gpu_m = re.search(r'(rtx|gtx|rx|arc|radeon|geforce|quadro|iris|uhd|t\d{3,4})\s*(\d{3,4}|xe|graphics)?\s*(ti|xt)?', t_lower)
    if gpu_m:
        base = gpu_m.group(1).upper()
        num = gpu_m.group(2) if gpu_m.group(2) else ""
        suffix = " " + gpu_m.group(3).upper() if gpu_m.group(3) else ""
        s['gpuModel'] = f"{base} {num}{suffix}".strip()

    # --- CPU Keresés ---
    cpu_pattern = re.search(r'(ryzen\s*[3579]|i[3579])[\s\-]+(\d[\w\d\-]+)', t_lower)
    if cpu_pattern:
        prefix = cpu_pattern.group(1).upper()
        model = cpu_pattern.group(2).upper()
        s['cpuMfr'] = 'AMD' if 'RYZEN' in prefix else 'Intel'
        s['cpuModel'] = f"{prefix.replace(' ', '')}-{model}"
    elif 'ultra' in t_lower:
        s['cpuMfr'] = 'Intel'
        m = re.search(r'ultra\s*([579])\s*([\w\d]+)', t_lower)
        if m: s['cpuModel'] = f"Core Ultra {m.group(1)}-{m.group(2).upper()}"

    # --- RAM Méret és Típus ---
    ram_m = re.search(r'(\d+)\s*gb', t_lower)
    if ram_m:
        val = int(ram_m.group(1))
        if val <= 128:
            s['ramSize'] = val
        else:
            s['ssdSize'] = val

    # ÚJ: RAM típus (DDR3, DDR4, DDR5, LPDDR stb.)
    ram_type_m = re.search(r'(lpddr\d|ddr\d)', t_lower)
    if ram_type_m:
        s['ramType'] = ram_type_m.group(1).upper()

    # SSD dedikált keresés
    ssd_m = re.search(r'(\d+)\s*(gb|tb)\s*(ssd|nvme|m\.2|tárhely)', t_lower)
    if ssd_m:
        size = int(ssd_m.group(1))
        real_size = size * 1024 if ssd_m.group(2) == 'tb' else size
        if not s['ssdSize'] or real_size > s['ssdSize']:
            s['ssdSize'] = real_size

    return s

def scrape():
    all_items = []
    seen_links = set()
    filename = 'hirdetesek.json'

    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                all_items = json.load(f)
                seen_links = {item['link'] for item in all_items}
            print(f"Betöltve {len(seen_links)} korábbi hirdetés.")
        except:
            print("Hiba a fájl betöltésekor.")

    scraper = cloudscraper.create_scraper()
    selected_ua = random.choice(USER_AGENTS)
    
    headers = {
        'User-Agent': selected_ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    print("Munkamenet kezdése...")
    try:
        scraper.get("https://hardverapro.hu", headers=headers, timeout=30)
        time.sleep(random.uniform(3, 6))
    except: pass

    new_count = 0

    for page in range(MAX_PAGES):
        offset = page * 100
        current_list_url = f"{BASE_URL}?offset={offset}"
        print(f"--- {page+1}. oldal lekérése ---")
        
        headers['Referer'] = "https://hardverapro.hu"
        resp = scraper.get(current_list_url, headers=headers, timeout=30)
        if resp.status_code != 200: break

        soup = BeautifulSoup(resp.text, 'html.parser')
        ads = soup.select('li.media')

        for ad in ads:
            title_el = ad.select_one('.uad-col-title a')
            if not title_el: continue
            
            title_text = title_el.get_text(strip=True)
            
            # --- Bazár szűrés: ha többes szám vagy lista jellegű szavak vannak a címben ---
            bazaar_keywords = ['lista', 'válogatás', 'eladóak', 'laptopok', 'gépek', 'db', 'alkatrészek']
            if any(word in title_text.lower() for word in bazaar_keywords):
                continue

            link = title_el['href']
            if not link.startswith('http'): link = 'https://hardverapro.hu' + link
            
            if link in seen_links:
                continue 

            print(f"ÚJ HIRDETÉS! Elemzés: {link}")
            new_count += 1
            headers['Referer'] = current_list_url
            
            try:
                time.sleep(random.uniform(2, 4))
                ad_resp = scraper.get(link, headers=headers, timeout=30)
                ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
                
                full_text = ad_soup.get_text()
                specs = extract_specs(full_text)
                
                # --- Ár felismerés javítása (tisztán számként) ---
                price_el = ad_soup.select_one('.uad-price')
                price_raw = price_el.get_text(strip=True) if price_el else "0"
                price_clean = re.sub(r'[^\d]', '', price_raw)
                price_val = int(price_clean) if price_clean else 0

                # --- Eladó adatai ---
                seller_el = ad_soup.select_one('.uad-user a')
                seller_name = seller_el.get_text(strip=True) if seller_el else "Ismeretlen"
                
                rating_el = ad_soup.select_one('.uad-rating')
                seller_rating = rating_el.get_text(strip=True) if rating_el else "Nincs értékelés"
                
                all_items.append({
                    'title': title_text,
                    'link': link,
                    'price': price_val,
                    'seller': seller_name,
                    'rating': seller_rating,
                    'timestamp': time.time(),
                    **specs
                })
                seen_links.add(link)

                wait_time = random.uniform(25, 40)
                print(f"  Várakozás: {wait_time:.1f} mp...")
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"Hiba a hirdetésnél: {e}")
                continue

        if page < MAX_PAGES - 1:
            time.sleep(random.uniform(5, 10))

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    
    print(f"Kész! {new_count} új hirdetés hozzáadva.")

if __name__ == "__main__":
    scrape()
