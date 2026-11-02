import copy
import unittest
from update import read,ROOT,validate,publish,parse_feed,queue_words

class Tests(unittest.TestCase):
    def setUp(self):self.pack=read(ROOT/'approved-roots.json')
    def test_catalog(self):validate(self.pack)
    def test_publish(self):
        old=copy.deepcopy(self.pack)
        self.assertEqual(publish(self.pack,old)['version'],old['version'])
        self.pack['roots'][0]['words'].append('telephone')
        self.assertEqual(publish(self.pack,old)['version'],old['version']+1)
    def test_bad_catalog(self):
        self.pack['roots'][0]['meaning']='<script>x</script>'
        with self.assertRaises(ValueError):validate(self.pack)
    def test_queue_no_guess(self):
        words=[{'word':'disparate','date':'2026-10-26','source':'https://example.com'}, {'word':'unknownword','date':'2026-11-01','source':'https://example.com'}]
        q=queue_words(self.pack,words,[])
        self.assertEqual([e['word'] for e in q],['unknownword'])
        self.assertEqual(queue_words(self.pack,words,q),q)
    def test_feed(self):
        raw=b'<rss><channel><item><title>disparate</title><link>https://www.merriam-webster.com/word-of-the-day/disparate-2026-10-26</link></item></channel></rss>'
        self.assertEqual(parse_feed(raw)[0]['word'],'disparate')
        for bad in [raw.replace(b'www.merriam-webster.com',b'evil.example'),b'<!DOCTYPE rss>'+raw,b'<rss/>']:
            with self.assertRaises(ValueError):parse_feed(bad)


class ReliabilityTests(unittest.TestCase):
    def setUp(self):self.pack=read(ROOT/'approved-roots.json')
    def test_invalid_types(self):
        for value in [None,[],{'schema':True,'version':1,'roots':[]}]:
            with self.assertRaises(ValueError):validate(value)
    def test_primary_required(self):
        broken=copy.deepcopy(self.pack);broken.pop('primary')
        with self.assertRaises(ValueError):publish(broken,self.pack)
    def test_bad_primary(self):
        self.pack['primary']['biology']='tele'
        with self.assertRaises(ValueError):validate(self.pack)
    def test_queue_never_truncates(self):
        entries=[{'word':f'word{i}','date':'2026-11-01','source':'https://example.com'} for i in range(1100)]
        self.assertEqual(len(queue_words(self.pack,entries,[])),1100)
    def test_older_repeat_cannot_replace_newer(self):
        newer={'word':'unknown','date':'2026-11-01','source':'https://example.com'}
        older={**newer,'date':'2026-10-01'}
        self.assertEqual(queue_words(self.pack,[older],[newer]),[newer])
    def test_explicit_review_resolution(self):
        from update import decisions_valid
        entry={'word':'unknown','date':'2026-11-01','source':'https://example.com'}
        decision={'word':'unknown','reason':'No supported root','source':'https://example.com','reviewer':'test','reviewed_on':'2026-11-01','status':'no-suitable-root'}
        decisions_valid([decision],self.pack)
        self.assertEqual(queue_words(self.pack,[entry],[],[decision]),[])
        decision['word']='disparate'
        with self.assertRaises(ValueError):decisions_valid([decision],self.pack)
    def test_feed_order(self):
        raw=b'<rss><channel><item><title>old</title><link>https://www.merriam-webster.com/word-of-the-day/old-2026-10-01</link></item><item><title>new</title><link>https://www.merriam-webster.com/word-of-the-day/new-2026-11-01</link></item></channel></rss>'
        self.assertEqual(parse_feed(raw)[0]['word'],'new')
    def test_outage_does_not_block_approved_publication(self):
        import tempfile,datetime
        from pathlib import Path
        from update import write,refresh
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);write(root/'roots-pack.json',self.pack)
            approved=copy.deepcopy(self.pack);approved['roots'][0]['words'].append('telephone')
            write(root/'approved-roots.json',approved);write(root/'review-decisions.json',[])
            queue=[{'word':'unknown','date':'2026-11-01','source':'https://example.com'}]
            write(root/'review-queue.json',queue)
            def down():raise OSError('offline')
            status=refresh(root,down,datetime.datetime(2026,11,2,tzinfo=datetime.timezone.utc))
            self.assertEqual(status['feed_state'],'unavailable')
            self.assertEqual(read(root/'roots-pack.json')['version'],self.pack['version']+1)
            self.assertEqual(read(root/'review-queue.json'),queue)



class FetchTests(unittest.TestCase):
    def test_retry_after_does_not_hammer_source(self):
        from update import fetch_feed
        import urllib.error
        from unittest.mock import patch,MagicMock
        error=urllib.error.HTTPError('https://example.com',429,'limited',{'Retry-After':'3600'},None)
        opener=MagicMock();opener.open.side_effect=error
        with patch('update.urllib.request.build_opener',return_value=opener),patch('update.time.sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):fetch_feed()
            self.assertEqual(opener.open.call_count,1);sleep.assert_not_called()
        error.close()

if __name__=='__main__':unittest.main()
