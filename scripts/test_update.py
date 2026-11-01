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

if __name__=='__main__':unittest.main()
