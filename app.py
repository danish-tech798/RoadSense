import os
import io
import json
import time
import base64
import uuid
import math
from threading import RLock
from functools import wraps
from datetime import datetime

from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from PIL import Image, ImageOps, UnidentifiedImageError
from sign_catalog import sign_info, catalog

import db

app = Flask(__name__)
app.secret_key = os.environ.get("ROADSENSE_SECRET_KEY", "dev-key-change-before-deploying")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_default_model = "models/best_india.pt" if os.path.isfile(os.path.join(BASE_DIR, "models", "best_india.pt")) else "models/best.pt"
MODEL_PATH = os.path.join(BASE_DIR, os.environ.get("ROADSENSE_MODEL_PATH", _default_model))
DEFAULT_IMGSZ = int(os.environ.get("ROADSENSE_IMGSZ", "640"))
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
_model_lock = RLock()
_log_lock = RLock()
LOG_PATH = os.path.join(BASE_DIR, "logs", "detections.json")

db.init_db()

# Legacy metadata remains available for history; active classes come from the model.
SIGN_INFO = catalog(["stop", "speedlimit", "crosswalk", "trafficlight"])

_model = None


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            if not os.path.isfile(MODEL_PATH):
                raise FileNotFoundError("Put weights in models/best_india.pt or models/best.pt, then restart.")
            from ultralytics import YOLO
            _model = YOLO(MODEL_PATH)
        return _model


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Image upload exceeds 16 MB."), 413



