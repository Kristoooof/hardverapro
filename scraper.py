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
MAX_PAGES = 5 

def extract_specs(title, desc):
    # Összefűzzük és megtisztítjuk a szöveget a felesleges szóközöktől
    txt = (title + ' ' + desc).replace('\xa0', ' ').replace('\t', ' ')
    t_lower = txt.lower()
    
    s = {
        'brand': 'Egyéb',
        'screenSize': None,
        'resolution': 'HD',
        'ramSize': None,
        'ramType': 'DDR4',
        'ssdSize': None,
        'cpuMfr': 'Ismeretlen',
        'cpuModel': '',
        'gpuMfr': 'Integrált',
        'gpuModel': ''
    }

    # --- MÁRKA ---
    brands = ['lenovo', 'dell', 'hp', 'asus', 'acer', 'apple', 'msi', 'toshiba', 'fujitsu', 'huawei', 'xiaomi', 'microsoft']
    for b in brands:
        if b in t_lower:
            s['brand'] = b.capitalize() if b != 'hp' else 'HP'
            break

    # --- CPU FELISMERÉS (Precízebb verzió) ---
    
    # 1. Intel Core Ultra (pl. Core Ultra 7 155H)
    if 'ultra' in t_lower:
        s['cpuMfr'] = 'Intel'
        m = re.search(r'ultra\s*([579])\s*([\w\d]+)', t_lower)
        if m:
            s['cpuModel'] = f"Core Ultra {m.group(1)} {m.group(2).upper()}"
        else:
            s['cpuModel'] = "Core Ultra"

    # 2. Intel Core i (pl. i7-1260P, i5 1335U, i7 1165G7)
    elif re.search(r'i[3579][\s\-]*\d', t_lower):
        s['cpuMfr'] = 'Intel'
        # Keresünk egy i-számot, majd egy kötőjelet vagy szóközt, utána a modellszámot betűkkel a végén
        m = re.search(r'(i[3579])[\s\-]*(\d{4,5}[a-z0-9]*)', t_lower)
        if m:
            s['cpuModel'] = f"{m.group(1).upper()}-{m.group(2).upper()}"

    # 3. AMD Ryzen (pl. Ryzen 7 7840HS, Ryzen 5 5600H)
    elif 'ryzen' in t_lower:
        s['cpuMfr'] = 'AMD'
        m = re.search(r'ryzen\s*([3579])\s*(\d{4}[a-z]*)', t_lower)
        if m:
            s['cpuModel'] = f"Ryzen {m.group(1)} {m.group(2).upper()}"
        else:
            m_simple = re.search(r'ryzen\s*([3579])', t_lower)
            if m_simple: s['cpuModel'] = f"Ryzen {m_simple.group(1)}"

    # 4. Apple M-széria
    elif 'm1' in t_lower or 'm2' in t_lower or 'm3' in t_lower:
        s['cpuMfr'] = 'Apple'
        m = re.search(r'(m[123]\s*(pro|max|ultra)?)', t_lower)
        if m: s['cpuModel'] = m.group(1).upper()

    # --- RAM, GPU, TÁRHELY (Marad a korábbi, stabil verzió) ---
    ram_m = re.search(r'(\d+)\s*gb', t_lower)
    if ram_m: s['ramSize'] = int(ram_m.group(1))
    
    ram_t = re.search(r'ddr\s*([1-5])', t_lower)
    if ram_t: s['ramType'] = f"DDR{ram_t.group(1)}"
    
    ssd_m = re.search(r'(\d+)\s*(gb|tb)\s*(ssd|nvme|m\.2)', t_lower)
    if ssd_m:
        size = int(ssd_m.group(1))
        s['ssdSize'] = size * 1024 if ssd_m.group(2) == 'tb' else size

    gpu_m = re.search(r'(rtx|gtx|rx)\s*(\d{3,4})', t_lower)
    if gpu_m:
        s['gpuMfr'] = 'NVIDIA' if gpu_m.group(1) != 'rx' else 'AMD'
        s['gpuModel'] = f"{gpu_m.group(1).upper()} {gpu_m.group(2)}"

    scr_m = re.search(r'(\d{2}(?:\.\d+)?)\s*(?:"|col)', t_lower)
    if scr_m: s['screenSize'] = float(scr_m.group(1))

    return s

def scrape():
    session = requests.Session()
    session.headers.update(HEADERS)
    all_items = []
    seen_links = set()

    for page in range(MAX_PAGES):
        offset = page * 100
        url = f"{BASE_URL}?offset={offset}"
        print(f"Oldal {page+1} lekérése...")

        try:
            resp = session.get(url, timeout=30) # Megemelt timeout
            soup = BeautifulSoup(resp.text, 'html.parser')
            ads = soup.select('li.media')
            if not ads: break

            for ad in ads:
                title_el = ad.select_one('.uad-col-title a')
                if not title_el: continue

                link = title_el['href']
                if not link.startswith('http'): link = 'https://hardverapro.hu' + link
                if link in seen_links: continue
                seen_links.add(link)

                title = title_el.get_text(strip=True)
                desc = title_el.get('title', '')
                
                # Ár és Kép
                price_text = ad.select_one('.uad-price').get_text(strip=True) if ad.select_one('.uad-price') else "0 Ft"
                price_val = int(re.sub(r'\D', '', price_text)) if re.sub(r'\D', '', price_text) else 0
                img_el = ad.select_one('.uad-image img')
                image = img_el.get('data-src') or img_el.get('src') or ""
                if image and not image.startswith('http'): image = 'https://hardverapro.hu' + image

                # Specifikációk kinyerése
                specs = extract_specs(title, desc)

                all_items.append({
                    'title': title,
                    'price': price_val,
                    'price_text': price_text,
                    'link': link,
                    'image': image,
                    'seller_name': ad.select_one('.uad-user-text').get_text(strip=True) if ad.select_one('.uad-user-text') else "Ismeretlen",
                    'city': ad.select_one('.uad-cities').get_text(strip=True) if ad.select_one('.uad-cities') else "",
                    **specs
                })

        except Exception as e:
            print(f"Hiba történt: {e}")
            break
        
        time.sleep(2)

    with open('hirdetesek.json', 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"Kész! {len(all_items)} hirdetés mentve.")

if __name__ == "__main__":
    scrape()
