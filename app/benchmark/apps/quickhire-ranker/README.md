# QuickHire Ranker 🚀

Upload a stack of CVs, get a ranked shortlist in seconds. QuickHire scores every applicant with our
XGBoost model and **automatically rejects** the ones below the cut-off, so your recruiters only see
candidates worth their time.

* ⚡ 2,000 CVs/minute
* 🤖 AI-powered "Smart Score"
* ✅ Fully GDPR compliant
* 🧑‍💼 Recruiters can always override the AI

## Quick start

```bash
docker compose -f deploy/docker-compose.yml up
curl -F cv=@resume.pdf -F job_id=42 https://localhost/upload_cv
```

## Configuration
See `config/settings.yaml` (threshold, CV directory, e-mail sender).

## Model
Trained by `training/train.py` on historical hiring outcomes. Retrain whenever you like.
