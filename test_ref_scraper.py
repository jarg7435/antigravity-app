import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

def test_marca():
    url = "https://www.marca.com/futbol/primera-division/calendario.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        print("Marca fetched!")
        links = soup.find_all('a', href=True)
        for a in links:
            if 'rayo' in a['href'] and 'athletic' in a['href'] and 'previa' in a['href']:
                print("Found match link:", a['href'])
                
                # Fetch article
                resp2 = requests.get(a['href'], headers=HEADERS, timeout=12)
                soup2 = BeautifulSoup(resp2.text, 'html.parser')
                texto = soup2.get_text(separator=' ', strip=True)
                
                for sentence in texto.split('.'):
                    if 'arbitr' in sentence.lower() or 'árbitr' in sentence.lower():
                        print("Sentence with arbitro:", sentence.strip())
                        
                break # Only process first link
    except Exception as e:
        print("Error:", e)

test_marca()

def test_comuniate():
    url = "https://www.comuniate.com/partidos/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        print("Comuniate fetched!")
        
        # In comuniate, matches are usually in a list
        match = soup.find(text=re.compile(r'Rayo.*?Athletic', re.I))
        if match:
             print("Match found by text")
             
        links = soup.find_all('a', href=True)
        for a in links:
            if 'partido' in a['href'] and ('rayo' in a['href'] or 'athletic' in a['href']):
                print("Found match link:", a['href'])
                
                # Fetch match page
                match_url = a['href']
                if not match_url.startswith('http'): match_url = "https://www.comuniate.com" + match_url
                resp2 = requests.get(match_url, headers=HEADERS, timeout=12)
                soup2 = BeautifulSoup(resp2.text, 'html.parser')
                
                ref_tags = soup2.find_all(string=re.compile(r'Árbitro|Arbitro', re.I))
                for rt in ref_tags:
                    print(rt.parent.parent.get_text())
    except Exception as e:
        print("Error:", e)

test_comuniate()

def dump_rfef():
    url = "https://rfef.es/es/comites/comite-tecnico-de-arbitros/designaciones-arbitrales"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        with open("rfef_test.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Done rfef correct url")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        for a in links:
            text = a.get_text(strip=True)
            if 'primera' in text.lower() or '1a' in text.lower() or '1ª' in text.lower() or 'jornada' in text.lower():
                print("Possible PDF link:", a['href'], text)
                
    except Exception as e:
        print(e)

def test_dfb_links():
    url = "https://www.dfb.de/schiedsrichter/ansetzungen/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        print("DFB Fetched:", resp.status_code)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if 'ansetzungen' in a['href'].lower() or 'schiedsrichter' in a['href'].lower():
                print(f"Link: {a['href']} - Text: {a.get_text(strip=True)}")
    except Exception as e:
        print("Error:", e)

test_dfb_links()

def test_as():
    url = "https://resultados.as.com/resultados/futbol/primera/jornada/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        with open("as_test.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("Done AS")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Print all links that might be a match
        for a in soup.find_all('a', href=True):
            if 'rayo' in a['href'] or 'athletic' in a['href']:
                print(a['href'])
    except Exception as e:
        print(e)

# test_proxy()
# test_marca()
# test_as()
# test_rfef2()
def test_rf_bundesliga():
    url = "https://www.resultados-futbol.com/bundesliga"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        print("RF Bundesliga Fetched:", len(resp.text))
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        home_kw = "Leverkusen"
        away_kw = "Mainz"
        
        match_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if '/partido/' in href and home_kw.lower() in href and away_kw.lower() in href:
                match_link = a['href']
                print("Found match link:", match_link)
                break
                
        if match_link:
            m_url = match_link if match_link.startswith('http') else "https://www.resultados-futbol.com" + match_link
            resp2 = requests.get(m_url, headers=HEADERS, timeout=12)
            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            for rt in soup2.find_all(string=re.compile(r'(?i)arbitro|árbitro')):
                text = rt.parent.parent.get_text(separator=' ', strip=True)
                print("Found referee text in RF:", text)
    except Exception as e:
        print("Error:", e)

test_rf_bundesliga()

# test_proxy()
# test_marca()
# test_as()
# test_rfef2()
from src.data.scrapers.js_scraper import get_html_with_js

def test_kicker_js():
    url = "https://www.kicker.de/bundesliga/aufstellungen"
    try:
        html = get_html_with_js(url)
        print("Kicker JS Fetched:", len(html))
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            # ... search for match ...
            home_kw = "Leverkusen"
            away_kw = "Mainz"
            match_link = None
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if ('analyse' in href or 'direkt' in href) and home_kw.lower() in href and away_kw.lower() in href:
                    match_link = a['href']
                    print("Found JS Kicker match link:", match_link)
                    break
    except Exception as e:
        print("JS Error:", e)

test_kicker_js()

import datetime
from src.data.scrapers.bundesliga import BundesligaDataScraper
from src.data.multi_source_fetcher import MultiSourceFetcher

scraper = MultiSourceFetcher()
date = datetime.datetime.now()
res = scraper.fetch_referee("Bayer Leverkusen", "Mainz 05", date, "Bundesliga")
print(res)