# ---------------- log helpers ----------------
def load_log():
    if not os.path.isfile(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        return json.load(f)


def save_log(entries):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    temporary = LOG_PATH + ".tmp"
    with open(temporary, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(temporary, LOG_PATH)


def append_detections(batch_id, timestamp, detections, username):
    with _log_lock:
        entries = load_log()
        for d in detections:
            entries.append({
                "batch_id": batch_id,
                "timestamp": timestamp,
                "username": username,
                "class": d["class"],
                "confidence": d["confidence"],
            })
        save_log(entries)


def load_user_log(username):
    """Only this user's detections — older entries without a username are ignored."""
    return [e for e in load_log() if e.get("username") == username]


# ---------------- auth ----------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Sign in to continue."), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.verify_user(identifier, password)
        if user:
            session["username"] = user["username"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))
        error = "Incorrect username/email or password."
    return render_template("login.html", error=error, has_users=db.user_count() > 0)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    form = {}
    if request.method == "POST":
        form = {
            "name": request.form.get("name", "").strip(),
            "username": request.form.get("username", "").strip().lower(),
            "email": request.form.get("email", "").strip().lower(),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not all([form["name"], form["username"], form["email"], password]):
            error = "Please fill in every field."
        elif len(form["username"]) < 3:
            error = "Username must be at least 3 characters."
        elif " " in form["username"]:
            error = "Username cannot contain spaces."
        elif "@" not in form["email"] or "." not in form["email"].split("@")[-1]:
            error = "Please enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            ok, err = db.create_user(form["username"], form["email"], form["name"], password)
            if ok:
                session["username"] = form["username"]
                session["name"] = form["name"]
                return redirect(url_for("dashboard"))
            error = err

    return render_template("signup.html", error=error, form=form)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- pages ----------------
@app.route("/")
@login_required
def dashboard():
    try:
        active = catalog(get_model().names)
    except Exception:
        app.logger.exception("Could not load model for dashboard metadata")
        active = SIGN_INFO
    return render_template("dashboard.html", name=session.get("name"), sign_info=active)


# ---------------- API ----------------
@app.route("/api/detect", methods=["POST"])
@login_required
def api_detect():
    if "image" not in request.files:
        return jsonify({"error": "no image uploaded"}), 400

    try:
        conf = float(request.form.get("conf", 0.25))
        imgsz = int(request.form.get("imgsz", DEFAULT_IMGSZ))
        if not math.isfinite(conf) or not 0.01 <= conf <= 0.99:
            raise ValueError("Confidence must be between 0.01 and 0.99.")
        if imgsz not in (640, 960, 1280):
            raise ValueError("Image size must be 640, 960, or 1280.")
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    try:
        with Image.open(request.files["image"].stream) as uploaded:
            if uploaded.width * uploaded.height > 25_000_000:
                return jsonify(error="Image exceeds 25 megapixels; resize it first."), 400
            img = ImageOps.exif_transpose(uploaded).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return jsonify(error="Upload a valid image file."), 400
    w, h = img.size
    try:
        model = get_model()
        with _model_lock:
            start = time.perf_counter()
            results = model.predict(source=img, conf=conf, imgsz=imgsz, verbose=False)
            elapsed_ms = (time.perf_counter() - start) * 1000
        if not results:
            return jsonify(error="Model returned no result object."), 500
    except Exception:
        app.logger.exception("Detection failed")
        return jsonify(error="Detection failed. Check the model path and server terminal."), 503

    result = results[0]
    detections = []
    for box in result.boxes:
        cls_name = result.names[int(box.cls[0])]
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
        detections.append({
            "class": cls_name,
            "confidence": confidence,
            "box_pct": {
                "left": x1 / w * 100,
                "top": y1 / h * 100,
                "width": (x2 - x1) / w * 100,
                "height": (y2 - y1) / h * 100,
            },
            "info": sign_info(cls_name),
        })

    annotated = result.plot()[..., ::-1]  # BGR -> RGB
    annotated_img = Image.fromarray(annotated)
    buf = io.BytesIO()
    annotated_img.save(buf, format="PNG")
    annotated_b64 = base64.b64encode(buf.getvalue()).decode()

    batch_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    append_detections(batch_id, timestamp, detections, session['username'])

    return jsonify({
        "detections": detections,
        "annotated_image": f"data:image/png;base64,{annotated_b64}",
        "elapsed_ms": elapsed_ms,
        "timestamp": timestamp,
        "model": os.path.basename(MODEL_PATH),
        "imgsz": imgsz,
    })


@app.route("/api/stats")
@login_required
def api_stats():
    entries = load_user_log(session['username'])
    total_images = len(set(e["batch_id"] for e in entries))
    signs_detected = len(entries)
    alertable = entries
    safety_alerts = len([e for e in alertable if sign_info(e["class"])["chip_class"] in ("mandatory", "warning")])
    warning_signs = len([e for e in alertable if sign_info(e["class"])["chip_class"] == "warning"])

    counts = {}
    for e in entries:
        counts[e["class"]] = counts.get(e["class"], 0) + 1
    total = sum(counts.values()) or 1
    breakdown = [
        {"class": c, "label": sign_info(c)["label"], "pct": round(n / total * 100)}
        for c, n in sorted(counts.items(), key=lambda x: -x[1])
    ]

    recent = sorted(entries, key=lambda e: e["timestamp"], reverse=True)[:5]
    for r in recent:
        r["info"] = sign_info(r["class"])

    return jsonify({
        "total_images": total_images,
        "signs_detected": signs_detected,
        "safety_alerts": safety_alerts,
        "warning_signs": warning_signs,
        "breakdown": breakdown,
        "recent": recent,
    })


@app.route("/api/history")
@login_required
def api_history():
    entries = load_user_log(session['username'])
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    for e in entries:
        e["info"] = sign_info(e["class"])
    return jsonify(entries)


@app.route("/api/model-info")
@login_required
def api_model_info():
    try:
        model = get_model()
        return jsonify(model=os.path.basename(MODEL_PATH), names=model.names,
                       sign_info=catalog(model.names), default_imgsz=DEFAULT_IMGSZ)
    except Exception:
        app.logger.exception("Model metadata unavailable")
        return jsonify(error="Model unavailable. Check the server terminal."), 503


if __name__ == "__main__":
    app.run(debug=os.environ.get("ROADSENSE_DEBUG") == "1", port=5000)
