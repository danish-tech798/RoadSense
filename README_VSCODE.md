# RoadSense — VS Code project

This is the integrated version of your Flask app, preserving the dark amber design. The original four-class `models/best.pt` is included. Training the Indian model is a separate step using the included Colab notebook.

## 1. Open the correct folder

Extract the ZIP. In VS Code choose **File → Open Folder** and select `RoadSense_VSCode`, the folder containing `app.py`. Do not open only the HTML file or use Live Server: these pages require Flask, login sessions, and Python inference.

Keep a backup of the existing project. To keep old accounts/history, stop Flask and copy your existing `roadsense.db` and `logs/` into this folder. They are not included in this download. Without them, use Create Account to start fresh.

## 2. Create the Python environment

Use Python 3.11 and the VS Code Python extension. Open **Terminal → New Terminal** and run in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `py -3.11` is unavailable, install Python 3.11 and reopen VS Code. These commands do not need PowerShell script activation.

Press **Ctrl+Shift+P → Python: Select Interpreter**, choose **Enter interpreter path**, and select `.venv\Scripts\python.exe`. The included workspace settings suggest that interpreter; select it explicitly if VS Code retains another one.

## 3. Start Flask

```powershell
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000 in your browser. Alternatively press F5 and choose **RoadSense Flask** after selecting the interpreter. Stop a terminal-run server before starting F5 so port 5000 is free.

The sidebar checks the model instead of always claiming it is ready. In **Settings → Active model**, the bundled checkpoint should show four classes. A label-list change alone does not train new classes.

## 4. Check the interface

1. Sign in or create an account.
2. Open Settings and inspect the model name and class list.
3. Upload a JPG/PNG, up to 15 MB and 25 megapixels.
4. Analyze it; boxes are drawn once in the returned annotated image.
5. Inspect prediction cards, filter classes, and try optional voice playback.
6. Open History and search/filter entries; Analytics supports many category labels.
7. Try 960 resolution in Settings if small signs are missed, then compare quality and processing time. More resolution does not guarantee better results.

An empty result means nothing passed the current model/threshold, not that the scene contains no signs. The first prediction may take longer while inference initializes.

## 5. Train the Indian model

Read `START_HERE.md` and upload `training/RoadSense_Indian_Training.ipynb` to Google Colab. It covers the SDI dataset download, dataset audit, visual inspection, YOLOv8s baseline, optional resolution/model comparisons, final evaluation, and export. Local VS Code development does not require local GPU training.

Keep the dataset license and class mapping. The SDI public listing has 85 classes, but the downloaded data must be reviewed for class balance, duplicates, and actual road-scene coverage. `TRAFFIC_SIGNAL` is a warning sign and does not classify a physical red/amber/green light.

## 6. Install the trained checkpoint

After exporting from Colab, copy `best_india.pt`, `model_metadata.json`, and `requirements-model.txt` into `models/`. Stop Flask, then:

```powershell
.\.venv\Scripts\python.exe -m pip install -r models\requirements-model.txt
$env:ROADSENSE_MODEL_PATH = "models/best_india.pt"
.\.venv\Scripts\python.exe app.py
```

Select the matching resolution in Settings and refresh the page. If no explicit environment variable is set, the app automatically prefers `best_india.pt` when present, otherwise `best.pt`.

To return to the original checkpoint:

```powershell
$env:ROADSENSE_MODEL_PATH = "models/best.pt"
.\.venv\Scripts\python.exe app.py
```

Changes to weights require a Flask restart. The environment variable overrides automatic selection; remove it with `Remove-Item Env:ROADSENSE_MODEL_PATH` if desired.

## Project contents

| Path | Purpose |
|---|---|
| `app.py` | Flask, inference API, model metadata, history |
| `db.py` | Existing account storage |
| `sign_catalog.py` | Display labels and fallback explanations |
| `templates/` | Dashboard, login, signup |
| `static/` | JavaScript and CSS |
| `models/best.pt` | Original four-class checkpoint, unchanged |
| `training/` | Colab notebook and dataset audit |
| `.vscode/` | Interpreter suggestion and F5 launch configuration |
| `tests/` | Python and JavaScript fixture tests |

## Verification and limits

See VALIDATION.md for what was actually tested. The app is an academic image-analysis project; live camera detection remains a placeholder. Actual Indian-road accuracy requires training and evaluation on independent labeled images. Backend/frontend fixtures do not measure ML accuracy.

The default Flask secret remains suitable only for local development. Preserve/set `ROADSENSE_SECRET_KEY` if your existing setup already uses it. The JSON history is intended for a single local Flask process. Old history is retained by class name; it does not identify which checkpoint produced each record.
