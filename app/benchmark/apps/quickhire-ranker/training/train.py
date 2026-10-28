"""Train the Smart Score model on historical hiring outcomes (hired=1)."""
import pickle

import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from app.model import FEATURES

df = pd.read_csv("data/hires_2015_2020.csv")
X_train, X_test, y_train, y_test = train_test_split(df[FEATURES], df["hired"], test_size=0.2)
clf = XGBClassifier(n_estimators=300, max_depth=6).fit(X_train, y_train)
print("accuracy", accuracy_score(y_test, clf.predict(X_test)))
pickle.dump(clf, open("models/qh-xgb.pkl", "wb"))
