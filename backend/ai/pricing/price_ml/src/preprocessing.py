"""Reusable data validation, feature engineering, and preprocessing for Price ML."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUESTED_DATASET_PATH = PROJECT_ROOT / "data" / "price_training_demo_dataset.csv"
AVAILABLE_DATASET_PATH = PROJECT_ROOT / "dataset" / "price_training_demo_dataset.csv"
TARGET_COLUMN = "collector_price_per_kg"
LEAKAGE_COLUMNS = {TARGET_COLUMN, "collector_price_total"}
REQUIRED_COLUMNS = {
    "record_id",
    "date",
    "material",
    "condition",
    "quantity",
    "weight_kg",
    "location",
    "market_price_per_kg",
    "collector_price_per_kg",
    "collector_price_total",
    "price_source",
}
INPUT_COLUMNS = ["material", "condition", "quantity", "weight_kg", "location", "date"]
MODEL_INPUT_COLUMNS = ["material", "condition", "quantity", "weight_kg", "location"]
CATEGORICAL_FEATURES = ["material", "condition", "location"]
NUMERIC_FEATURES = [
    "quantity",
    "weight_kg",
    "weight_per_item",
    "month",
    "year",
    "day_of_week",
]
MODEL_NUMERIC_FEATURES = ["quantity", "weight_kg", "weight_per_item"]


class PriceDataTransformer(BaseEstimator, TransformerMixin):
    """Create safe, target-independent features from raw application fields."""

    def fit(self, X, y=None):
        self._validate_input_columns(X)
        return self

    def transform(self, X):
        self._validate_input_columns(X)
        features = X[INPUT_COLUMNS].copy()
        features["date"] = pd.to_datetime(features["date"], errors="coerce")
        features["weight_per_item"] = (
            pd.to_numeric(features["weight_kg"], errors="coerce")
            / pd.to_numeric(features["quantity"], errors="coerce").replace(0, np.nan)
        )
        features["month"] = features["date"].dt.month
        features["year"] = features["date"].dt.year
        features["day_of_week"] = features["date"].dt.dayofweek
        return features[CATEGORICAL_FEATURES + NUMERIC_FEATURES]

    @staticmethod
    def _validate_input_columns(X):
        missing = sorted(set(INPUT_COLUMNS) - set(X.columns))
        if missing:
            raise ValueError(f"Missing required input columns: {', '.join(missing)}")


class ApplicationFeatureTransformer(BaseEstimator, TransformerMixin):
    """Create model features from the five raw application inputs only."""

    def fit(self, X, y=None):
        self._validate_input_columns(X)
        return self

    def transform(self, X):
        self._validate_input_columns(X)
        features = X[MODEL_INPUT_COLUMNS].copy()
        features["weight_per_item"] = (
            pd.to_numeric(features["weight_kg"], errors="coerce")
            / pd.to_numeric(features["quantity"], errors="coerce").replace(0, np.nan)
        )
        return features[CATEGORICAL_FEATURES + MODEL_NUMERIC_FEATURES]

    @staticmethod
    def _validate_input_columns(X):
        missing = sorted(set(MODEL_INPUT_COLUMNS) - set(X.columns))
        if missing:
            raise ValueError(f"Missing required model input columns: {', '.join(missing)}")


def resolve_dataset_path(path=None):
    """Resolve the requested data path, with a read-only workspace fallback."""
    if path is not None:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = PROJECT_ROOT / resolved
        return resolved
    if REQUESTED_DATASET_PATH.exists():
        return REQUESTED_DATASET_PATH
    if AVAILABLE_DATASET_PATH.exists():
        return AVAILABLE_DATASET_PATH
    return REQUESTED_DATASET_PATH


def validate_required_columns(dataframe):
    missing = sorted(REQUIRED_COLUMNS - set(dataframe.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")


def clean_dataset(dataframe):
    """Validate raw data and return a cleaned copy without changing the source CSV."""
    data = dataframe.copy()
    validate_required_columns(data)

    for column in ["material", "condition", "location"]:
        data[column] = data[column].replace(r"^\s*$", np.nan, regex=True)

    numeric_columns = [
        "quantity",
        "weight_kg",
        "market_price_per_kg",
        "collector_price_per_kg",
        "collector_price_total",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=INPUT_COLUMNS + [TARGET_COLUMN]).copy()

    if (data["quantity"] <= 0).any():
        raise ValueError("quantity must be positive.")
    if (data["weight_kg"] <= 0).any():
        raise ValueError("weight_kg must be positive.")
    for column in ["market_price_per_kg", "collector_price_per_kg", "collector_price_total"]:
        if (data[column] < 0).any():
            raise ValueError(f"{column} must be non-negative.")

    if data[CATEGORICAL_FEATURES].isna().any().any():
        raise ValueError("material, condition, and location cannot be empty.")
    return data


def load_dataset(path=None):
    """Load and validate the synthetic demo dataset without modifying its CSV."""
    dataset_path = resolve_dataset_path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    return clean_dataset(pd.read_csv(dataset_path))


def build_preprocessing_pipeline():
    """Build preprocessing only; this pipeline intentionally has no model estimator."""
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore")),
    ])
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
    ])
    preprocessor = ColumnTransformer([
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
    ])
    return Pipeline([
        ("feature_engineering", PriceDataTransformer()),
        ("preprocessing", preprocessor),
    ])


def build_model_pipeline(estimator):
    """Build a complete raw-input preprocessing plus estimator pipeline."""
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
    ])
    preprocessor = ColumnTransformer([
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ("numeric", numeric_pipeline, MODEL_NUMERIC_FEATURES),
    ])
    return Pipeline([
        ("feature_engineering", ApplicationFeatureTransformer()),
        ("preprocessing", preprocessor),
        ("regressor", estimator),
    ])


def prepare_training_data(path=None):
    """Return cleaned inputs, target, and a fitted preprocessing-only pipeline."""
    data = load_dataset(path)
    X = data[INPUT_COLUMNS].copy()
    y = data[TARGET_COLUMN].copy()
    pipeline = build_preprocessing_pipeline()
    transformed = pipeline.fit_transform(X, y)
    return X, y, pipeline, transformed


if __name__ == "__main__":
    X, y, pipeline, transformed = prepare_training_data()
    print(f"Dataset path: {resolve_dataset_path()}")
    print(f"Rows prepared: {len(X)}")
    print(f"Target: {TARGET_COLUMN}")
    print(f"Transformed data shape: {transformed.shape}")
    print("No model was trained or saved.")
