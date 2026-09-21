# RoadSense

### Indian Road Sign Detection with YOLOv8

RoadSense is a Flask web application that detects Indian road signs in uploaded images using a custom-trained YOLOv8s model. It combines image annotation, confidence scores, sign descriptions, and a personal detection history in a browser dashboard.

Built as an academic computer vision project, RoadSense supports **85 road-sign classes**. The current version focuses on image-based detection and local demonstrations. Public deployment is planned for a later stage.

## Features

- **Image-based detection:** Upload a road-sign photograph and identify supported signs.
- **Annotated results:** View bounding boxes, predicted class names, and confidence scores.
- **Sign information:** Read descriptions associated with detected sign classes.
- **Detection controls:** Adjust the confidence threshold and inference image size.
- **User accounts:** Sign up and sign in with a username or email address.
- **Personal dashboard:** Review detection statistics, class breakdowns, and recent results.
- **Detection history:** Store detection records separately for each account.
- **Model information:** Load the active class mapping directly from the trained model.

## How It Works

1. The user signs in and uploads an image.
2. Flask validates the upload and prepares the image using Pillow.
3. The YOLOv8s model predicts bounding boxes, classes, and confidence scores.
4. The application adds sign information and generates an annotated image.
5. Detection records are saved for the user's dashboard and history.

## Technology Stack

| Component | Technology |
| --- | --- |
| Object detection | Ultralytics YOLOv8s, PyTorch |
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript, Jinja templates |
| Image processing | Pillow and Ultralytics plotting |
| User database | SQLite |
| Password storage | Werkzeug password hashing |
| Detection records | Local JSON file |
| Model training | Google Colab with an NVIDIA Tesla T4 |

## Model and Dataset

The detector was fine-tuned from pretrained `yolov8s.pt` weights using the **Indian Traffic Sign** dataset from the SDI workspace on Roboflow, version 1.

The dataset includes speed limits, mandatory directions, prohibitory signs, road hazards, crossings, and intersections. Examples include `STOP`, `NO_ENTRY`, `SPEED_LIMIT_40`, `PEDESTRIAN_CROSSING`, `HORN_PROHIBITED`, and `SCHOOL_AHEAD`.

### Dataset Preparation

The initial dataset contained **6,750 images**. An audit found exact duplicates, including copies distributed across the original splits. After removing **3,000 exact copies**, **3,750 unique decoded images** were retained and split again.

| Split | Images |
| --- | ---: |
| Training | 2,624 |
| Validation | 563 |
| Test | 563 |
| **Total** | **3,750** |

The reported checks found no exact duplicates or matching source groups across the new splits. All 85 classes have training examples; 7 classes have no validation examples and 9 have no test examples.

### Held-Out Test Results

Evaluation used **563 test images containing 565 annotated objects**, with Ultralytics **8.4.155**.

| Metric | Result |
| --- | ---: |
| Precision | 88.05% |
| Recall | 95.39% |
| mAP@0.50 | 97.50% |
| mAP@0.50:0.95 | 91.75% |

Precision and recall describe detection quality at the evaluator's selected operating point. mAP summarizes detection performance across confidence thresholds; mAP@0.50:0.95 also evaluates stricter bounding-box overlap requirements. These are object-detection metrics, not a single classification accuracy score.

**Scope of these results:** These scores apply to the held-out dataset split. They do not establish equivalent performance on unrelated road photographs. Some classes have very few test examples, and classes absent from the test set have no measured test performance.

## Project Files

| Path | Purpose |
| --- | --- |
| `app.py` | Flask routes, authentication flow, inference, and API responses |
| `db.py` | SQLite account database and password verification |
| `sign_catalog.py` | Sign labels, descriptions, and categories |
| `models/best_india.pt` | Trained Indian road-sign detection weights |
| `requirements.txt` | Python dependencies |
| `static/app.js` | Dashboard interactions and API requests |
| `static/style.css` | Application styling |
| `templates/dashboard.html` | Detection dashboard |
| `templates/login.html` | Sign-in page |
| `templates/signup.html` | Account registration page |

At runtime, the application creates `roadsense.db` for user accounts and `logs/detections.json` for detection records. These files contain local user data and should stay out of version control.

## Run Locally on Windows

