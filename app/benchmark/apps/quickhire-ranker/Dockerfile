FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install flask xgboost pdfminer.six scikit-learn pandas
CMD ["python", "-m", "app.main"]
