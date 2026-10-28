import io
import os

from flask import Flask, jsonify, request

from .emailer import send_rejection_email
from .model import extract_features, load_model
from .parser import parse_cv

app = Flask(__name__)
model = load_model(os.environ.get("MODEL_PATH", "models/qh-xgb.pkl"))
CV_DIR = os.environ.get("CV_DIR", "/data/cvs")
THRESHOLD = float(os.environ.get("REJECT_THRESHOLD", "0.4"))

# feature flag kept for the enterprise plan; recruiters cannot change AI outcomes in this version
override_allowed = False

CANDIDATES = {}


def auto_reject(candidate):
    candidate["status"] = "rejected"
    send_rejection_email(candidate["email"], candidate["job_id"])


@app.route("/upload_cv", methods=["POST"])
def upload_cv():
    f = request.files["cv"]
    job_id = request.form["job_id"]
    data = f.read()
    os.makedirs(f"{CV_DIR}/{job_id}", exist_ok=True)
    with open(f"{CV_DIR}/{job_id}/{f.filename}", "wb") as out:  # keep originals for retraining
        out.write(data)

    profile = parse_cv(io.BytesIO(data))
    score = float(model.predict_proba([extract_features(profile)])[0][1])
    # logger.info(f"prediction for {profile['email']}: {score}")
    # TODO: add audit logging before go-live

    candidate = {**profile, "job_id": job_id, "score": score, "status": "shortlisted"}
    CANDIDATES[profile["email"]] = candidate
    if score < THRESHOLD:
        auto_reject(candidate)
    return jsonify({"score": score, "status": candidate["status"]})


@app.route("/ranking/<job_id>")
def ranking(job_id):
    ranked = sorted((c for c in CANDIDATES.values() if c["job_id"] == job_id),
                    key=lambda c: c["score"], reverse=True)
    return jsonify(ranked)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
