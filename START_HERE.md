# RoadSense upgrade: step-by-step

This package includes the Flask backend, your integrated templates/static files, your original four-class model, VS Code configuration, and the Colab training notebook. It does not contain newly trained Indian weights. Start with README_VSCODE.md for local setup. Preserve your existing account database and history when migrating.

## 1. What the uploaded project shows

- `app.py` uses Flask, not Streamlit. `/api/detect` accepts an image and confidence, runs YOLO, returns boxes, a PNG, and metadata, then stores per-user detection history in JSON.
- `db.py` and `roadsense.db` manage user accounts. The database schema was inspected without reading account rows. No account database is distributed in this overlay.
- The model is YOLOv8s with four classes. Its stored validation mAP50 is 0.95928 and mAP50–95 is 0.79224. Best recorded epoch: 39; history: 54 epochs. These are original-validation results, not Indian-road accuracy.
- The original README describes 877 images, but that count was not independently verified from image files. Its written metrics differ from the uploaded checkpoint, so use the checkpoint metrics when documenting this exact model.
- The uploaded backend has metadata for only four classes. The new backend builds the active label list from model names and supplies fallback metadata for every class.
- The templates and static files supplied in your follow-up are now integrated. Duplicate box overlays were removed; model metadata, searchable classes, history filters, resolution settings, and scalable category charts were added. Browser rendering has not been verified in this environment.

## 2. Back up your existing project

Close the Flask server. In File Explorer, copy the entire project folder to a separate folder such as `RoadSense_before_indian_upgrade`. Keep the original model and database.

Open the extracted `RoadSense_VSCode` folder as a separate project in VS Code. It contains the original `models/best.pt` and all source files. A new local account database is created on first launch. To preserve accounts, close both apps and copy your existing `roadsense.db` and `logs/` folder into this new project. Keep the backup until you finish checking the upgrade.

## 3. Dataset selected for the first experiment

