import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
import matplotlib

matplotlib.use("Agg")  # lets matplotlib draw charts without opening a window
import matplotlib.pyplot as plt


def robustness_audit(model, X_test, y_test,
                     noise_levels=(0.05, 0.1, 0.25, 0.5),
                     repeats=5, max_drop=0.05, seed=0):
    """Add Gaussian noise to the test features and measure the accuracy drop.

    noise_levels are fractions of each column's standard deviation,
    so 0.1 means "noise about 10% as large as the feature's natural spread".
    """
    rng = np.random.default_rng(seed)
    X_test = X_test.reset_index(drop=True)
    y_test = np.asarray(y_test)
    numeric_cols = X_test.select_dtypes(include="number").columns

    baseline = accuracy_score(y_test, model.predict(X_test))

    results = []
    for level in noise_levels:
        accs = []
        for _ in range(repeats):  # repeat because noise is random
            X_noisy = X_test.copy()
            for col in numeric_cols:
                std = X_test[col].std()
                X_noisy[col] = X_test[col] + rng.normal(0, level * std, len(X_test))
            accs.append(accuracy_score(y_test, model.predict(X_noisy)))
        results.append(float(np.mean(accs)))

    drops = [baseline - a for a in results]

    # Score: average share of baseline accuracy kept across all noise levels
    retention = [a / baseline if baseline > 0 else 0 for a in results]
    score = int(round(100 * float(np.clip(np.mean(retention), 0, 1))))

    # Pass if the accuracy drop at the 0.1 noise level stays small
    check_idx = list(noise_levels).index(0.1) if 0.1 in noise_levels else 0
    passed = bool(drops[check_idx] < max_drop)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([0] + list(noise_levels), [baseline] + results,
            marker="o", color="#4f46e5")
    ax.set_xlabel("Noise level (fraction of feature std)")
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy under noise")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    return {
        "baseline_accuracy": float(baseline),
        "noisy_accuracy": dict(zip(noise_levels, results)),
        "accuracy_drop": dict(zip(noise_levels, [float(d) for d in drops])),
        "score": score,
        "pass": passed,
        "figure": fig,
    }


