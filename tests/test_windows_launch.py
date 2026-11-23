"""Offline regression checks for the Windows Codex launcher."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_preflight

ROOT = Path(__file__).resolve().parents[1]


class WinPreflightTest(unittest.TestCase):
    def test_chatgpt_login(self):
        with patch('windows_preflight.shutil.which', return_value=r'C:\\npm\\codex.cmd'), \
             patch('windows_preflight.subprocess.run', return_value=SimpleNamespace(
                 returncode=0, stdout='Logged in using ChatGPT', stderr='')) as run:
            self.assertTrue(windows_preflight.check_chatgpt_login())
        self.assertEqual(run.call_args.args[0][1:], ['login', 'status'])

    def test_api_key_auth_denied(self):
        with patch('windows_preflight.shutil.which', return_value='codex.cmd'), \
             patch('windows_preflight.subprocess.run', return_value=SimpleNamespace(
                 returncode=0, stdout='Logged in using an API key', stderr='')):
            self.assertFalse(windows_preflight.check_chatgpt_login())

    def test_windows_starter_requires_live_model_before_switching(self):
        content = (ROOT / 'START_WINDOWS_CODEX.bat').read_text('utf-8')
        self.assertIn('smoke_test.py --backend codex', content)
        self.assertIn('switch_backend.py codex', content)
        self.assertIn('windows_preflight.py --codex-login', content)

    def test_bom_tolerant_config(self):
        with patch('dotenv.dotenv_values', return_value={'BACKEND': 'codex'}) as reader:
            self.assertTrue(windows_preflight.backend_is_codex())
        self.assertEqual(reader.call_args.kwargs['encoding'], 'utf-8-sig')


if __name__ == '__main__':
    unittest.main()
