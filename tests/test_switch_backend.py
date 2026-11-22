import unittest
from switch_backend import switch_backend


class SwitchBackendTest(unittest.TestCase):
    def test_changes_only_backend(self):
        src = 'TELEGRAM_BOT_TOKEN=123:secret\nBACKEND=mock\nTESTER_PAIR_CODE=abcdef\n'
        result = switch_backend(src, 'codex')
        self.assertEqual(result, src.replace('BACKEND=mock', 'BACKEND=codex'))

    def test_adds_if_missing(self):
        self.assertEqual(switch_backend('A=B\r\n', 'ollama'), 'A=B\r\nBACKEND=ollama\r\n')

    def test_duplicate_entries_fail_closed(self):
        with self.assertRaises(ValueError):
            switch_backend('BACKEND=mock\nBACKEND=ollama\n', 'codex')


if __name__ == '__main__':
    unittest.main()
