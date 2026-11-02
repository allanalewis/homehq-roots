#!/usr/bin/env python3
"""Publish reviewed data and queue unmapped daily words. No AI-generated etymology."""
import argparse
import datetime as dt
import json
import os
import tempfile
import time
import unicodedata
import urllib.error
from email.utils import parsedate_to_datetime
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
    body=json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
        name=stream.name
        stream.write(body)
    try:os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def normalize(value):
    return unicodedata.normalize('NFC',value.strip()).lower()

def text(value, limit):
    return isinstance(value, str) and 0 < len(value.strip()) <= limit and not re.search(r'[<>\x00-\x1f]',value)

def validate(pack):
    if not isinstance(pack,dict) or type(pack.get('schema')) is not int or pack.get('schema') != 1 or type(pack.get('version')) is not int or not 1 <= pack['version'] <= 9007199254740991:
        raise ValueError('Invalid catalog version')
    roots=pack.get('roots')
    if not isinstance(roots,list) or not 1 <= len(roots) <= 2000:raise ValueError('Invalid root count')
    ids=set()
    for r in roots:
        if not isinstance(r,dict):raise ValueError('Invalid root')
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
            if not isinstance(e,dict):raise ValueError('Invalid example')
            if not text(e.get('word'),40) or not text(e.get('focus'),35) or not isinstance(e.get('before'),str) or not isinstance(e.get('after'),str) or e['before']+e['focus']+e['after']!=e['word']:
                raise ValueError('Invalid example')
    choices={}
    for r in roots:
        if len({normalize(w) for w in r['words']})!=len(r['words']):raise ValueError('Duplicate word in root')
        for w in r['words']:choices.setdefault(normalize(w),set()).add(r['id'])
    primary=pack.get('primary',{})
    if not isinstance(primary,dict):raise ValueError('Invalid primary mappings')
    for word,root_id in primary.items():
        if word!=normalize(word) or root_id not in choices.get(word,set()):raise ValueError('Invalid primary root')
    if len(json.dumps(pack,ensure_ascii=False,indent=2).encode())+1>LIMIT:raise ValueError('Catalog too large')
    return pack

def publish(approved, previous):
    validate(approved);validate(previous)
    choices={}
    for r in approved['roots']:
        for w in r['words']:choices.setdefault(normalize(w),set()).add(r['id'])
    if any(len(ids)>1 and word not in approved.get('primary',{}) for word,ids in choices.items()):
        raise ValueError('Choose a primary root for ambiguous words')
    content={'roots':approved['roots'],'primary':approved.get('primary',{})}
    changed=any(content[k]!=previous.get(k,{}) for k in content)
    result={'schema':1,'version':previous['version']+changed,**content}
    return validate(result)

def parse_feed(raw):
    if len(raw)>LIMIT or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Unsafe/oversize RSS')
    decoded=raw.decode('utf-8-sig')
    if '\x00' in decoded:raise ValueError('Unexpected RSS encoding')
    items=ET.fromstring(decoded).findall('./channel/item')
    if not 1<=len(items)<=100:raise ValueError('Invalid RSS item count')
    out=[]
    for item in items:
        word=(item.findtext('title') or '').strip(); url=(item.findtext('link') or '').strip()
        u=urllib.parse.urlsplit(url)
        match=re.fullmatch(r'/word-of-the-day/[a-z0-9-]+-(\d{4}-\d{2}-\d{2})',u.path)
        if not text(word,80) or u.scheme!='https' or u.netloc!='www.merriam-webster.com' or u.query or u.fragment or not match:raise ValueError('Invalid daily word')
        dt.date.fromisoformat(match[1])
        out.append({'word':word,'date':match[1],'source':url})
    return sorted(out,key=lambda item:(item['date'],item['word']),reverse=True)

