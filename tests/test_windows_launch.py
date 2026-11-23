"""Offline checks for the Windows Codex one-click launcher and preflight."""
import sys
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_preflight

ROOT = Path(__file__).resolve().parents[1]


class WinPreflightTest(unittest.TestCase):
    def test_subscription_login_success(self):
        with patch('windows_preflight.shutil.which', return_value=r'C:\\npm\\codex.cmd'), \
             patch('windows_preflight.subprocess.run', return_value=SimpleNamespace(
                 returncode=0, stdout='Logged in using ChatGPT', stderr='')) as run:
            self.assertTrue(windows_preflight.check_chatgpt_login())
        self.assertEqual(run.call_args.args[0][1:], ['login','status'])
        if 'USERPROFILE' in os.environ:
            self.assertIn('USERPROFILE', run.call_args.kwargs['env'])

    def test_api_key_login_is_rejected(self):
        with patch('windows_preflight.shutil.which', return_value='codex.cmd'), \
             patch('windows_preflight.subprocess.run', return_value=SimpleNamespace(
                 returncode=0, stdout='Logged in using an API key', stderr='')):
            self.assertFalse(windows_preflight.check_chatgpt_login())

    def test_windows_launcher_never_autofills_secret(self):
        launcher = (ROOT/'START_WINDOWS_CODEX.bat').read_text('utf-8')
        runner = (ROOT/'windows_launcher.py').read_text('utf-8')
        self.assertIn('windows_launcher.py', launcher)
        self.assertIn('/K', launcher)
        self.assertIn("call_python('smoke_test.py', '--backend', 'codex')", runner)
        self.assertIn("call_python('switch_backend.py', 'codex')", runner)
        self.assertIn('check_chatgpt_login', runner)
        self.assertNotIn('OPENAI_API_KEY=', launcher + runner)
        self.assertNotIn('BACKEND=mock', launcher + runner)

    def test_backend_detection_uses_utf8_bom_tolerant_reader(self):
        with patch('dotenv.dotenv_values', return_value={'BACKEND': 'codex'}) as reader:
            self.assertTrue(windows_preflight.backend_is_codex())
        self.assertEqual(reader.call_args.kwargs['encoding'], 'utf-8-sig')

    def test_live_smoke_fails_closed_on_contextual_fallback(self):
        import smoke_test
        with patch.object(sys, 'argv', ['smoke_test.py', '--backend', 'codex']), \
             patch('smoke_test.CodexBackend'), \
             patch('smoke_test.Tutor') as tutor:
            tutor.return_value.respond.return_value = SimpleNamespace(
                reply='Фраза-заглушка', flag='none', mastery='working',
                parent_note='Fallback', model_used=False)
            with self.assertRaises(SystemExit) as ctx:
                smoke_test.main()
            self.assertEqual(ctx.exception.code, 3)


if __name__ == '__main__':
    unittest.main()