Use [SDI Indian Traffic Sign](https://universe.roboflow.com/sdi/indian-traffic-sign). Its public page, checked 17 September 2026, lists 6,750 images, 85 classes, one version, object detection, and CC BY 4.0. Include attribution in your report. The exact downloaded export may differ; the notebook prints its actual class list and counts.

Open the dataset page, open its dataset/version area, and use the available download/export action. Select **YOLOv8** and download the ZIP. Roboflow may require sign-in; interface labels or export access may change. Do not use the page's hosted inference API snippet: we need annotated images for training. If no export is available, send the page/error shown rather than downloading an unrelated dataset.

Why this choice: it supplies Indian sign categories and detection annotations, including individual speed limits. It is an initial dataset, not verified evidence of real-road generalization. I could inspect the public metadata but could not audit the export's actual images in this session.

The first run keeps every exported category. This avoids quietly deleting labels and teaching YOLO to treat visible omitted signs as background. If some classes lack useful data, review their examples and deliberately redesign the label set before a later run. Do not rename or reorder YAML names independently of label IDs.

`TRAFFIC_SIGNAL` means a signal-warning sign. It is not the old `trafficlight` object class and does not classify red/amber/green. Training only on SDI does not preserve physical traffic-light detection automatically. Add a separately annotated physical-light dataset with a consistent merged label map if that feature is required. Similarly, signs for crossings and painted road crossings are different objects.

## 4. Open the Colab notebook

1. Open Google Colab and choose **File → Upload notebook**.
2. Upload `training/RoadSense_Indian_Training.ipynb` from the overlay.
3. Select a GPU under **Runtime → Change runtime type**.
4. Run the installation cell; it checks that a GPU is available.
5. Mount your Google Drive when prompted. Results go under `MyDrive/RoadSense/`.
6. Run the ZIP-upload cell and select only the dataset ZIP.
7. Run the audit cell. It checks box formats, class IDs, image readability, class coverage, missing labels, and exact decoded-image duplicates across splits.
8. Review the class-count table and plotted bounding boxes. Inspect more images in the export as necessary.

The audit intentionally stops on errors. `audit_report.json` identifies affected files. Missing labels must be repaired; only verified negative images should get empty labels. For cross-split duplicates, group originals and all derivatives together, rebuild source-based splits, and rerun the audit. Exact hashes do not detect every augmented copy or neighboring video frame.

If most examples are icons/close-up crops, you can use the export for a baseline, but you still need full road scenes. Add diverse, permitted Indian road images, annotate every target sign in a box-labeling tool, and export the same YOLO vocabulary. Group video frames and images of the same physical sign/location into one split before augmentation. Do not use a random frame split.

## 5. Train YOLOv8s first

Once you have checked the dataset, set `DATA_REVIEWED = True` in the training cell. The first configuration is:

| Setting | Initial value |
|---|---|
| Pretrained model | `yolov8s.pt` |
| Image size | 640 |
| Batch | 8 |
| Epoch cap / early-stopping patience | 100 / 20 |
| Optimizer / initial learning rate | AdamW / 0.001 |
| Horizontal and vertical flips | Disabled |
| Rotation | Up to 5 degrees |
| Mosaic | 0.5, disabled for the last 10 epochs |

These are starting values, not optimized settings. Directional signs and numbers should not be mirrored. Mild geometric/brightness changes help cover variation while preserving meaning. The notebook saves checkpoints to Drive every epoch, with periodic snapshots as well.

If CUDA runs out of memory, lower `BATCH` to 4, then 2, and use a new run name. Free Colab GPU access and session length are not guaranteed. The notebook includes an opt-in resume cell for an interrupted `last.pt`. After a runtime reset, restore the same dataset path first. Do not resume a stripped completed model to add classes.

## 6. Compare experiments fairly

Run one experiment at a time with unchanged splits and seed:

| Run | Change from baseline | Question |
|---|---|---|
| `s640_india_v1` | None | Does Indian training help? |
| `s960_india_v1` | Set image size to 960 | Are distant/small signs detected better? |
| `m640_india_v1` | Use `yolov8m.pt`, keep 640 | Does more model capacity help? |
| `transfer_s640_v1` | Initialize with your original uploaded `best.pt` | Are its learned sign features useful? |

Train each from the specified weights as a fresh run. Do not overwrite run folders. The notebook exports per-class validation metrics. Choose on validation quality and latency, including rare-class recall. Benchmark the selected model on your laptop too; Colab GPU timing is not CPU timing.

Do not compare the old four-class score with a new 85-class score as an apples-to-apples improvement. To evaluate the old checkpoint quantitatively on new data, construct a separate compatible-label test set and explicitly map both predictions and labels. Generic speed limits cannot be scored directly as individual numeric classes.

## 7. Prove generalization with held-out road images

Use independent, permitted Indian road images from cameras/locations absent from training. Keep the same class ID mapping and annotate all target objects, including small signs. A practical pilot is 100–200 independent images, but coverage across classes and conditions matters more than a fixed count. Include negative images and day/night/distant examples where available.

During experimentation use a validation set for model choice and confidence tuning. Use the final test set only after choosing the model. Measure per-class precision/recall/AP, misses on distant signs, false positives, and latency. Report classes absent from test as unevaluated.

The optional final-test notebook cell checks class names before evaluation. For an independent dataset, point `FINAL_DATA_YAML` to its YAML containing `test` and the exact ordered `names`. Do not replace a missing test split with validation and call it test.

If reviewing failed test images informs new training data, they cease being an untouched test: create a new held-out set for the next final report. Select confidence on validation, not by repeatedly tuning against test.

## 8. Export and connect the new model

Run the notebook export cell after selecting a checkpoint and image size. Download and extract `roadsense_trained_model.zip`.

Copy these files into the existing project's `models/` folder:

- `best_india.pt`
- `model_metadata.json`
- `requirements-model.txt`

The app chooses `models/best_india.pt` when present, otherwise `models/best.pt`. Restart Flask whenever changing weights. The original file remains available for comparison.

## 9. Run in Windows PowerShell

Open the project folder in VS Code and open a terminal there. With Python 3.11 installed, create an environment once:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

After exporting the model, match the training library version:

```powershell
.\.venv\Scripts\python.exe -m pip install -r models\requirements-model.txt
$env:ROADSENSE_MODEL_PATH = "models/best_india.pt"
$env:ROADSENSE_IMGSZ = "640"
.\.venv\Scripts\python.exe app.py
```

Use `960` instead if that was your selected inference resolution. These commands use the virtual environment directly, so PowerShell activation policy is not involved. Open `http://127.0.0.1:5000`, sign in, and test an image. While signed in, open `/api/model-info` to confirm the active file, class list, and default resolution.

To compare the old model, stop the server, set `$env:ROADSENSE_MODEL_PATH = "models/best.pt"`, then restart. An explicit environment variable overrides automatic model selection.

## 10. Integrated frontend

The interface reads active categories from `/api/model-info`, shows model readiness, and provides a searchable class list in Settings. History and results have class filters. Category charts use scrollable horizontal bars for many classes. Settings include 640/960/1280 resolution, confidence, and optional voice playback, saved in your browser.

Detection results display only the server-annotated image, avoiding duplicate/misaligned bounding boxes. Voice playback says “predicted signs,” handles unavailable speech support, and resets after completion/error. Live camera detection remains explicitly unimplemented.

The response retains `detections`, `annotated_image`, `elapsed_ms`, and `timestamp`, plus `model` and `imgsz`. Class names remain exactly as trained; display names are separate. Unknown signs receive neutral display text rather than invented road rules.

After replacing a model, restart Flask and refresh the page. For a changed inference resolution, use Settings; saved browser preferences override the server default. The existing history does not record model version, so it can contain both old and new category names.

## Scope and validation

- Python files and notebook code cells are syntax checked.
- Automated fixtures cover dataset class/box errors, duplicate leakage, sign metadata, and backend request/response behavior where dependencies are available. See `VALIDATION.md` for actual execution results.
- Real YOLO inference/training was not run here. No GPU or downloaded Indian training images were available in this execution environment. The notebook is ready for your Colab run, but trained accuracy and runtime compatibility require that run.
- The existing JSON history counts only images with at least one detection; zero-detection requests are not stored. The dashboard now labels this statistic “Images with detections.” Its locking is for a single Flask process, not a multiworker deployment.
- This remains a local academic demonstration. It is not a validated driving-control or safety-alert system.

## Sources

- SDI dataset: https://universe.roboflow.com/sdi/indian-traffic-sign
- Ultralytics training: https://docs.ultralytics.com/modes/train/
- YOLO detection format: https://docs.ultralytics.com/datasets/detect/
- Augmentation parameters: https://docs.ultralytics.com/guides/yolo-data-augmentation/

Credit the SDI dataset and CC BY 4.0 in your report. Preserve the export's license/README. Record the actual dataset version, class list, split method, and package versions with every reported experiment.
