#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urljoin
import requests, re, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from email.utils import formatdate

BASE = 'https://noticias.ai'
OUT = Path(__file__).resolve().parent / 'noticias-ai-feed.xml'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

html = requests.get(BASE, timeout=30, headers=HEADERS).text
soup = BeautifulSoup(html, 'html.parser')

items, seen = [], set()
for a in soup.select('a[href]'):
    href = a.get('href', '').strip()
    text = ' '.join(a.get_text(' ', strip=True).split())
    if not href or href.startswith('#'):
        continue
    full = urljoin(BASE, href)
    if not full.startswith(BASE):
        continue
    if '/wp-content/' in full or any(full.endswith(ext) for ext in ('.jpg','.jpeg','.png','.webp','.gif','.svg','.pdf')):
        continue
    if len(text) < 8 or text.lower() in {'leer más', 'read more', 'inicio', 'home'}:
        continue
    key = (full, text)
    if key in seen:
        continue
    seen.add(key)
    score = 0
    if len(text) > 20: score += 2
    if re.search(r'/20\d{2}/|/\d{4}/\d{2}/', full): score += 3
    if full.count('-') >= 3: score += 2
    if any(seg in full for seg in ('/machine-learning/','/infraestructura/','/general/','/noticias/','/notas-de-prensa/')): score += 1
    items.append((score, text, full))

items.sort(key=lambda x: (-x[0], x[1]))
selected, used = [], set()
for score, title, link in items:
    if link in used:
        continue
    used.add(link)
    selected.append((title, link))
    if len(selected) >= 20:
        break

rss = ET.Element('rss', version='2.0')
channel = ET.SubElement(rss, 'channel')
ET.SubElement(channel, 'title').text = 'Noticias.ai (feed no oficial)'
ET.SubElement(channel, 'link').text = BASE
ET.SubElement(channel, 'description').text = 'Feed RSS no oficial generado a partir de la portada de noticias.ai'
ET.SubElement(channel, 'language').text = 'es'
ET.SubElement(channel, 'lastBuildDate').text = formatdate(usegmt=True)

for title, link in selected:
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = link
    ET.SubElement(item, 'guid').text = link
    ET.SubElement(item, 'pubDate').text = formatdate(usegmt=True)
    ET.SubElement(item, 'description').text = title

with open(OUT, 'wb') as f:
    f.write(ET.tostring(rss, encoding='utf-8', xml_declaration=True))

print(f'Escrito {OUT} con {len(selected)} items')
