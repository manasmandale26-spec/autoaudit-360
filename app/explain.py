import numpy as np
import pandas as pd
import shap
import matplotlib

matplotlib.use("Agg")  # lets matplotlib draw charts without opening a window
import matplotlib.pyplot as plt


def explain_audit(model, X_train, X_test, sensitive_col=None,
                  max_samples=200, top_n=10):
    """Explain which features drive the model's predictions using SHAP."""
    background = shap.sample(X_train, 100, random_state=0)
    X_eval = X_test.iloc[:max_samples]

    explainer = shap.Explainer(model, background)
    sv = explainer(X_eval)
    values = sv.values

    # Classifiers can return one set of values per class: (rows, features, classes).
    # Keep only the positive class so we have (rows, features).
    if values.ndim == 3:
        values = values[:, :, 1]

    importance = (
        pd.Series(np.abs(values).mean(axis=0), index=X_eval.columns)
        .sort_values(ascending=False)
    )

    # Does the sensitive attribute rank among the top 3 drivers?
    sensitive_in_top3 = bool(
        sensitive_col is not None and sensitive_col in importance.index[:3]
    )

    # Simple heuristic score: lower if a sensitive feature dominates
    score = 60 if sensitive_in_top3 else 100

    # Bar chart of the top features (works with st.pyplot in Streamlit)
    top = importance.head(top_n)[::-1]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(top.index, top.values, color="#4f46e5")
    ax.set_xlabel("Mean |SHAP value| (average impact on prediction)")
    ax.set_title("Top feature importance")
    fig.tight_layout()

    return {
        "feature_importance": {k: float(v) for k, v in importance.items()},
        "top_features": list(importance.index[:top_n]),
        "sensitive_in_top3": sensitive_in_top3,
        "score": score,
        "figure": fig,
    }


