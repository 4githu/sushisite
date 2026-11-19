"""Bounded, cached fetch of the public SNU Co-op daily menu; HTML is never sent to clients."""
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from threading import Lock
from time import monotonic
import httpx
from fastapi import HTTPException

URL = 'https://snuco.snu.ac.kr/foodmenu/'
_cache = {}
_lock = Lock()

class MenuParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.cell = None
        self.row = {}
        self.rows = []
        self.page_date = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'date': self.page_date = attrs.get('value')
        if tag == 'table' and 'menu-table' in attrs.get('class', '').split(): self.inside = True
        if not self.inside: return
        if tag == 'tr': self.row = {}
        if tag == 'td':
            self.cell = next((k for k in ('title','breakfast','lunch','dinner') if k in attrs.get('class','').split()), None)
            if self.cell: self.row[self.cell] = ''
        if tag in ('br','p','div') and self.cell: self.row[self.cell] += '\n'
    def handle_data(self, data):
        if self.inside and self.cell: self.row[self.cell] += data
    def handle_endtag(self, tag):
        if tag == 'td': self.cell = None
        if tag == 'tr' and self.inside:
            row = {k: '\n'.join(line.strip() for line in v.splitlines() if line.strip()) for k,v in self.row.items()}
            if row.get('title') and row['title'] != '식당': self.rows.append(row)
        if tag == 'table': self.inside = False

def menus(day: date):
    key = day.isoformat()
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < 900: return cached[1]
        try:
            response = httpx.get(URL, params={'date': key}, timeout=12, follow_redirects=True)
            response.raise_for_status()
            parser = MenuParser(); parser.feed(response.text)
            if parser.page_date != key or 'menu-table' not in response.text:
                raise ValueError('식단 페이지 형식이 변경되었습니다.')
            data = {'date': key, 'restaurants': parser.rows, 'source': URL+'?date='+key,
                    'fetchedAt': datetime.now(timezone.utc).isoformat(), 'stale': False}
            if len(_cache) >= 32: _cache.pop(next(iter(_cache)))
            _cache[key] = (monotonic(), data)
            return data
        except (httpx.HTTPError, ValueError):
            if cached: return {**cached[1], 'stale': True}
            raise HTTPException(503, '공식 식단을 불러오지 못했습니다. 잠시 후 다시 시도하거나 원문을 확인해주세요.')
