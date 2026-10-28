import unittest
from types import SimpleNamespace
from streaming import LiveSession, Cancelled

class QueueTests(unittest.TestCase):
    def make(self, policy):
        wrapper=SimpleNamespace(model=SimpleNamespace(talker=None,
            config=SimpleNamespace(tts_eos_token_id=100,tts_pad_token_id=101)))
        s=LiveSession(wrapper, lambda *a:None,starvation=policy)
        s.embed=lambda x:x
        s.tokenize_offsets=lambda text:(list(map(ord,text)),[(i,i+1) for i in range(len(text))])
        return s
    def test_seal_does_not_consume_late_text(self):
        s=self.make('segment')
        self.assertEqual(s.next_embedding(),[100])
        self.assertFalse(s.session_ended)
        s.feed('好');s.end()
        self.assertEqual(s.next_embedding(),[101])
        self.assertEqual(s.get(),'好')
        s.ended=False
        self.assertEqual(s.next_embedding(),[100])
        self.assertTrue(s.session_ended)
    def test_queued_text_precedes_end(self):
        s=self.make('segment');s.feed('甲乙');s.feed('丙');s.end()
        self.assertEqual([s.next_embedding() for _ in range(4)],[[ord('甲')],[ord('乙')],[ord('丙')],[100]])
        self.assertTrue(s.session_ended)
    def test_multibyte_tokens_preserved(self):
        s=self.make('segment')
        s.tokenize_offsets=lambda text: ([7,8,9],[(0,1),(0,1),(1,2)]) if text=='苹果' else ([9],[(0,1)])
        s.feed('苹果');s.end()
        self.assertEqual([s.next_embedding() for _ in range(4)],[[7],[8],[9],[100]])
    def test_cancel_during_underflow(self):
        s=self.make('segment');s.cancel()
        with self.assertRaises(Cancelled):s.next_embedding()
    def test_diagnostic_pad_is_not_end(self):
        s=self.make('pad')
        self.assertEqual(s.next_embedding(),[101]);self.assertFalse(s.ended)
        s.feed('甲');self.assertEqual(s.next_embedding(),[ord('甲')])

if __name__=='__main__':unittest.main()