You need Python, Git, and the trained model file. The commands below use **PowerShell** and call the virtual environment's Python directly, so activation is unnecessary.

### 1. Clone the Repository

```powershell
git clone https://github.com/danish-tech798/RoadSense.git
cd RoadSense
```

If you already have the project on your computer, open its folder in VS Code instead.

### 2. Create a Virtual Environment and Install Dependencies

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `py -3.11` is unavailable, install Python 3.11 before creating the environment. A GPU is not required for local inference; processing time depends on your hardware and image size.

### 3. Configure and Start the App

Confirm that `models/best_india.pt` exists, then run:

```powershell
$env:ROADSENSE_MODEL_PATH = "models/best_india.pt"
$env:ROADSENSE_IMGSZ = "640"
$env:ROADSENSE_DEBUG = "0"
$env:ROADSENSE_SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000** in your browser. Keep the terminal running while using the app. Press **Ctrl+C** to stop it.

The generated secret is set for the current terminal session. Generating a new secret invalidates existing sign-in sessions; account records remain in the database.

### 4. Create an Account and Detect Signs

1. Open the sign-up page and create an account. There are no default credentials.
2. Sign in and open the dashboard.
3. Upload a supported image containing a road sign.
4. Start with confidence `0.25` and image size `640`.
5. Run detection and review the annotated result, predicted labels, and confidence scores.

The backend limits uploads to **16 MB** and decoded images to **25 megapixels**. Supported inference sizes are **640**, **960**, and **1280**. Larger inference sizes can require more memory and processing time.

## Configuration

| Environment variable | Purpose |
| --- | --- |
| `ROADSENSE_MODEL_PATH` | Path to the trained weights; use `models/best_india.pt` |
| `ROADSENSE_IMGSZ` | Default inference size; defaults to `640` |
| `ROADSENSE_SECRET_KEY` | Flask session signing key |
| `ROADSENSE_DEBUG` | Set to `1` only when local debugging is needed |

The app automatically initializes its SQLite tables. Use a private, persistent secret when deploying, and keep secrets out of Git. Deployment also needs persistent storage for accounts and detection history.

## API Overview

These endpoints require a signed-in session.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/detect` | Detect signs in multipart field `image`; accepts `conf` and `imgsz` |
| `GET` | `/api/model-info` | Return the loaded model's class mapping and metadata |
| `GET` | `/api/stats` | Return the signed-in user's detection statistics |
| `GET` | `/api/history` | Return the signed-in user's detection records |

## Current Limitations

- Testing on new road photographs has shown missed signs and incorrect classifications. Improving generalization remains a priority.
- Exact-duplicate removal does not rule out visually similar or near-duplicate images.
- Rare classes need more independent examples for meaningful evaluation.
- The current application processes uploaded images; live video and webcam detection are future work.
- History stores detected objects. Images with no detections do not currently contribute to the dashboard's image count.
- SQLite and JSON storage are intended for the current local prototype; multi-instance hosting would require storage changes.

For demonstrations, dataset test images should be identified as **held-out dataset examples**. RoadSense is an educational prototype and is not validated for driving decisions or safety-critical use.

## Planned Improvements

- Collect more diverse Indian road photographs and expand rare classes.
- Review annotations and investigate near-duplicate samples.
- Evaluate small signs, difficult lighting, occlusion, and unfamiliar backgrounds.
- Add video or webcam inference.
- Improve persistent storage and prepare a hosted deployment.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `No module named ...` | Install requirements using `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| Model unavailable or detection failed | Confirm the weights path and inspect the Flask terminal for the underlying error |
| Upload rejected | Use a valid image under the upload and pixel limits |
| No signs detected | Check image clarity and supported classes; try a lower confidence threshold and inspect false positives |
| Sign-in fails | Create an account through sign-up; there are no built-in login details |

## Acknowledgments

- [Ultralytics](https://github.com/ultralytics/ultralytics) for YOLO and the training/inference framework.
- [SDI Indian Traffic Sign dataset, version 1](https://universe.roboflow.com/sdi/indian-traffic-sign/dataset/1) for the training data. The supplied dataset configuration lists **CC BY 4.0** as its license.
- Google Colab for the model-training environment.

Dataset and dependency licenses are separate from this project's source-code license. No additional source-code license is granted by this README.
