import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synology'))
from radio import LibraryRadio, VISUALIZER_BANKS


class FixtureLibrary:
    def __init__(self):
        self.tracks = {
            ident: {'id': ident, 'title': f'Track {ident}', 'artist': 'Fixture',
                    'album': 'Preset tests', 'available': True, 'duration': 300}
            for ident in (1, 2, 3)
        }

    def station_catalog(self):
        return list(self.tracks.values())

    def station_track(self, ident):
        return self.tracks[ident]

    def connect(self):
        raise AssertionError('The fixture does not scan the database')

    def track(self, ident):
        raise AssertionError('The fixture does not read audio')


class VisualPresetSyncTests(unittest.TestCase):
    def test_vlm_bank_includes_echo_loom(self):
        self.assertIn('Echo Loom', VISUALIZER_BANKS['VLM'])

    def test_owner_can_select_echo_loom_for_current_song(self):
        radio = self.make_radio()
        radio.control('visualizer', {'bank': 'VLM', 'preset': 'Echo Loom'})
        current = radio.snapshot()
        self.assertEqual(current['visualizer'], {'bank': 'VLM', 'preset': 'Echo Loom'})
        next_state = radio.control('next', {})
        self.assertNotEqual(next_state['visualizer']['preset'], 'Echo Loom')

    def make_radio(self):
        radio = LibraryRadio(FixtureLibrary(), target_seconds=600, start_paused=True,
                             visualizer_bank='Default')
        radio.pool = [1, 2, 3]
        radio.ids = [1, 2, 3]
        radio.kinds = ['random'] * 3
        radio.index = 0
        radio.playing = True
        radio.version = 1
        return radio

    def test_preset_is_stable_during_pause_resume_and_refresh(self):
        radio = self.make_radio()
        first = radio.snapshot()
        same = radio.snapshot(since=first['version'])
        self.assertEqual(first['visualizer'], same['visualizer'])

        radio.control('toggle', {})
        paused = radio.snapshot()
        radio.control('toggle', {})
        resumed = radio.snapshot()
        refreshed = radio.snapshot(since=resumed['version'])
        self.assertEqual(first['visualizer'], paused['visualizer'])
        self.assertEqual(first['visualizer'], resumed['visualizer'])
        self.assertEqual(first['visualizer'], refreshed['visualizer'])

    def test_next_assigns_one_different_preset(self):
        radio = self.make_radio()
        first = radio.snapshot()
        changes = []
        before = first['visualizer']
        result = radio.control('next', {})
        if result['visualizer'] != before:
            changes.append(result['visualizer'])
        again = radio.snapshot(since=result['version'])
        if again['visualizer'] != result['visualizer']:
            changes.append(again['visualizer'])
        self.assertEqual(len(changes), 1)
        self.assertNotEqual(first['visualizer']['preset'], result['visualizer']['preset'])
        self.assertEqual(result['visualizer'], again['visualizer'])

    def test_natural_end_assigns_one_different_preset(self):
        radio = self.make_radio()
        first = radio.snapshot()
        radio.offset = 301
        radio.started = time.monotonic() - 1
        result = radio.snapshot()
        self.assertEqual(result['current']['id'], 2)
        self.assertNotEqual(first['visualizer']['preset'], result['visualizer']['preset'])
        self.assertEqual(result['visualizer'], radio.snapshot()['visualizer'])


if __name__ == '__main__':
    unittest.main()
