"""Load the saved collector price model and predict from raw application inputs."""

from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "collector_price_model.joblib"

# Ensure the serialized src.preprocessing transformer is importable when this file
# is run directly with ``python src/predict.py``.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def validate_prediction_inputs(material, condition, quantity, weight_kg, location):
    """Validate raw application values before they reach the saved pipeline."""
    for name, value in {
        "material": material,
        "condition": condition,
        "location": location,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    try:
        numeric_quantity = float(quantity)
        numeric_weight = float(weight_kg)
    except (TypeError, ValueError) as error:
        raise ValueError("quantity and weight_kg must be numeric.") from error

    if not np.isfinite(numeric_quantity) or numeric_quantity <= 0:
        raise ValueError("quantity must be greater than 0.")
    if not np.isfinite(numeric_weight) or numeric_weight <= 0:
        raise ValueError("weight_kg must be greater than 0.")

    return numeric_quantity, numeric_weight


def load_model(model_path=MODEL_PATH):
    """Load the complete preprocessing-plus-regressor pipeline."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Saved model not found: {path}")
    return joblib.load(path)


def predict_price(material, condition, quantity, weight_kg, location):
    """Return collector price per kilogram and total price for one input record."""
    numeric_quantity, numeric_weight = validate_prediction_inputs(
        material, condition, quantity, weight_kg, location
    )
    input_data = pd.DataFrame([{
        "material": material.strip(),
        "condition": condition.strip(),
        "quantity": numeric_quantity,
        "weight_kg": numeric_weight,
        "location": location.strip(),
    }])

    predicted_price_per_kg = float(load_model().predict(input_data)[0])
    if not np.isfinite(predicted_price_per_kg):
        raise ValueError("The model returned a non-finite prediction.")

    predicted_total_price = predicted_price_per_kg * numeric_weight
    return {
        "input": {
            "material": material.strip(),
            "condition": condition.strip(),
            "quantity": numeric_quantity,
            "weight_kg": numeric_weight,
            "location": location.strip(),
        },
        "predicted_price_per_kg": predicted_price_per_kg,
        "predicted_total_price": predicted_total_price,
    }


def main():
    print("KABADIWALA PRICE ML")
    print("Enter application inputs:")
    try:
        material = input("Material: ")
        condition = input("Condition: ")
        quantity = input("Quantity: ")
        weight_kg = input("Weight (kg): ")
        location = input("Location: ")
        result = predict_price(material, condition, quantity, weight_kg, location)
    except (ValueError, FileNotFoundError) as error:
        print(f"Prediction error: {error}")
        return

    print("\nPREDICTION")
    print(f"Predicted price/kg: {result['predicted_price_per_kg']:.2f}")
    print(f"Predicted total price: {result['predicted_total_price']:.2f}")


if __name__ == "__main__":
    main()
