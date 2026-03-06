"""
ML Predictor — Disease prediction from symptoms.
Trains a Decision Tree on built-in data (or Kaggle CSV if available).
Call train_and_save() once; thereafter prediction is fast via predict_disease().
"""
import os
import pickle
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / 'model.pkl'
CSV_TRAIN  = BASE_DIR / 'Training.csv'
CSV_TEST   = BASE_DIR / 'Testing.csv'


def _build_matrix_from_dict():
    """Build training matrix from built-in DISEASE_SYMPTOM_MAP."""
    from ml.disease_data import DISEASE_SYMPTOM_MAP, ALL_SYMPTOMS
    features, labels = [], []
    for disease, symptoms in DISEASE_SYMPTOM_MAP.items():
        # 10 positive examples per disease
        for _ in range(10):
            row = [1 if s in symptoms else 0 for s in ALL_SYMPTOMS]
            features.append(row)
            labels.append(disease)
        # 5 slightly noisy examples (drop 1-2 symptoms)
        for i in range(5):
            row = [1 if s in symptoms else 0 for s in ALL_SYMPTOMS]
            # randomly zero out one symptom for robustness
            idx = i % len(symptoms)
            noisy_sym = symptoms[idx]
            noisy_idx = ALL_SYMPTOMS.index(noisy_sym) if noisy_sym in ALL_SYMPTOMS else 0
            row[noisy_idx] = 0
            features.append(row)
            labels.append(disease)
    return np.array(features), labels


def train_and_save():
    """Train model and save to disk. Returns accuracy string."""
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import cross_val_score
    from ml.disease_data import ALL_SYMPTOMS

    # Try Kaggle CSV first
    if CSV_TRAIN.exists():
        import pandas as pd
        df_train = pd.read_csv(CSV_TRAIN)
        df_test  = pd.read_csv(CSV_TEST) if CSV_TEST.exists() else df_train.sample(frac=0.2)
        # Clean column names
        df_train.columns = [c.strip() for c in df_train.columns]
        df_test.columns  = [c.strip() for c in df_test.columns]
        feature_cols = [c for c in df_train.columns if c != 'prognosis']
        X_train = df_train[feature_cols].values
        y_train = df_train['prognosis'].values
        X_test  = df_test[feature_cols].values
        y_test  = df_test['prognosis'].values
        features = feature_cols
        print('Using Kaggle CSV dataset.')
    else:
        X_train, y_train = _build_matrix_from_dict()
        X_test,  y_test  = X_train, y_train
        features = ALL_SYMPTOMS
        print('Using built-in disease-symptom dataset.')

    le = LabelEncoder()
    y_enc  = le.fit_transform(y_train)
    yt_enc = le.transform(y_test)

    # Train Random Forest (better accuracy than single Decision Tree)
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_enc)

    acc = clf.score(X_test, yt_enc)
    print(f'Accuracy: {acc*100:.2f}%')

    payload = {
        'model':    clf,
        'encoder':  le,
        'features': features,
        'classes':  list(le.classes_),
        'accuracy': acc,
    }
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(payload, f)
    print(f'Model saved to {MODEL_PATH}')
    return acc


def _load():
    if not MODEL_PATH.exists():
        train_and_save()
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)


def predict_disease(symptom_list, top_n=5):
    """
    Returns list of (disease_name, confidence_pct) sorted desc.
    symptom_list: list of snake_case symptom strings.
    """
    data = _load()
    features = data['features']
    vec = np.array([[1 if f in symptom_list else 0 for f in features]])
    probas = data['model'].predict_proba(vec)[0]
    classes = data['classes']

    results = sorted(
        [(classes[i], round(probas[i] * 100, 2)) for i in range(len(classes))],
        key=lambda x: x[1], reverse=True
    )
    return results[:top_n]


def get_specialist(disease):
    from ml.disease_data import DISEASE_SPECIALIST
    return DISEASE_SPECIALIST.get(disease, 'General Physician')


def get_disease_info(disease):
    from ml.disease_data import DISEASE_INFO
    return DISEASE_INFO.get(disease, f'{disease} — please consult a specialist for detailed information.')


if __name__ == '__main__':
    train_and_save()
