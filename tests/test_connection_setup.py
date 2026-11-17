import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('connection_settings', Path(__file__).resolve().parents[1] / 'synology/sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SetupTests(unittest.TestCase):
    def test_public_links_and_confirmation_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = module.ConnectionSettings(directory)
            with self.assertRaisesRegex(ValueError, 'Save your public address first'):
                settings.save({'public_base':'https://music.example', 'confirm_internet':True})
            initial = settings.save({'public_base':'https://music.example/player/'})
            self.assertEqual(initial['stream_url'], 'https://music.example/player/stream.mp3')
            self.assertEqual(initial['screen_url'], 'https://music.example/player/dr-screen')
            self.assertEqual(initial['internet_confirmed_at'], 0)
            confirmed = settings.save({'public_base':initial['public_base'], 'confirm_internet':True})
            self.assertGreater(confirmed['internet_confirmed_at'], 0)
            restored = module.ConnectionSettings(directory)
            self.assertEqual(restored.snapshot(), confirmed)
            self.assertEqual(restored.save({'public_base':initial['public_base']})['internet_confirmed_at'], confirmed['internet_confirmed_at'])
            changed = restored.save({'public_base':'https://other.example'})
            self.assertEqual(changed['internet_confirmed_at'], 0)
            local = restored.save({'public_base':'', 'stream_url':'http://192.168.1.4:8001/stream.mp3', 'screen_url':'http://192.168.1.4:8001/dr-screen'})
            self.assertEqual(local['internet_confirmed_at'], 0)
            self.assertEqual(local['public_base'], '')

    def test_private_and_invalid_addresses_never_become_public_links(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = module.ConnectionSettings(directory)
            good = settings.save({'public_base':'http://music.example:8001'})
            for address in ('http://192.168.1.5:8001', 'http://10.0.0.1', 'http://172.16.1.1',
                            'http://127.0.0.1', 'http://localhost', 'http://player.local',
                            'http://100.64.0.1', 'http://[::1]', 'http://player',
                            'ftp://music.example', 'https://user:password@music.example',
                            'https://music.example:0', 'https://music.example:bad',
                            'https://music.example/dr-screen', 'https://music.example?token=test'):
                with self.subTest(address=address):
                    with self.assertRaises(ValueError): settings.save({'public_base':address})
                    self.assertEqual(settings.snapshot(), good)


if __name__ == '__main__':
    unittest.main()
