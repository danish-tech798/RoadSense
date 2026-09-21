import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from sign_catalog import sign_info
from training.audit_dataset import audit


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data.yaml").write_text("names: [STOP]\nnc: 1\n")
        for split, color in [("train", "red"), ("valid", "green"), ("test", "blue")]:
            (self.root / split / "images").mkdir(parents=True)
            (self.root / split / "labels").mkdir()
            Image.new("RGB", (40, 40), color).save(self.root / split / "images/a.png")
            (self.root / split / "labels/a.txt").write_text("0 0.5 0.5 0.5 0.5\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_dataset_has_absolute_yaml(self):
        report = audit(self.root)
        self.assertFalse(report["errors"])
        self.assertEqual(report["splits"]["train"]["instances_per_class"]["STOP"], 1)
        self.assertIn(str(self.root), (self.root / "audited_data.yaml").read_text())

    def test_cross_split_duplicate_blocks_training(self):
        Image.new("RGB", (40, 40), "red").save(self.root / "valid/images/a.png")
        self.assertTrue(audit(self.root)["cross_split_duplicate_groups"])
        self.assertFalse((self.root / "audited_data.yaml").exists())

    def test_bad_box_or_class_blocks_training(self):
        (self.root / "train/labels/a.txt").write_text("4 0.5 0.5 0.5 0.5\n0 nan 0.5 0.5 0.5\n")
        self.assertEqual(len(audit(self.root)["errors"]), 3)  # two rows + absent train class

    def test_missing_label_is_not_silently_background(self):
        (self.root / "valid/labels/a.txt").unlink()
        self.assertTrue(any("Missing label" in e for e in audit(self.root)["errors"]))

    def test_valid_empty_label_is_negative(self):
        (self.root / "valid/labels/a.txt").write_text("")
        result = audit(self.root)
        self.assertFalse(result["errors"])
        self.assertEqual(result["splits"]["val"]["empty_labels"], 1)


class CatalogTests(unittest.TestCase):
    def test_speed_number_is_retained(self):
        self.assertEqual(sign_info("SPEED_LIMIT_40")["label"], "Speed limit 40 km/h")

    def test_signal_warning_is_distinct_from_light(self):
        self.assertIn("warning sign", sign_info("TRAFFIC_SIGNAL")["meaning"])
        self.assertIn("physical traffic light", sign_info("trafficlight")["meaning"])

    def test_unknown_class_has_complete_fallback(self):
        self.assertEqual(set(sign_info("NEW_CLASS")), {"label", "icon", "chip", "chip_class", "meaning", "rule"})


@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask not installed")
class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate this test from real account databases and weights.
        fake_db = types.ModuleType("db")
        fake_db.init_db = lambda: None
        spec = importlib.util.spec_from_file_location("roadsense_test_app", ROOT / "app.py")
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"db": fake_db}):
            spec.loader.exec_module(cls.module)
        cls.module.app.config.update(TESTING=True, SECRET_KEY="test-only-key")

    def setUp(self):
        import numpy as np
        self.tmp = tempfile.TemporaryDirectory()
        self.module.LOG_PATH = str(Path(self.tmp.name) / "detections.json")
        box = types.SimpleNamespace(cls=[0], conf=[0.9], xyxy=[[2, 2, 10, 10]])
        result = types.SimpleNamespace(names={0: "SPEED_LIMIT_40"}, boxes=[box],
                                       plot=lambda: np.zeros((20, 20, 3), dtype=np.uint8))
        self.module._model = types.SimpleNamespace(names=result.names, predict=lambda **kw: [result])
        self.client = self.module.app.test_client()
        with self.client.session_transaction() as session:
            session["username"] = "fixture-user"

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, **fields):
        image = io.BytesIO()
        Image.new("RGB", (20, 20)).save(image, format="PNG")
        image.seek(0)
        return self.client.post("/api/detect", data={"image": (image, "test.png"), **fields})

    def test_detection_preserves_api_and_new_class(self):
        response = self.post(imgsz="960")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["detections"][0]["class"], "SPEED_LIMIT_40")
        self.assertEqual(data["detections"][0]["box_pct"]["width"], 40)
        self.assertEqual(data["imgsz"], 960)
        self.assertTrue(data["annotated_image"].startswith("data:image/png;base64,"))
        self.assertEqual(len(self.client.get("/api/history").get_json()), 1)

    def test_invalid_confidence_and_size(self):
        self.assertEqual(self.post(conf="nan").status_code, 400)
        self.assertEqual(self.post(imgsz="17").status_code, 400)

    def test_invalid_image(self):
        response = self.client.post("/api/detect", data={"image": (io.BytesIO(b"not an image"), "x.png")})
        self.assertEqual(response.status_code, 400)

    def test_empty_detections_are_valid(self):
        import numpy as np
        result = types.SimpleNamespace(names={0: "STOP"}, boxes=[], plot=lambda: np.zeros((20,20,3), dtype=np.uint8))
        self.module._model.predict = lambda **kw: [result]
        self.assertEqual(self.post().get_json()["detections"], [])

    def test_other_users_do_not_see_history(self):
        self.post()
        with self.client.session_transaction() as session:
            session["username"] = "another-user"
        self.assertEqual(self.client.get("/api/history").get_json(), [])


if __name__ == "__main__":
    unittest.main()
