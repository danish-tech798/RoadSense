"""Audit a standard Roboflow YOLO detection export without altering its splits.

Usage: python audit_dataset.py /path/to/export
Writes audited_data.yaml and audit_report.json beside the source data.yaml.
Strict about missing labels: verified negatives must have empty .txt files.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import yaml
from PIL import Image

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def audit(root):
    root = Path(root).resolve()
    config = yaml.safe_load((root / "data.yaml").read_text())
    names = config["names"]
    if isinstance(names, dict):
        names = {int(k): str(v) for k, v in names.items()}
        if sorted(names) != list(range(len(names))):
            raise ValueError("Class IDs must be contiguous from zero")
        names = [names[i] for i in range(len(names))]
    if not isinstance(names, list) or not names or len(set(names)) != len(names):
        raise ValueError("Expected nonempty unique class names")
    if "nc" in config and int(config["nc"]) != len(names):
        raise ValueError("nc does not match names")
    report = {"names": names, "splits": {}, "errors": [], "warnings": []}
    hashes = defaultdict(list)
    data = {"path": str(root), "names": names, "nc": len(names)}
    for split, folders in (("train", ["train"]), ("val", ["valid", "val"]), ("test", ["test"])):
        options = [root / f / "images" for f in folders if (root / f / "images").is_dir()]
        if len(options) != 1:
            if split != "test":
                report["errors"].append(f"Expected exactly one {split} images directory")
            else:
                report["warnings"].append("No test split: create an independent labeled road-scene test set")
            continue
        image_dir = options[0]
        data[split] = str(image_dir)
        paths = sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in EXTENSIONS)
        counts, image_counts = Counter(), Counter()
        empty, small, boxes = 0, 0, 0
        if not paths:
            report["errors"].append(f"Empty {split} image directory")
        for path in paths:
            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    digest = hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()
                    hashes[digest].append((split, str(path.relative_to(root))))
            except Exception as exc:
                report["errors"].append(f"Unreadable image {path.name}: {exc}")
                continue
            label = image_dir.parent / "labels" / path.relative_to(image_dir).with_suffix(".txt")
            if not label.exists():
                report["errors"].append(f"Missing label: {label.relative_to(root)}")
                continue
            lines = [s for s in label.read_text().splitlines() if s.strip()]
            empty += not lines
            seen = set()
            for line_no, line in enumerate(lines, 1):
                try:
                    values = list(map(float, line.split()))
                    if len(values) != 5 or not all(map(math.isfinite, values)):
                        raise ValueError("expected five finite numbers")
                    cls, x, y, bw, bh = values
                    if not cls.is_integer() or not 0 <= cls < len(names):
                        raise ValueError("invalid class ID")
                    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < bw <= 1 and 0 < bh <= 1):
                        raise ValueError("invalid normalized box")
                    if min(x-bw/2, y-bh/2) < -0.001 or max(x+bw/2, y+bh/2) > 1.001:
                        raise ValueError("box extends outside image")
                    counts[int(cls)] += 1
                    seen.add(int(cls))
                    boxes += 1
                    small += min(bw*w, bh*h) * 640/max(w, h) < 16
                except ValueError as exc:
                    report["errors"].append(f"{label.relative_to(root)}:{line_no}: {exc}")
            image_counts.update(seen)
        report["splits"][split] = {
            "images": len(paths), "empty_labels": empty, "boxes": boxes,
            "boxes_with_short_side_under_16px_at_640": small,
            "instances_per_class": {name: counts[i] for i, name in enumerate(names)},
            "images_per_class": {name: image_counts[i] for i, name in enumerate(names)},
        }
        absent = [n for i, n in enumerate(names) if not counts[i]]
        if absent:
            report["errors" if split == "train" else "warnings"].append(f"{split} classes without instances: {absent}")
    cross = [v for v in hashes.values() if len({s for s, _ in v}) > 1]
    report["cross_split_duplicate_groups"] = cross
    report["within_split_duplicate_groups"] = [v for v in hashes.values() if len(v)>1 and len({s for s, _ in v})==1]
    if cross:
        report["errors"].append(f"{len(cross)} exact decoded-image duplicate groups cross splits; repair splits before training")
    report["warnings"].append("Exact hashes do not detect all resized, augmented, near-duplicate images or adjacent video frames. Review source groups manually.")
    (root / "audit_report.json").write_text(json.dumps(report, indent=2))
    if report["errors"]:
        (root / "audited_data.yaml").unlink(missing_ok=True)
    else:
        (root / "audited_data.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    result = audit(parser.parse_args().root)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["errors"]))
