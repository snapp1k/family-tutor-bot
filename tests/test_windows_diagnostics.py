"""Offline tests for the persistent Windows launcher and privacy-safe diagnostics."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import windows_launcher as wl


class WindowsDiagnosticTests(unittest.TestCase):
    def test_persistent_cmd_even_after_zero_exit(self):
        text = (Path(__file__).resolve().parents[1] / 'START_WINDOWS_CODEX.bat').read_text('utf-8')
        self.assertIn('"%ComSpec%" /D /K', text)
        self.assertIn('if not exist "bot.py" goto :not_extracted', text)
        self.assertIn('".venv\\Scripts\\python.exe" windows_launcher.py', text)
        self.assertIn('exit /b %RESULT%', text)

    def test_status_log_contains_only_allowlisted_labels(self):
        with tempfile.TemporaryDirectory() as d:
            logfile = Path(d) / 'windows_startup.log'
            with patch.object(wl, 'LOGFILE', logfile):
                wl.record('codex_found', 'ok')
                with self.assertRaises(ValueError):
                    wl.record('TELEGRAM_BOT_TOKEN=not-a-token', 'ok')
                with self.assertRaises(ValueError):
                    wl.record('codex_found', 'secret')
            self.assertTrue(logfile.exists())
            self.assertIn('codex_found: ok', logfile.read_text('utf-8'))
            self.assertNotIn('not-a-token', logfile.read_text('utf-8'))

    def test_existing_config_not_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.env').write_text('EXISTING_SECRET=keep', encoding='utf-8')
            with patch.object(wl, 'ROOT', root), patch.object(wl, 'call_python', return_value=0) as run, \
                 patch.object(wl, 'record'):
                self.assertTrue(wl.configure())
            self.assertEqual((root / '.env').read_text('utf-8'), 'EXISTING_SECRET=keep')
            self.assertEqual(run.call_args_list, [call('windows_preflight.py', '--config')])

    def test_new_config_is_validated_in_separate_python_process(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            calls = []
            def fake_runner(*args):
                calls.append(args)
                if args == ('setup.py',):
                    (root / '.env').write_text('TOKEN=placeholder', encoding='utf-8')
                return 0
            with patch.object(wl, 'ROOT', root), patch.object(wl, 'call_python', side_effect=fake_runner), \
                 patch.object(wl, 'record'), patch('windows_launcher.subprocess.run', return_value=SimpleNamespace(returncode=0)):
                self.assertTrue(wl.configure())
            self.assertEqual(calls, [('setup.py',), ('windows_preflight.py', '--config')])

    def test_model_check_skipped_if_codex_enabled(self):
        with patch('windows_preflight.backend_is_codex', return_value=True), \
             patch.object(wl, 'call_python') as process, patch.object(wl, 'record'):
            self.assertTrue(wl.configure_codex_backend())
            process.assert_not_called()

    def test_failed_model_check_does_not_switch_backend(self):
        with patch('windows_preflight.backend_is_codex', return_value=False), \
             patch.object(wl, 'call_python', return_value=2) as process, patch.object(wl, 'record'):
            self.assertFalse(wl.configure_codex_backend())
            process.assert_called_once_with('smoke_test.py', '--backend', 'codex')

    def test_failed_bot_exits_with_status_and_log(self):
        with patch.object(wl, 'configure', return_value=True), \
             patch.object(wl, 'check_codex', return_value=True), \
             patch.object(wl, 'configure_codex_backend', return_value=True), \
             patch.object(wl, 'call_python', return_value=17), \
             patch.object(wl, 'record') as log:
            self.assertEqual(wl.main(), 17)
            log.assert_any_call('bot_run', 'stopped_unexpectedly')

if __name__ == '__main__':
    unittest.main()
