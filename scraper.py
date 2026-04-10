"""
Hardverapró laptop hirdetés scraper
Telepítés: pip install requests beautifulsoup4
Használat: python scraper.py
Output: hirdetesek.json
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'hu-HU,hu;q=0.9',
}

def extract_specs(title, desc):
    """Kinyeri a specifikációkat a címből és leírásból."""
    txt = (title + ' ' + desc).replace('\xa0', ' ').replace('\t', ' ')
    t = txt.lower()
    s = {}

    # Márka
    brands = ['huawei','xiaomi','microsoft','razer','lenovo','samsung',
              'toshiba','fujitsu','medion','asus','acer','dell','apple','msi','hp','lg']
    for b in brands:
        if b in t:
            s['brand'] = b[0].upper() + b[1:]
            break

    # Kijelző méret
    m = re.search(r'(\d{2}(?:\.\d+)?)\s*[""]', txt)
    if m:
        s['screenSize'] = float(m.group(1))

    # Felbontás
    if re.search(r'\b(4k|uhd|3840x2160|3456x2160|3024x1964)\b', t):
        s['resolution'] = '4K / QHD+'
    elif re.search(r'\b(qhd|wqhd|2560x1600|2560x1440|wqxga)\b', t):
        s['resolution'] = 'QHD'
    elif re.search(r'\b(fhd\+?|full\s*hd|1920x1080|2880x1800)\b', t):
        s['resolution'] = 'FHD'
    elif re.search(r'\b(hd\+|1600x900)\b', t):
        s['resolution'] = 'HD+'
    elif re.search(r'\b(hd[^+]|1366x768|1280x720)\b', t):
        s['resolution'] = 'HD'

    # RAM típus + méret
    m = re.search(r'(\d+)\s*gb\s*(lpddr)?\s*(ddr[345])?', txt, re.I)
    if m:
        s['ramSize'] = int(m.group(1))
        if m.group(3):
            s['ramType'] = m.group(3).upper()
        elif m.group(2):
            s['ramType'] = 'LP' + m.group(2).upper()

    # SSD
    m = re.search(r'(\d+)\s*(tb|gb)\s*(?:ssd|nvme|m\.?2)', txt, re.I)
    if m:
        s['ssdSize'] = int(m.group(1)) * (1024 if m.group(2).lower() == 'tb' else 1)
    else:
        m = re.search(r'(?:ssd|nvme|m\.?2|tárhely)\s*:?\s*(\d+)\s*(tb|gb)', txt, re.I)
        if m:
            s['ssdSize'] = int(m.group(1)) * (1024 if m.group(2).lower() == 'tb' else 1)

    # CPU
    m = re.search(r'(i[3579])-(\d{4,5}[a-z]*)', txt, re.I)
    if m:
        s['cpuMfr'] = 'Intel'
        s['cpuModel'] = m.group(1).upper() + '-' + m.group(2).upper()
    else:
        m = re.search(r'(ryzen\s*[3579])\s*(\d{4}[a-z]*)', txt, re.I)
        if m:
            s['cpuMfr'] = 'AMD'
            name = re.sub(r'\b\w', lambda c: c.upper(), m.group(1).strip())
            s['cpuModel'] = name + ' ' + m.group(2).upper()
        elif re.search(r'\bm[123]\b', t) and ('macbook' in t or 'apple' in t):
            m = re.search(r'(m[123])\s*(pro|max|ultra)?', txt, re.I)
            if m:
                s['cpuMfr'] = 'Apple'
                s['cpuModel'] = m.group(1).upper() + (m.group(2) and ' ' + m.group(2)[0].upper() + m.group(2)[1:].lower() or '')

    # GPU
    m = re.search(r'(rtx|gtx)\s*(\d{3,4})', txt, re.I)
    if m:
        s['gpuMfr'] = 'NVIDIA'
        s['gpuModel'] = m.group(1).upper() + ' ' + m.group(2)
    else:
        m = re.search(r'(?:rx|radeon)\s*(\d{3,4})\s*(m|s|xt)?', txt, re.I)
        if m:
            s['gpuMfr'] = 'AMD'
            s['gpuModel'] = 'RX ' + m.group(1) + (m.group(2) and m.group(2).upper() or '')
    if 'gpuMfr' not in s and re.search(r'iris\s*(xe|plus|pro)|uhd\s*graphics|intel\s*(iris|uhd|hd)\s*graphics', t):
        s['gpuMfr'] = 'Intel'
        s['gpuModel'] = 'Integrált'

    # Modell
    patterns = [
        r'(?:thinkpad|thinkbook|ideapad|legion|yoga)\s*[\w\d\-., ]+',
        r'(?:latitude|precision|inspiron|xps|vostro)\s*[\w\d\-., ]+',
        r'(?:elitebook|probook|omen|pavilion|zbook|spectre|envy)\s*[\w\d\-., ]+',
        r'(?:rog\s*(?:strix|zephyr|flow)?|vivobook|zenbook|tuf)\s*[\w\d\-., ]+',
        r'(?:aspire|swift|nitro|predator)\s*[\w\d\-., ]+',
        r'(?:katana|bravo|cyborg|gl|gf|gp|gs|ge)\s*[\w\d\-., ]+',
        r'(?:macbook\s*(?:air|pro))[\w\d\-., ]*',
        r'(?:surface\s*(?:laptop|pro|book))[\w\d\-., ]*',
        r'(?:matebook)\s*[\w\d\-., ]+',
    ]
    for p in patterns:
        m = re.search(p, txt, re.I)
        if m:
            model = m.group(0).strip().replace(' ', ' ').rstrip(' ,.-')
            words = model.split(' ')
            s['model'] = ' '.join(words[:5]) if len(words) > 5 else model
            break

    return s


def scrape_page(url):
    """Egy listaoldal scrapelése."""
    print(f' Lekérem: {url}')
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    items = []

    # Hardverapró lista struktúra
    ads = soup.select('.uad, .listed-ad, [data-ad-id], .ad-item')
    if not ads:
        # Fallback: linkek alapján
        for a in soup.select('a[href*="/aprok/laptop_notebook/elado"]'):
            title = a.get_text(strip=True)
            if len(title) < 10:
                continue
            parent = a.find_parent(['tr', 'li', 'div'])
            price_text = ''
            if parent:
                pm = re.search(r'(\d[\d\s.]*)\s*ft', parent.get_text(), re.I)
                if pm:
                    price_text = pm.group(0)
            items.append({
                'title': title,
                'desc': '',
                'price_text': price_text,
                'link': a.get('href', ''),
                'image': '',
                'seller_name': '',
                'seller_pos': 0,
                'seller_neg': 0,
            })
        return items

    for ad in ads:
        a_tag = ad.select_one('a[href*="/aprok/"]')
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        if len(title) < 10:
            continue

        # Ár
        price_el = ad.select_one('[class*="price"], .uad-price')
        price_text = price_el.get_text(strip=True) if price_el else ''

        # Leírás
        desc_el = ad.select_one('[class*="desc"], .uad-desc, [class*="info"]')
        desc = desc_el.get_text(strip=True) if desc_el else ''

        # Kép
        img_el = ad.select_one('img')
        image = ''
        if img_el:
            image = img_el.get('data-src') or img_el.get('src') or ''

        # Link
        link = a_tag.get('href', '')
        if link and not link.startswith('http'):
            link = 'https://hardverapro.hu' + link

        # Eladó
        seller_el = ad.select_one('a[href*="/felhasznalo/"], [class*="user"], [class*="seller"]')
        seller_name = seller_el.get_text(strip=True) if seller_el else ''

        # Értékelések
        seller_pos, seller_neg = 0, 0
        rating_els = ad.select('[class*="rating"], [class*="eval"]')
        if rating_els:
            rt = rating_els[0].get_text()
            pm = re.search(r'\+(\d+)', rt)
            if pm:
                seller_pos = int(pm.group(1))
            nm = re.search(r'[-–](\d+)', rt)
            if nm:
                seller_neg = int(nm.group(1))

        items.append({
            'title': title,
            'desc': desc,
            'price_text': price_text,
            'link': link,
            'image': image,
            'seller_name': seller_name,
            'seller_pos': seller_pos,
            'seller_neg': seller_neg,
        })

    return items


def parse_price(text):
    """Ár szövegből szám."""
    if not text:
        return None
    m = re.search(r'(\d[\d\s.]*)\s*ft', text, re.I)
    if m:
        return int(m.group(1).replace(' ', '').replace('.', ''))
    return None


def main():
    print('='*50)
    print('Hardverapró Laptop Scraper')
    print('='*50)

    all_items = []
    pages = 5 # Ennyi oldalt nézünk végig

    for i in range(1, pages + 1):
        url = f'https://hardverapro.hu/aprok/laptop_notebook/{i + "/" if i > 1 else ""}'
        try:
            items = scrape_page(url)
            print(f' -> {len(items)} hirdetés találva')
            all_items.extend(items)
        except Exception as e:
            print(f' -> HIBA: {e}')
        time.sleep(1.5) # Polite scraping

    if not all_items:
        print('\nNem sikerült egy hirdetést sem lekérni.')
        return

    print(f'\nÖsszesen {len(all_items)} hirdetés feldolgozása...')

    # Specifikációk kinyerése + JSON formátum
    output = []
    for item in all_items:
        specs = extract_specs(item['title'], item['desc'] + ' ' + item['price_text'])
        output.append({
            'title': item['title'],
            'desc': item['desc'],
            'price': parse_price(item['price_text']),
            'link': item['link'],
            'image': item['image'],
            'seller': {
                'name': item['seller_name'] or 'Ismeretlen',
                'pos': item['seller_pos'],
                'neg': item['seller_neg'],
            },
            'brand': specs.get('brand', ''),
            'screenSize': specs.get('screenSize'),
            'resolution': specs.get('resolution', ''),
            'ramType': specs.get('ramType', ''),
            'ramSize': specs.get('ramSize'),
            'ssdSize': specs.get('ssdSize'),
            'cpuMfr': specs.get('cpuMfr', ''),
            'cpuModel': specs.get('cpuModel', ''),
            'gpuMfr': specs.get('gpuMfr', ''),
            'gpuModel': specs.get('gpuModel', ''),
            'model': specs.get('model', ''),
        })

    # Fájlba írás
    filename = 'hirdetesek.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\nKész! {len(output)} hirdetés mentve: {filename}')
    print(f'Fájlméret: {len(json.dumps(output, ensure_ascii=False)) // 1024} KB')
    print(f'\nTöltsd fel a GitHub repódba, majd frissítsd a DATA_URL-t az HTML-ben!')


if __name__ == '__main__':
    main()