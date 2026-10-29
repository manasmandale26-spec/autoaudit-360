# Compliance readiness screen: maps audit results to checklist items.
# Regulation references are general (no article numbers). Verify wording against
# the official texts before citing anything in your report.

WEIGHTS = {"fairness": 0.30, "explain": 0.20, "robustness": 0.25, "privacy": 0.25}


def _item(requirement, regulations, status, evidence):
    return {
        "requirement": requirement,
        "regulations": regulations,
        "status": status,  # "Pass", "Fail", or "Not assessed"
        "evidence": evidence,
    }


def _status(result, passed):
    if result is None:
        return "Not assessed"
    return "Pass" if passed(result) else "Fail"


def compliance_audit(fairness=None, explain=None, robustness=None, privacy=None):
    """Turn module results (dicts from the other audit functions) into a checklist
    and an overall Trust Score. Any module can be None if it was not run."""
    checklist = []

    # --- Fairness ---
    checklist.append(_item(
        "Bias testing performed and group disparities within threshold",
        ["EU AI Act (data governance / bias examination)",
         "NIST AI RMF (Measure: fairness and bias)",
         "ISO/IEC 42001 (AI risk assessment)"],
        _status(fairness, lambda r: r["pass"]),
        None if fairness is None else
        f"Demographic parity diff {abs(fairness['demographic_parity_diff']):.3f}, "
        f"equalized odds diff {abs(fairness['equalized_odds_diff']):.3f}",
    ))

    # --- Explainability ---
    checklist.append(_item(
        "Model decisions can be explained at the feature level",
        ["EU AI Act (transparency obligations)",
         "NIST AI RMF (Measure: explainable and interpretable)",
         "ISO/IEC 42001 (transparency)"],
        _status(explain, lambda r: len(r["top_features"]) > 0),
        None if explain is None else
        "Top drivers: " + ", ".join(explain["top_features"][:3]),
    ))
    checklist.append(_item(
        "Sensitive attribute is not a dominant driver of predictions",
        ["EU AI Act (non-discrimination)",
         "NIST AI RMF (Measure: fairness and bias)"],
        _status(explain, lambda r: not r["sensitive_in_top3"]),
        None if explain is None else
        ("Sensitive attribute ranks in the top 3 drivers" if explain["sensitive_in_top3"]
         else "Sensitive attribute is not in the top 3 drivers"),
    ))

    # --- Robustness ---
    checklist.append(_item(
        "Model performance is stable under noisy inputs",
        ["EU AI Act (accuracy, robustness and cybersecurity)",
         "NIST AI RMF (Measure: valid, reliable and secure)",
         "ISO/IEC 42001 (AI system performance monitoring)"],
        _status(robustness, lambda r: r["pass"]),
        None if robustness is None else
        f"Baseline accuracy {robustness['baseline_accuracy']:.3f}, robustness score {robustness['score']}",
    ))

    # --- Privacy ---
    checklist.append(_item(
        "No direct personal identifiers (Aadhaar, PAN, phone, email) found in data",
        ["India DPDP Act 2023 (personal data protection, data minimisation)",
         "EU AI Act (data governance)",
         "ISO/IEC 42001 (data management)"],
        _status(privacy, lambda r: r["pass"]),
        None if privacy is None else
        (f"{privacy['high_severity_count']} high-severity PII column(s): "
         + ", ".join(privacy["pii_columns"]) if privacy["pii_columns"] else "No PII columns detected"),
    ))
    checklist.append(_item(
        "Possible personal-data columns reviewed (names, addresses, etc.)",
        ["India DPDP Act 2023 (purpose limitation, data minimisation)"],
        _status(privacy, lambda r: r["medium_severity_count"] == 0),
        None if privacy is None else
        f"{privacy['medium_severity_count']} column(s) flagged by name only",
    ))

    # --- Governance items that code can't verify: always "Not assessed" ---
    checklist.append(_item(
        "Human oversight process documented",
        ["EU AI Act (human oversight)", "NIST AI RMF (Govern)"],
        "Not assessed",
        "Needs a manual check: cannot be verified from data or model alone",
    ))
    checklist.append(_item(
        "Technical documentation and audit logs maintained",
        ["EU AI Act (technical documentation, record keeping)",
         "ISO/IEC 42001 (documented information)"],
        "Not assessed",
        "Needs a manual check: attach the generated PDF report to your records",
    ))

    # --- Trust Score: weighted average of the modules that were run ---
    scores = {
        "fairness": _fairness_score(fairness),
        "explain": None if explain is None else explain["score"],
        "robustness": None if robustness is None else robustness["score"],
        "privacy": None if privacy is None else privacy["score"],
    }
    used = {k: v for k, v in scores.items() if v is not None}
    total_weight = sum(WEIGHTS[k] for k in used)
    trust_score = (
        int(round(sum(WEIGHTS[k] * v for k, v in used.items()) / total_weight))
        if total_weight > 0 else None
    )

    assessed = [c for c in checklist if c["status"] != "Not assessed"]
    passed = sum(c["status"] == "Pass" for c in assessed)

    return {
        "checklist": checklist,
        "module_scores": scores,
        "trust_score": trust_score,
        "rating": _rating(trust_score),
        "passed": passed,
        "assessed": len(assessed),
        "not_assessed": len(checklist) - len(assessed),
        "disclaimer": "Compliance readiness screen only. This is not a legal "
                      "opinion or a certification of compliance.",
    }


def _fairness_score(fairness):
    """Turn fairness gaps into 0-100: 100 means no gap, 0 means a gap of 0.5 or more."""
    if fairness is None:
        return None
    worst_gap = max(abs(fairness["demographic_parity_diff"]),
                    abs(fairness["equalized_odds_diff"]))
    return int(round(100 * max(0.0, 1 - worst_gap / 0.5)))


def _rating(score):
    if score is None:
        return "Not available"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Needs attention"
    return "High risk"


