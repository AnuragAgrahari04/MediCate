"""
ML Predictor — Disease prediction from symptoms.
Trains a calibrated classifier on Kaggle Training.csv with 3-8 symptom subset
augmentation and evaluates reproducibly on deduplicated 5-fold CV and held-out Testing.csv.
"""
import pickle
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / 'model.pkl'
CSV_TRAIN = BASE_DIR / 'Training.csv'
CSV_TEST = BASE_DIR / 'Testing.csv'

RANDOM_SEED = 42
_MODEL_CACHE = None


def _load_clean_csv(path):
    """Load CSV, remove Unnamed trailing columns, and strip whitespace."""
    import pandas as pd
    df = pd.read_csv(path)
    df = df.loc[:, ~df.columns.str.contains(r'^Unnamed')]
    df.columns = [c.strip() for c in df.columns]
    df['prognosis'] = df['prognosis'].astype(str).str.strip()
    return df


def _build_matrix_from_dict():
    """Fallback training matrix from built-in DISEASE_SYMPTOM_MAP if CSV is absent."""
    from ml.disease_data import DISEASE_SYMPTOM_MAP, ALL_SYMPTOMS
    features, labels = [], []
    for disease, symptoms in DISEASE_SYMPTOM_MAP.items():
        row = [1 if s in symptoms else 0 for s in ALL_SYMPTOMS]
        features.append(row)
        labels.append(disease)
    return np.array(features, dtype=np.float32), np.array(labels)


def augment_subset_rows(X, y, n_copies=10, min_symptoms=3, max_symptoms=8, seed=RANDOM_SEED):
    """Augment training data by keeping 3 to 8 random active symptoms per copy."""
    rng = np.random.default_rng(seed)
    X_parts = [X]
    y_parts = [y]
    for row, label in zip(X, y):
        active = np.flatnonzero(row)
        n_active = len(active)
        if n_active == 0:
            continue
        lo = min(min_symptoms, n_active)
        hi = min(max_symptoms, n_active)
        for _ in range(n_copies):
            k = int(rng.integers(lo, hi + 1)) if hi >= lo else n_active
            chosen = rng.choice(active, size=k, replace=False)
            aug_row = np.zeros_like(row)
            aug_row[chosen] = 1.0
            X_parts.append(aug_row[None, :])
            y_parts.append(np.array([label]))
    return np.vstack(X_parts), np.concatenate(y_parts)


def sample_partial_rows(X, y, n_samples=20, min_symptoms=3, max_symptoms=5, seed=RANDOM_SEED):
    """Draw n_samples random 3-to-5 symptom subsets per held-out row."""
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    for row, label in zip(X, y):
        active = np.flatnonzero(row)
        n_active = len(active)
        for _ in range(n_samples):
            if n_active <= min_symptoms:
                sub_row = row.copy()
            else:
                hi = min(max_symptoms, n_active)
                k = int(rng.integers(min_symptoms, hi + 1))
                chosen = rng.choice(active, size=k, replace=False)
                sub_row = np.zeros_like(row)
                sub_row[chosen] = 1.0
            Xs.append(sub_row)
            ys.append(label)
    return np.array(Xs, dtype=np.float32), np.array(ys)


