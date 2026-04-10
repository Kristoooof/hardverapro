import requests
from bs4 import BeautifulSoup
import json
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.8',
}

BASE_URL = 'https://hardverapro.hu/aprok/notebook/pc/index.html'
MAX_PAGES = 5 # Állítsd be, hány oldalt töltsön le (1 oldal = 100 hirdetés)

def extract_specs(title, desc):
    """Kinyeri az adatokat a weboldal által elvárt formátumban."""
    txt = (title + ' ' + desc).lower()
    s = {
        'brand': 'Egyéb',
        'screenSize': None,
        'resolution': 'HD',
        'ramSize': None,
        'ssdSize': None,
        'cpuMfr': 'Ismeretlen',
        'cpuModel': '',
        'gpuMfr': 'Integrált',
        'gpuModel': ''
    }

    # MÁRKA
    brands = ['lenovo', 'dell', 'hp', 'asus', 'acer', 'apple', 'msi', 'toshiba', 'fujitsu', 'huawei', 'xiaomi', 'microsoft']
    for b in brands:
        if b in txt:
            s['brand'] = b.capitalize() if b != 'hp' else 'HP'
            break

    # KIJELZŐ MÉRET (számként)
    m = re.search(r'(\d{2}(?:\.\d+)?)\s*(?:"|col|\')', txt)
    if m:
        s['screenSize'] = float(m.group(1))

    # FELBONTÁS
    if any(x in txt for x in ['4k', 'uhd', '3840x']): s['resolution'] = '4K'
    elif any(x in txt for x in ['qhd', '2k', '2560x']): s['resolution'] = 'QHD'
    elif any(x in txt for x in ['fhd', '1920x', 'full hd']): s['resolution'] = 'FHD'

    # RAM (számként)
    m = re.search(r'(\d+)\s*gb\s*(ram|ddr)?', txt)
    if m:
        s['ramSize'] = int(m.group(1))

    # TÁRHELY (SSD/NVME - GB-ban kifejezve)
    m = re.search(r'(\d+)\s*(gb|tb)\s*(ssd|nvme|m\.2|hdd)', txt)
    if m:
        size = int(m.group(1))
        unit = m.group(2)
        s['ssdSize'] = size * 1024 if unit == 'tb' else size

    # CPU
    if 'intel' in txt or re.search(r'i[3579]-', txt):
        s['cpuMfr'] = 'Intel'
        m = re.search(r'(i[3579]-?\d{4,5}[a-z]*)', txt)
        if m: s['cpuModel'] = m.group(1).upper()
    elif 'ryzen' in txt or 'amd' in txt:
        s['cpuMfr'] = 'AMD'
        m = re.search(r'(ryzen\s?\d)', txt)
        if m: s['cpuModel'] = m.group(0).capitalize()
    elif 'm1' in txt or 'm2' in txt or 'm3' in txt:
        s['cpuMfr'] = 'Apple'
        m = re.search(r'(m[123]\s?(pro|max|ultra)?)', txt)
        if m: s['cpuModel'] = m.group(1).upper()

    # GPU
    m = re.search(r'(rtx|gtx|rx)\s?(\d{3,4})', txt)
    if m:
        s['gpuMfr'] = 'NVIDIA' if m.group(1) != 'rx' else 'AMD'
        s['gpuModel'] = f"{m.group(1).upper()} {m.group(2)}"

    return s

def scrape():
    session = requests.Session()
    session.headers.update(HEADERS)
    all_items = []
    seen_links = set()

    for page in range(MAX_PAGES):
        offset = page * 100
        url = f"{BASE_URL}?offset={offset}"
        print(f"Oldal {page+1} letöltése...")

        try:
            resp = session.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            ads = soup.select('li.media')

            for ad in ads:
                title_el = ad.select_one('.uad-col-title a')
                if not title_el: continue

                link = 'https://hardverapro.hu' + title_el['href'] if not title_el['href'].startswith('http') else title_el['href']
                if link in seen_links: continue
                seen_links.add(link)

                title = title_el.get_text(strip=True)
                desc = title_el.get('title', '')
                
                # Kép kinyerése
                img_el = ad.select_one('.uad-image img')
                image = ""
                if img_el:
                    image = img_el.get('data-src') or img_el.get('src') or ""
                    if image and not image.startswith('http'):
                        image = 'https://hardverapro.hu' + image

                # Ár számként
                price_el = ad.select_one('.uad-price')
                price_text = price_el.get_text(strip=True) if price_el else "0 Ft"
                price_val = int(re.sub(r'\D', '', price_text)) if re.sub(r'\D', '', price_text) else 0

                # Specifikációk
                specs = extract_specs(title, desc)

                # A weboldaladnak szükséges JSON objektum felépítése
                item = {
                    'title': title,
                    'price': price_val,
                    'price_text': price_text,
                    'link': link,
                    'image': image,
                    'seller_name': ad.select_one('.uad-user-text').get_text(strip=True) if ad.select_one('.uad-user-text') else "Ismeretlen",
                    'city': ad.select_one('.uad-cities').get_text(strip=True) if ad.select_one('.uad-cities') else "",
                    **specs
                }
                all_items.append(item)

        except Exception as e:
            print(f"Hiba az oldalnál: {e}")
            break
        
        time.sleep(1.5)

    # Mentés a weboldal által várt néven
    with open('hirdetesek.json', 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    
    print(f"\nKész! {len(all_items)} hirdetés mentve a hirdetesek.json-ba.")

if __name__ == "__main__":
    scrape()