def decisions_valid(decisions,pack):
    if not isinstance(decisions,list):raise ValueError('Invalid review decisions')
    known={normalize(w) for r in pack['roots'] for w in r['words']}
    seen=set()
    for d in decisions:
        if not isinstance(d,dict) or any(not text(d.get(k),n) for k,n in [('word',80),('reason',500),('reviewer',80),('source',500)]):raise ValueError('Incomplete review decision')
        word=normalize(d['word'])
        if word in seen or word in known:raise ValueError('Duplicate/conflicting review decision')
        seen.add(word)
        if d.get('status') not in ('no-suitable-root','excluded'):raise ValueError('Invalid decision status')
        dt.date.fromisoformat(d['reviewed_on'])
        u=urllib.parse.urlsplit(d['source'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Invalid review source')
    return decisions

def queue_words(pack, words, previous, decisions=()):
    known={normalize(w) for r in pack['roots'] for w in r['words']}
    known.update(normalize(d['word']) for d in decisions)
    pending={}
    for item in [*previous,*words]:
        if not isinstance(item,dict) or not text(item.get('word'),80) or not text(item.get('source'),500):raise ValueError('Invalid queued word')
        dt.date.fromisoformat(item['date'])
        word=normalize(item['word'])
        if word not in known and (word not in pending or item['date']>pending[word]['date']):pending[word]=item
    # Never discard older unreviewed words to meet an arbitrary queue cap.
    return sorted(pending.values(),key=lambda e:(e['date'],e['word']),reverse=True)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected redirect')

def fetch_feed():
    request=urllib.request.Request(FEED,headers={'User-Agent':'HomeHQRoots/1.1 (+https://github.com/allanalewis/homehq-roots)'})
    for attempt in range(3):
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:
                return response.read(LIMIT+1)
        except urllib.error.HTTPError as error:
            if attempt==2 or error.code not in (429,500,502,503,504):raise
            wait=2**attempt
            retry=error.headers.get('Retry-After')
            if retry:
                try:wait=max(wait,int(retry))
                except ValueError:
                    try:wait=max(wait,(parsedate_to_datetime(retry)-dt.datetime.now(dt.timezone.utc)).total_seconds())
                    except (ValueError,TypeError):raise error
                # Defer a long server deadline to the next scheduled run.
                if wait>60:raise error
            time.sleep(wait)
        except (urllib.error.URLError,TimeoutError):
            if attempt==2:raise
            time.sleep(2**attempt)

def refresh(root=ROOT, fetch=fetch_feed, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    timestamp=now.isoformat(timespec='seconds')
    pack=publish(read(root/'approved-roots.json'),read(root/'roots-pack.json'))
    decisions=decisions_valid(read(root/'review-decisions.json'),pack)
    old_status=read(root/'status.json') if (root/'status.json').exists() else {}
    previous=read(root/'review-queue.json') if (root/'review-queue.json').exists() else []
    try:
        words=parse_feed(fetch())
        latest_date=dt.date.fromisoformat(words[0]['date'])
        age=(now.date()-latest_date).days
        if age<0:raise ValueError('Future feed edition')
        prior_latest=old_status.get('latest_word')
        regressed=prior_latest and prior_latest['date']>words[0]['date']
        state='ok' if age<=2 and not regressed else 'stale'
        last_success=timestamp
        latest=prior_latest if regressed else words[0]
    except (OSError,ValueError,ET.ParseError):
        words=[];state='unavailable'
        last_success=old_status.get('last_success_at')
        latest=old_status.get('latest_word')
    queue=queue_words(pack,words,previous,decisions)
    status={'checked_at':timestamp,'last_success_at':last_success,'feed_state':state,
            'latest_word':latest,'catalog_version':pack['version'],'root_count':len(pack['roots']),
            'pending_review':len(queue),'resolved_without_root':len(decisions)}
    # Generated files are exposed together by the workflow's single Git commit.
    write(root/'roots-pack.json',pack);write(root/'review-queue.json',queue);write(root/'status.json',status)
    print(f"Catalog v{pack['version']}; feed {state}; {len(queue)} pending reviews.")
    return status

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed-file',type=Path,help='Offline test input')
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    if args.validate_only:
        pack=publish(read(ROOT/'approved-roots.json'),read(ROOT/'roots-pack.json'))
        decisions_valid(read(ROOT/'review-decisions.json'),pack)
        queue_words(pack,[],read(ROOT/'review-queue.json'))
        return
    refresh(fetch=args.feed_file.read_bytes if args.feed_file else fetch_feed)

if __name__=='__main__':main()
