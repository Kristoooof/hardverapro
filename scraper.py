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
MAX_PAGES = 10  # Állítsd be, hány oldalt szeretnél (1 oldal = 100 hirdetés)

def parse_price(text):
    if not text: return 0
    nums = re.sub(r'\D', '', text)
    return int(nums) if nums else 0

def scrape_everything():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_results = []
    seen_links = set() # Duplikátumok kiszűrésére

    for page in range(MAX_PAGES):
        offset = page * 100
        # Az első oldalnál nem feltétlen kell az offset, de nem rontja el
        current_url = f"{BASE_URL}?offset={offset}"
        
        print(f"[{page + 1}/{MAX_PAGES}] Oldal lekérése: {current_url}...")
        
        try:
            response = session.get(current_url, timeout=15)
            if response.status_code != 200:
                print(f"Hiba az oldalnál: {response.status_code}")
                break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            ads = soup.select('li.media')
            
            if not ads:
                print("Nincs több hirdetés ezen az oldalon.")
                break

            for ad in ads:
                title_el = ad.select_one('.uad-col-title a')
                if not title_el: continue
                
                link = title_el['href']
                if not link.startswith('http'):
                    link = 'https://hardverapro.hu' + link
                
                # Ha már láttuk ezt a hirdetést (pl. kiemelt hirdetés több oldalon is ott van)
                if link in seen_links:
                    continue
                seen_links.add(link)

                title = title_el.get_text(strip=True)
                price_text = ad.select_one('.uad-price').get_text(strip=True) if ad.select_one('.uad-price') else "0 Ft"
                seller = ad.select_one('.uad-user-text').get_text(strip=True) if ad.select_one('.uad-user-text') else "Ismeretlen"
                city = ad.select_one('.uad-cities').get_text(strip=True) if ad.select_one('.uad-cities') else ""

                all_results.append({
                    'title': title,
                    'link': link,
                    'price_text': price_text,
                    'price_value': parse_price(price_text),
                    'seller': seller,
                    'city': city
                })

            # Fontos: tartsunk szünetet az oldalak között, hogy ne tiltsanak ki!
            print(f"  -> Eddig összesen {len(all_results)} egyedi hirdetés.")
            time.sleep(2) 

        except Exception as e:
            print(f"Hiba történt a lapozás közben: {e}")
            break

    # Mentés
    if all_results:
        with open('hirdetesek.json', 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\nSiker! Összesen {len(all_results)} hirdetés elmentve a hirdetesek.json fájlba.")

if __name__ == "__main__":
    scrape_everything()