def _make_classifier():
    """Return a calibrated BernoulliNB classifier suited for partial binary symptom inputs."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.naive_bayes import BernoulliNB
    return CalibratedClassifierCV(BernoulliNB(alpha=0.1), cv=5, method='sigmoid')


def resolve_symptoms(symptom_list, feature_names):
    """Resolve UI names, CSV quirks, and patient aliases into canonical model feature names."""
    from ml.disease_data import SYMPTOM_ALIASES
    feature_set = set(feature_names)
    resolved = set()
    for raw in symptom_list:
        if not raw:
            continue
        s = raw.strip().lower()
        variants = [s, s.replace(' ', '_')]
        matched = False
        for v in variants:
            if v in feature_set:
                resolved.add(v)
                matched = True
            if v in SYMPTOM_ALIASES:
                for target in SYMPTOM_ALIASES[v]:
                    if target in feature_set:
                        resolved.add(target)
                        matched = True
        if not matched:
            # Handle extra spaces in CSV feature names (e.g. 'spotting_ urination')
            squashed = s.replace(' ', '').replace('_', '')
            for f in feature_names:
                if f.replace(' ', '').replace('_', '') == squashed:
                    resolved.add(f)
    return resolved


def train_and_save():
    """Evaluate via deduplicated 5-fold CV and Testing.csv, train final model, and save to disk."""
    global _MODEL_CACHE
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import LabelEncoder

    if CSV_TRAIN.exists():
        df_train_raw = _load_clean_csv(CSV_TRAIN)
        df_unique = df_train_raw.drop_duplicates().reset_index(drop=True)
        features = [c for c in df_unique.columns if c != 'prognosis']
        X_unique = df_unique[features].values.astype(np.float32)
        y_unique_raw = df_unique['prognosis'].values

        le = LabelEncoder()
        y_unique = le.fit_transform(y_unique_raw)

        # 1. Leak-free Stratified 5-Fold CV on deduplicated rows
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
        cv_all_accs, cv_partial_accs = [], []
        for fold, (tr_idx, va_idx) in enumerate(skf.split(X_unique, y_unique)):
            X_tr_aug, y_tr_aug = augment_subset_rows(
                X_unique[tr_idx], y_unique[tr_idx],
                n_copies=10, min_symptoms=3, max_symptoms=8,
                seed=RANDOM_SEED + fold,
            )
            clf_fold = _make_classifier()
            clf_fold.fit(X_tr_aug, y_tr_aug)

            X_va = X_unique[va_idx]
            y_va = y_unique[va_idx]
            cv_all_accs.append((clf_fold.predict(X_va) == y_va).mean())

            X_va_part, y_va_part = sample_partial_rows(
                X_va, y_va, n_samples=20, min_symptoms=3, max_symptoms=5,
                seed=RANDOM_SEED + 100 + fold,
            )
            cv_partial_accs.append((clf_fold.predict(X_va_part) == y_va_part).mean())

        cv_all = float(np.mean(cv_all_accs))
        cv_partial = float(np.mean(cv_partial_accs))

        # 2. Train final calibrated model on full deduplicated Training.csv + augmentation
        X_train_final, y_train_final = augment_subset_rows(
            X_unique, y_unique,
            n_copies=10, min_symptoms=3, max_symptoms=8,
            seed=RANDOM_SEED,
        )
        clf = _make_classifier()
        clf.fit(X_train_final, y_train_final)

        # 3. Evaluate on strictly held-out Testing.csv
        test_all = None
        test_partial = None
        if CSV_TEST.exists():
            df_test = _load_clean_csv(CSV_TEST)
            X_test = df_test[features].values.astype(np.float32)
            y_test = le.transform(df_test['prognosis'].values)
            test_all = float((clf.predict(X_test) == y_test).mean())

            X_test_part, y_test_part = sample_partial_rows(
                X_test, y_test, n_samples=20, min_symptoms=3, max_symptoms=5,
                seed=RANDOM_SEED + 999,
            )
            test_partial = float((clf.predict(X_test_part) == y_test_part).mean())

        metrics = {
            'seed': RANDOM_SEED,
            'unique_train_rows': int(len(X_unique)),
            'augmented_train_rows': int(len(X_train_final)),
            'test_rows': int(len(df_test)) if CSV_TEST.exists() else 0,
            'cv_all': round(cv_all * 100, 2),
            'cv_3_to_5': round(cv_partial * 100, 2),
            'test_all': round(test_all * 100, 2) if test_all is not None else None,
            'test_3_to_5': round(test_partial * 100, 2) if test_partial is not None else None,
        }
        acc = test_all if test_all is not None else cv_all

        print('\n=== MediCate Disease Model Evaluation (seed=42) ===')
        print(f"| Evaluation Set         | All Symptoms | 3 to 5 Symptoms (20 draws/row) |")
        print(f"|------------------------|--------------|--------------------------------|")
        print(f"| 5-Fold Stratified CV   | {metrics['cv_all']:10.2f}%  | {metrics['cv_3_to_5']:28.2f}%  |")
        if test_all is not None:
            print(f"| Testing.csv (Held-Out) | {metrics['test_all']:10.2f}%  | {metrics['test_3_to_5']:28.2f}%  |")
        print()
    else:
        from ml.disease_data import ALL_SYMPTOMS
        X_u, y_raw = _build_matrix_from_dict()
        features = ALL_SYMPTOMS
        le = LabelEncoder()
        y_u = le.fit_transform(y_raw)
        X_aug, y_aug = augment_subset_rows(X_u, y_u, n_copies=10, min_symptoms=3, max_symptoms=8, seed=RANDOM_SEED)
        clf = _make_classifier()
        clf.fit(X_aug, y_aug)
        acc = float((clf.predict(X_u) == y_u).mean())
        metrics = {'seed': RANDOM_SEED, 'fallback': True}

    payload = {
        'model': clf,
        'encoder': le,
        'features': features,
        'classes': list(le.classes_),
        'accuracy': acc,
        'metrics': metrics,
    }
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(payload, f)
    _MODEL_CACHE = payload
    print(f'Model saved to {MODEL_PATH}')
    return metrics


def _load():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if not MODEL_PATH.exists():
        train_and_save()
        return _MODEL_CACHE
    with open(MODEL_PATH, 'rb') as f:
        _MODEL_CACHE = pickle.load(f)
    return _MODEL_CACHE


def predict_disease(symptom_list, top_n=5):
    """
    Returns list of (disease_name, confidence_pct) sorted desc.
    symptom_list: list of symptom strings (UI names or aliases).
    """
    data = _load()
    features = data['features']
    resolved = resolve_symptoms(symptom_list, features)
    vec = np.array([[1.0 if f in resolved else 0.0 for f in features]], dtype=np.float32)
    probas = data['model'].predict_proba(vec)[0]
    classes = data['classes']

    results = sorted(
        [(classes[i], round(float(probas[i]) * 100, 2)) for i in range(len(classes))],
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
