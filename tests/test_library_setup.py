import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("library_setup", Path(__file__).resolve().parents[1] / "preview/library_setup.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.demo = module.SetupDemo()
        self.addCleanup(self.demo.close)
        self.before = self.snapshot()

    def snapshot(self):
        return {str(p.relative_to(self.demo.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.demo.root.rglob("*") if p.is_file()}

    def tearDown(self):
        self.assertEqual(self.before, self.snapshot(), "Validation/confirmation wrote fixture data")

    def validate(self, **kwargs):
        return self.demo.validate(dict(mode="existing", fixture="existing", music_path="/music", **kwargs))

    def test_compatible_and_explicit_confirmation(self):
        result = self.validate()
        self.assertTrue(result["ok"])
        self.assertEqual(result["plan"], dict(unchanged=1, changed=1, new=1, missing_retained=1))
        token = result["confirmation_token"]
        self.assertFalse(self.demo.confirm({"token": token})["ok"])
        confirmed = self.demo.confirm({"token": token, "confirmed": True})
        self.assertTrue(confirmed["simulated"])
        self.assertFalse(confirmed["scan_started"])
        self.assertFalse(self.demo.confirm({"token": token, "confirmed": True})["ok"])

    def test_paths_require_matching_container_mount(self):
        choice = dict(mode="existing", fixture="different-path", music_path="/music")
        self.assertFalse(self.demo.validate(choice)["ok"])
        choice["music_path"] = "/mnt/lossless"
        self.assertTrue(self.demo.validate(choice)["ok"])
        choice["music_path"] = "/mnt/loss"
        self.assertFalse(self.demo.validate(choice)["ok"])

    def test_incompatible_and_unavailable_block(self):
        result = self.demo.validate(dict(mode="existing", fixture="incompatible"))
        self.assertFalse(result["ok"])
        self.assertIn("missing_columns", result)
        self.assertFalse(self.validate(unavailable=True)["ok"])

    def test_revalidate_source_after_confirmation(self):
        result = self.validate()
        marker = self.demo.music / ".preview-library-id"
        original = marker.read_bytes()
        marker.unlink()  # Only our generated temporary fixture.
        try:
            self.assertFalse(self.demo.confirm(dict(token=result["confirmation_token"], confirmed=True))["ok"])
        finally:
            marker.write_bytes(original)

    def test_new_library_does_not_create_index(self):
        result = self.demo.validate(dict(mode="new"))
        self.assertTrue(result["ok"])
        self.assertTrue(self.demo.confirm(dict(token=result["confirmation_token"], confirmed=True))["simulated"])

    def test_changed_index_requires_validation_again(self):
        result = self.validate()
        db = self.demo.root / "existing.db"
        original = db.read_bytes()
        try:
            with module.CONNECT(db) as con:
                con.execute("UPDATE tracks SET title='temporary fixture change'")
            self.assertFalse(self.demo.confirm(dict(token=result["confirmation_token"], confirmed=True))["ok"])
        finally:
            db.write_bytes(original)

    def test_unoffered_files_and_traversal_blocked(self):
        self.assertFalse(self.demo.validate(dict(mode="existing", fixture="../../production"))["ok"])
        self.assertFalse(self.demo.validate(dict(mode="existing", music_path="/music/../other"))["ok"])

    def test_active_wal_rejected_without_reading_it(self):
        wal = self.demo.root / "existing.db-wal"
        wal.write_bytes(b"synthetic journal")
        try:
            self.assertFalse(self.validate()["ok"])
        finally:
            wal.unlink()


if __name__ == "__main__":
    unittest.main()
