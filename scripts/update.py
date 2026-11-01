#!/usr/bin/env python3
"""Publish reviewed data and queue unmapped daily words. No AI-generated etymology."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FEED = 'https://www.merriam-webster.com/wotd/feed/rss2'
LIMIT = 2 * 1024 * 1024

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def text(value, limit):
    return isinstance(value, str) and 0 < len(value.strip()) <= limit and not re.search(r'[<>\x00-\x1f]',value)

def validate(pack):
    if pack.get('schema') != 1 or type(pack.get('version')) is not int or not 1 <= pack['version'] <= 9007199254740991:
        raise ValueError('Invalid catalog version')
    roots=pack.get('roots')
    if not isinstance(roots,list) or not 1 <= len(roots) <= 2000:raise ValueError('Invalid root count')
    ids=set()
    for r in roots:
        for key,limit in [('id',60),('form',35),('language',40),('kind',40),('meaning',100),('source',500)]:
            if not text(r.get(key),limit):raise ValueError('Invalid '+key)
        if r['id'] in ids:raise ValueError('Duplicate root ID')
        ids.add(r['id'])
        u=urllib.parse.urlsplit(r['source'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Invalid source')
        words=r.get('words')
        if not isinstance(words,list) or not 1<=len(words)<=200 or any(not text(w,80) for w in words):raise ValueError('Invalid mappings')
        examples=r.get('examples')
        if not isinstance(examples,list) or len(examples)!=2:raise ValueError('Two reviewed examples required')
        for e in examples:
            if not text(e.get('word'),40) or not text(e.get('focus'),35) or not isinstance(e.get('before'),str) or not isinstance(e.get('after'),str) or e['before']+e['focus']+e['after']!=e['word']:
                raise ValueError('Invalid example')
    if len(json.dumps(pack,ensure_ascii=False).encode())>LIMIT:raise ValueError('Catalog too large')
    return pack

def publish(approved, previous):
    validate(approved);validate(previous)
    return {'schema':1,'version':previous['version']+(approved['roots']!=previous['roots']), 'roots':approved['roots']}

def parse_feed(raw):
    if len(raw)>LIMIT or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Unsafe/oversize RSS')
    items=ET.fromstring(raw).findall('./channel/item')
    if not 1<=len(items)<=100:raise ValueError('Invalid RSS item count')
    out=[]
    for item in items:
        word=(item.findtext('title') or '').strip(); url=(item.findtext('link') or '').strip()
        u=urllib.parse.urlsplit(url)
        match=re.fullmatch(r'/word-of-the-day/[a-z0-9-]+-(\d{4}-\d{2}-\d{2})',u.path)
        if not text(word,80) or u.scheme!='https' or u.netloc!='www.merriam-webster.com' or u.query or u.fragment or not match:raise ValueError('Invalid daily word')
        dt.date.fromisoformat(match[1])
        out.append({'word':word,'date':match[1],'source':url})
    return out

def queue_words(pack, words, previous):
    known={w.strip().casefold() for r in pack['roots'] for w in r['words']}
    pending={e['word'].casefold():e for e in previous if e['word'].casefold() not in known}
    for item in words:
        if item['word'].casefold() not in known:pending[item['word'].casefold()]=item
    return sorted(pending.values(),key=lambda e:(e['date'],e['word']),reverse=True)[:1000]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed-file',type=Path,help='Offline test input')
    args=parser.parse_args()
    # Network and parsing must succeed before writing any files.
    if args.feed_file:raw=args.feed_file.read_bytes()
    else:
        req=urllib.request.Request(FEED,headers={'User-Agent':'HomeHQRoots/1.0 (+https://github.com/allanalewis/homehq-roots)'})
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.url!=FEED:raise ValueError('Unexpected redirect')
            raw=response.read(LIMIT+1)
    words=parse_feed(raw)
    pack=publish(read(ROOT/'approved-roots.json'),read(ROOT/'roots-pack.json'))
    queue_path=ROOT/'review-queue.json'
    queue=queue_words(pack,words,read(queue_path) if queue_path.exists() else [])
    write(ROOT/'roots-pack.json',pack)
    write(queue_path,queue)
    write(ROOT/'status.json',{'checked_on':dt.datetime.now(dt.timezone.utc).date().isoformat(),'latest_word':words[0], 'catalog_version':pack['version'],'root_count':len(pack['roots']),'pending_review':len(queue)})
    print(f"Published version {pack['version']}; {len(queue)} words need review. No unreviewed definitions published.")

if __name__=='__main__':main()
