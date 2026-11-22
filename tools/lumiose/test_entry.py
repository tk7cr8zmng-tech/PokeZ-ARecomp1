import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lumiose_entry', Path(__file__).with_name('entry.py'))
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class EntryTests(unittest.TestCase):
    def test_entry_version_matches_launcher(self):
        source = (Path(__file__).resolve().parents[2] / 'runtime/ui/launcher.mm').read_text(encoding='utf-8')
        version = re.search(r'^#define LARECOMP_VERSION "([^"]+)"', source, re.M)
        self.assertIsNotNone(version)
        self.assertEqual(entry.LAUNCHER_VERSION, version.group(1))

    def test_first_setup_prepares_mod_before_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'lumiose').mkdir()
            (root / 'extracted').mkdir()
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if len(calls) == 1:
                    self.assertEqual(kwargs['env']['LUMIOSE_FIRST_SETUP'], '1')
                    (root / 'extracted' / (entry.GAME_LIBRARY + '.id')).write_text('game-id')
                    Path(kwargs['env']['LUMIOSE_SETUP_DONE']).write_text('ready')
                else:
                    (root / 'lumiose/config.json').write_text(json.dumps({'server': '127.0.0.1:1'}))
                    (root / 'lumiose/update-state.json').write_text('{}')
                return type('Result', (), {'returncode': 0})()
            cwd = os.getcwd()
            try:
                with patch.object(entry, 'ROOT', root), patch.object(entry.subprocess, 'run', side_effect=run), \
                     patch.object(entry, 'desktop_notice'), patch.object(entry, 'launch') as launch:
                    entry.main()
                self.assertEqual(len(calls), 2)
                self.assertEqual(Path(calls[1][1]).name, 'setup.py')
                launch.assert_called_once()
            finally:
                os.chdir(cwd)

    def test_existing_install_rechecks_once_and_marks_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'lumiose').mkdir(); (root / 'extracted').mkdir()
            (root / 'lumiose/update-state.json').write_text('{}')
            (root / 'lumiose/config.json').write_text(json.dumps({'server': '127.0.0.1:1'}))
            (root / 'extracted' / (entry.GAME_LIBRARY + '.id')).write_text('new-game-id')
            def run(command, **kwargs):
                Path(kwargs['env']['LUMIOSE_SETUP_DONE']).write_text('ready')
                return type('Result', (), {'returncode': 0})()
            cwd = os.getcwd()
            try:
                with patch.object(entry, 'ROOT', root), patch.object(entry.subprocess, 'run', side_effect=run) as preflight, \
                     patch.object(entry, 'launch') as launch:
                    entry.main(); entry.main()
                    preflight.assert_called_once(); self.assertEqual(launch.call_count, 2)
                    self.assertEqual((root / 'lumiose/launcher-code-revision.txt').read_text().strip(), entry.GAME_CODE_REVISION)
            finally:
                os.chdir(cwd)

    def test_closed_setup_does_not_accept_an_old_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'lumiose').mkdir(); (root / 'extracted').mkdir()
            (root / 'lumiose/update-state.json').write_text('{}')
            (root / 'extracted' / (entry.GAME_LIBRARY + '.id')).write_text('old-id')
            cwd = os.getcwd()
            try:
                with patch.object(entry, 'ROOT', root), patch.object(entry.subprocess, 'run') as preflight, \
                     patch.object(entry, 'launch') as launch:
                    preflight.return_value.returncode = 0
                    with self.assertRaisesRegex(RuntimeError, 'not completed'): entry.main()
                    launch.assert_not_called()
                    self.assertFalse((root / 'lumiose/launcher-code-revision.txt').exists())
            finally:
                os.chdir(cwd)

    def test_normalize_server(self):
        self.assertEqual(entry.normalize_server(' 10.0.0.5:27777 '), '10.0.0.5:27777')
        self.assertEqual(entry.normalize_server('10.0.0.5:080'), '10.0.0.5:80')
        for bad in ('10.0.0.5', 'example.com:27777', '10.0.0.256:1', '10.0.0.5:0', '10.0.0.5:65536', ':27777', '010.0.0.5:1'):
            with self.assertRaises(ValueError, msg=bad): entry.normalize_server(bad)

    def test_server_override_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(entry, 'ROOT', root), patch.dict(os.environ, {}, clear=False):
                os.environ.pop('LUMIOSE_SERVER', None)
                self.assertIsNone(entry.server_override())
                (root / entry.SERVER_FILE).write_text('# my server\n\n 192.168.1.20:27777\n', encoding='utf-8')
                self.assertEqual(entry.server_override(), '192.168.1.20:27777')
                os.environ['LUMIOSE_SERVER'] = '10.1.2.3:4000'  # (the environment wins over the file)
                self.assertEqual(entry.server_override(), '10.1.2.3:4000')
                os.environ['LUMIOSE_SERVER'] = 'not-an-address'
                with self.assertRaisesRegex(RuntimeError, 'LUMIOSE_SERVER is invalid'): entry.server_override()

    def test_server_file_updates_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'lumiose').mkdir(); (root / 'extracted').mkdir()
            (root / 'lumiose/update-state.json').write_text('{}')
            (root / 'lumiose/config.json').write_text(json.dumps({'server': '127.0.0.1:1'}))
            (root / 'lumiose/launcher-code-revision.txt').write_text(entry.GAME_CODE_REVISION)
            (root / entry.SERVER_FILE).write_text('192.168.1.20:27777\n')
            cwd = os.getcwd()
            try:
                with patch.object(entry, 'ROOT', root), patch.dict(os.environ, {}, clear=False), \
                     patch.object(entry, 'launch'):
                    os.environ.pop('LUMIOSE_SERVER', None)
                    entry.main()
                self.assertEqual(json.loads((root / 'lumiose/config.json').read_text())['server'], '192.168.1.20:27777')
            finally:
                os.chdir(cwd)

    def test_no_override_keeps_configured_server(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'lumiose').mkdir(); (root / 'extracted').mkdir()
            (root / 'lumiose/update-state.json').write_text('{}')
            (root / 'lumiose/config.json').write_text(json.dumps({'server': '127.0.0.1:1'}))
            (root / 'lumiose/launcher-code-revision.txt').write_text(entry.GAME_CODE_REVISION)
            cwd = os.getcwd()
            try:
                with patch.object(entry, 'ROOT', root), patch.dict(os.environ, {}, clear=False), \
                     patch.object(entry, 'launch'):
                    os.environ.pop('LUMIOSE_SERVER', None)
                    entry.main()
                self.assertEqual(json.loads((root / 'lumiose/config.json').read_text())['server'], '127.0.0.1:1')
            finally:
                os.chdir(cwd)

if __name__ == '__main__':
    unittest.main()
