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
    t_lower = text_to_scan.lower().replace('\xa0', ' ').replace('\t', ' ')
    
    s = {
        'brand': 'Egyéb',
        'screenSize': None,
        'refreshRate': None,
        'cpuMfr': 'Ismeretlen',
        'cpuModel': '',
        'gpuModel': None,
        'ramSize': None,
        'ramType': None,
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

    # --- GPU Keresés (Szigorított) ---
    # Kulcsszó után kötelezően várunk egy modellszámot (pl. 3060, 1650, 6800, A770)
    gpu_pattern = re.search(r'(rtx|gtx|geforce|rx|radeon|arc|intel|quadro)\s*(\d{3,4}(?:\s*(?:ti|xt|max-q))?)', t_lower)
    if gpu_pattern:
        brand_part = gpu_pattern.group(1).upper()
        model_part = gpu_pattern.group(2).upper()
        # "Hülye" modellek kiszűrése (pl. ha a szám túl nagy vagy irreleváns tartományba esik)
        try:
            model_num = int(re.search(r'\d+', model_part).group())
            if 100 <= model_num <= 9000: # Reális GPU modellszám tartomány
                s['gpuModel'] = f"{brand_part} {model_part}"
        except:
            s['gpuModel'] = None

    # --- CPU Keresés ---
    cpu_pattern = re.search(r'(ryzen\s*[3579]|i[3579])[\s\-]+(\d[\w\d\-]+)', t_lower)
    if cpu_pattern:
        prefix = cpu_pattern.group(1).upper()
        model = cpu_pattern.group(2).upper()
        s['cpuMfr'] = 'AMD' if 'RYZEN' in prefix else 'Intel'
        s['cpuModel'] = f"{prefix.replace(' ', '')}-{model}"

    # --- RAM Méret és Típus (Szűrt) ---
    ram_m = re.search(r'(\d+)\s*gb', t_lower)
    if ram_m:
        val = int(ram_m.group(1))
        if val <= 128: s['ramSize'] = val

    # Csak DDR3, 4, 5 és LPDDR3, 4, 5 engedélyezett
    ram_type_m = re.search(r'(lpddr|ddr)(\d)', t_lower)
    if ram_type_m:
        gen = ram_type_m.group(2)
        if gen in ['3', '4', '5']:
            s['ramType'] = ram_type_m.group(1).upper() + gen

    # SSD
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
        except: pass

    scraper = cloudscraper.create_scraper()
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    for page in range(MAX_PAGES):
        offset = page * 100
        current_list_url = f"{BASE_URL}?offset={offset}"
        print(f"--- {page+1}. oldal lekérése ---")
        
        resp = scraper.get(current_list_url, headers=headers, timeout=30)
        if resp.status_code != 200: break
        soup = BeautifulSoup(resp.text, 'html.parser')
        ads = soup.select('li.media')

        for ad in ads:
            title_el = ad.select_one('.uad-col-title a')
            if not title_el: continue
            
            title_text = title_el.get_text(strip=True)
            if any(word in title_text.lower() for word in ['lista', 'válogatás', 'laptopok', 'db']):
                continue

            link = title_el['href']
            if not link.startswith('http'): link = 'https://hardverapro.hu' + link
            if link in seen_links: continue 

            try:
                time.sleep(random.uniform(2, 4))
                ad_resp = scraper.get(link, headers=headers, timeout=30)
                ad_soup = BeautifulSoup(ad_resp.text, 'html.parser')
                
                # --- Ár kinyerése és szűrése ---
                price_box = ad_soup.select_one('.uad-details')
                price_val = 0
                if price_box and price_box.find('h2'):
                    price_text = price_box.find('h2').get_text(strip=True)
                    price_digits = re.sub(r'[^\d]', '', price_text)
                    price_val = int(price_digits) if price_digits else 0
                
                if price_val < 20000:
                    print(f"Átugorva (olcsó): {price_val} Ft")
                    continue

                full_text = ad_soup.get_text()
                specs = extract_specs(full_text)
                
                seller_el = ad_soup.select_one('.uad-user a')
                rating_el = ad_soup.select_one('.uad-rating')

                all_items.append({
                    'title': title_text,
                    'link': link,
                    'price': price_val,
                    'seller': seller_el.get_text(strip=True) if seller_el else "Ismeretlen",
                    'rating': rating_el.get_text(strip=True) if rating_el else "Nincs",
                    'timestamp': time.time(),
                    **specs
                })
                seen_links.add(link)
                print(f"Mentve: {title_text[:40]}... ({price_val} Ft)")
                time.sleep(random.uniform(20, 30))
                
            except Exception as e:
                print(f"Hiba: {e}")
                continue

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    scrape()
