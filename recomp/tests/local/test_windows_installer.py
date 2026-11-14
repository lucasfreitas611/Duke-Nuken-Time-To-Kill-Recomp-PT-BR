"""Installer guard regressions. No disc, compiler or user profile is modified."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch


def module(name):
    path = Path(__file__).resolve().parents[2] / 'tools/installer' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


setup = module('player_setup')
package = module('package_windows')


class InstallerGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'app'
        (self.app / 'sdk').mkdir(parents=True)
        self.project = self.root / 'project'
        self.project.mkdir()

    def manifest(self, entries):
        (self.app / 'sdk/sdk-manifest.json').write_text(json.dumps(dict(schema=1, files=entries)))

    def entry(self, path, content=b'authored source'):
        target = self.app / 'sdk' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return dict(path=path, sha256=hashlib.sha256(content).hexdigest())

    def test_all_payload_verified_before_existing_project_is_changed(self):
        first = self.entry('first.txt')
        second = self.entry('second.txt')
        (self.project / 'first.txt').write_bytes(b'existing version')
        (self.app / 'sdk/second.txt').write_bytes(b'corrupted payload')
        self.manifest([first, second])
        with self.assertRaises(ValueError):
            setup.copy_sdk(self.app, self.project)
        self.assertEqual((self.project / 'first.txt').read_bytes(), b'existing version')
        self.assertFalse((self.project / 'second.txt').exists())

    def test_parent_absolute_drive_and_backslash_paths_rejected(self):
        for name in ('../outside', '/absolute', 'C:/outside', 'folder\\outside', ''):
            with self.subTest(path=name), self.assertRaises((ValueError, IsADirectoryError)):
                self.reject(name)

    def reject(self, name):
        self.manifest([dict(path=name, sha256='0' * 64)])
        setup.copy_sdk(self.app, self.project)

    def test_case_insensitive_duplicate_paths_rejected(self):
        entry = self.entry('source.c')
        self.manifest([entry, dict(entry, path='SOURCE.C')])
        with self.assertRaises(ValueError):
            setup.copy_sdk(self.app, self.project)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_valid_source_copied_without_touching_saves(self):
        (self.project / 'saves').mkdir()
        (self.project / 'saves/card1.mcd').write_bytes(b'private test sentinel')
        self.manifest([self.entry('src/test.c')])
        fingerprint = setup.copy_sdk(self.app, self.project)
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual((self.project / 'src/test.c').read_bytes(), b'authored source')
        self.assertEqual((self.project / 'saves/card1.mcd').read_bytes(), b'private test sentinel')

    def test_retry_preserves_unchanged_source_timestamps_for_build_resume(self):
        self.manifest([self.entry('src/test.c')])
        setup.copy_sdk(self.app, self.project)
        target = self.project / 'src/test.c'
        os.utime(target, (1000000000, 1000000000))
        before = target.stat().st_mtime_ns
        setup.copy_sdk(self.app, self.project)
        self.assertEqual(target.stat().st_mtime_ns, before)

    def test_packaging_rejects_cards_including_backups_and_generated_data(self):
        for name in ('psxrecomp/card2.mcd.bak.before_copy', 'psxrecomp/dummy.0.mcr',
                     'saves/card1.mcd', 'disc/game.bin', 'generated/game.c',
                     'build-local/game.exe', 'src/game.pack', 'src/debug.log'):
            with self.subTest(path=name), self.assertRaises(ValueError):
                package.audit_sdk_path(Path(name))
        package.audit_sdk_path(Path('psxrecomp/bios/openbios.bin'))
        package.audit_sdk_path(Path('psxrecomp/recompiler/lib/rabbitizer/include/analysis/test.hpp'))

    def test_checker_reports_import_failures_and_old_tool_versions(self):
        with patch.object(setup.importlib, 'import_module', side_effect=OSError('broken DLL')), \
             patch.object(setup, 'command_version', return_value=(True, 'version 1.0.0')):
            checks = setup.requirements(self.app, self.root / 'missing-kit', self.root / 'data')
        results = {c['name']: c['ok'] for c in checks}
        self.assertFalse(results['Biblioteca numpy'])
        self.assertFalse(results['Biblioteca Pillow'])
        self.assertFalse(results['Biblioteca capstone'])
        self.assertFalse(results['cmake'])
        self.assertFalse(results['ninja'])
        self.assertFalse(results['clang++'])
        self.assertFalse(setup.save_report(checks, self.root / 'data'))
        self.assertFalse(json.loads((self.root / 'data/requirements.json').read_text())['ready'])

    def test_automatic_library_install_only_when_other_requirements_pass(self):
        data = self.root / 'data'
        checks = [
            dict(name='Biblioteca numpy', ok=False, detail=''),
            dict(name='cmake', ok=True, detail=''),
        ]
        with patch.object(setup, 'requirements', return_value=checks):
            self.assertEqual(setup.check_status(self.app, self.root, data), 2)
            wheels = self.app / 'wheels'
            wheels.mkdir()
            (wheels / 'numpy.whl').touch()
            self.assertEqual(setup.check_status(self.app, self.root, data), 3)
            checks[1]['ok'] = False
            self.assertEqual(setup.check_status(self.app, self.root, data), 2)

    def test_invalid_replacement_disc_leaves_current_install_ready(self):
        ready = self.root / 'ready.json'
        ready.write_text('existing preparation')
        with patch.dict(sys.modules, {'disc_lab': unittest.mock.Mock()}):
            disc_lab = sys.modules['disc_lab']
            disc_lab.import_disc.side_effect = ValueError('disco incompatível')
            with self.assertRaisesRegex(ValueError, 'disco incompatível'):
                setup.prepare(self.app, self.root / 'kit', self.root, self.root / 'invalid.bin', 2)
        self.assertEqual(ready.read_text(), 'existing preparation')

    def launch(self, changed_sdk=False):
        self.manifest([self.entry('src/test.c')])
        digest = hashlib.sha256((self.app / 'sdk/sdk-manifest.json').read_bytes()).hexdigest()
        (self.root / 'ready.json').write_text(json.dumps(dict(schema=1, sdk='outdated' if changed_sdk else digest)))
        arguments = ['player_setup.py', 'play', '--app-root', str(self.app),
                     '--toolchain', str(self.root / 'kit'), '--data-dir', str(self.root)]
        with patch.object(sys, 'argv', arguments), patch.object(setup, 'run') as run:
            result = setup.main()
        return result, run

    def test_first_launch_defaults_and_user_preferences_on_later_launch(self):
        result, run = self.launch()
        self.assertEqual(result, 0)
        command = list(map(str, run.call_args.args[0]))
        self.assertEqual(command[command.index('--internal-scale') + 1], '2')
        self.assertEqual(command[command.index('--frame-rate') + 1], 'auto')
        self.assertEqual(command[command.index('--memcard-dir') + 1], str(self.root / 'saves'))
        config = self.root / 'config/player-profiles.json'
        config.parent.mkdir()
        config.write_text('user preference sentinel')
        result, run = self.launch()
        self.assertEqual(result, 0)
        self.assertNotIn('--internal-scale', run.call_args.args[0])
        self.assertNotIn('--frame-rate', run.call_args.args[0])
        self.assertEqual(config.read_text(), 'user preference sentinel')

    def test_updated_sdk_refuses_to_launch_old_preparation(self):
        result, run = self.launch(changed_sdk=True)
        self.assertEqual(result, 1)
        run.assert_not_called()
        self.assertIn('atualizado', (self.root / 'last-error.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
