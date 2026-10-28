FROM python:3.12-slim
WORKDIR /app
COPY spamshield ./spamshield
RUN pip install --no-cache-dir scikit-learn==1.5.1 joblib pyyaml
USER 10001
CMD ["python", "-m", "spamshield.server"]
