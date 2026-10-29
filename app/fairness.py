from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
)
from sklearn.metrics import accuracy_score


def fairness_audit(y_true, y_pred, sensitive, threshold=0.1):
    dp = demographic_parity_difference(y_true, y_pred, sensitive_features=sensitive)
    eo = equalized_odds_difference(y_true, y_pred, sensitive_features=sensitive)
    mf = MetricFrame(
        metrics=accuracy_score,
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=sensitive,
    )
    return {
        "demographic_parity_diff": dp,
        "equalized_odds_diff": eo,
        "accuracy_by_group": mf.by_group.to_dict(),
        "pass": abs(dp) < threshold and abs(eo) < threshold,  # threshold is configurable
    }

