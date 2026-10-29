from pathlib import Path

import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from compliance import compliance_audit
from explain import explain_audit
from fairness import fairness_audit
from privacy import privacy_audit
from robustness import robustness_audit
from report import build_report

st.set_page_config(page_title="AutoAudit-360", layout="wide")

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "adult_sample.csv"
MAX_ROWS = 20000       # keeps the free hosting tier fast
MAX_CATEGORIES = 50    # text columns with more distinct values are skipped


@st.cache_data
def load_sample():
    return pd.read_csv(SAMPLE_PATH)


def run_audit(df, target, sensitive, positive, fairness_threshold, max_drop):
    data = df.dropna().reset_index(drop=True)
    if len(data) < 100:
        raise ValueError("Fewer than 100 complete rows remain after removing missing values.")

    y = (data[target].astype(str) == positive).astype(int)

    # Skip ID-like text columns (names, IDs): one-hot encoding them would explode the data
    features = data.drop(columns=[target])
    text_cols = features.select_dtypes(exclude="number").columns
    dropped = [c for c in text_cols if features[c].nunique() > MAX_CATEGORIES]
    features = features.drop(columns=dropped)
    X = pd.get_dummies(features, dtype=float).astype(float)

    # Groups for the fairness audit; bin numeric attributes such as age into quartiles
    groups = data[sensitive]
    if pd.api.types.is_numeric_dtype(groups) and groups.nunique() > 10:
        groups = pd.qcut(groups, 4, duplicates="drop")
    groups = groups.astype(str)

    X_train, X_test, y_train, y_test, g_train, g_test = train_test_split(
        X, y, groups, test_size=0.3, random_state=0, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=60, max_depth=10, random_state=0, n_jobs=-1
    ).fit(X_train, y_train)
    pred = model.predict(X_test)

    fair = fairness_audit(y_test.to_numpy(), pred, g_test.to_numpy(), threshold=fairness_threshold)
    expl = explain_audit(model, X_train, X_test, sensitive_col=sensitive, max_samples=100)
    rob = robustness_audit(model, X_test, y_test, max_drop=max_drop)
    priv = privacy_audit(df)  # scan the original data, before encoding
    comp = compliance_audit(fair, expl, rob, priv)

    return {
        "accuracy": float(accuracy_score(y_test, pred)),
        "n_rows": len(data),
        "dropped": dropped,
        "fairness": fair,
        "explain": expl,
        "robustness": rob,
        "privacy": priv,
        "compliance": comp,
    }


# ---------------------------------------------------------------- page
st.title("AutoAudit-360")
st.caption("End-to-End Trustworthy AI Audit & Regulatory Compliance Suite")

with st.sidebar:
    st.header("Settings")
    source = st.radio("Data source", ["Sample: UCI Adult", "Upload CSV"])
    fairness_threshold = st.slider("Fairness gap threshold", 0.01, 0.30, 0.10, 0.01)
    max_drop = st.slider("Max accuracy drop under noise", 0.01, 0.20, 0.05, 0.01)
    st.caption("Thresholds are adjustable defaults, not legal standards.")

df = None
if source == "Sample: UCI Adult":
    if SAMPLE_PATH.exists():
        df = load_sample()
    else:
        st.warning("Sample data not found. Run `python make_sample_data.py` first.")
else:
    uploaded = st.file_uploader("Upload a CSV file", type="csv")
    if uploaded is not None:
        df = pd.read_csv(uploaded)

if df is None:
    st.info("Choose a data source to begin.")
    st.stop()

if len(df) > MAX_ROWS:
    df = df.sample(MAX_ROWS, random_state=0).reset_index(drop=True)
    st.caption(f"Large file: using a random sample of {MAX_ROWS:,} rows.")

with st.expander("Preview data"):
    st.dataframe(df.head(20))

cols = list(df.columns)
default_target = "class" if "class" in cols else cols[-1]
c1, c2, c3 = st.columns(3)
target = c1.selectbox("Target column (what the model predicts)", cols, index=cols.index(default_target))

sens_options = [c for c in cols if c != target]
default_sens = "sex" if "sex" in sens_options else sens_options[0]
sensitive = c2.selectbox("Sensitive attribute", sens_options, index=sens_options.index(default_sens))

labels = sorted(df[target].dropna().astype(str).unique())
if len(labels) != 2:
    st.error(f"The target column must have exactly 2 values. '{target}' has {len(labels)}.")
    st.stop()
positive = c3.selectbox("Favourable outcome", labels, index=1)

if st.button("Run Audit", type="primary"):
    try:
        with st.spinner("Running audit... explainability can take up to a minute."):
            st.session_state["results"] = run_audit(
                df, target, sensitive, positive, fairness_threshold, max_drop
            )
            st.session_state["settings"] = {
                "dataset": "UCI Adult sample" if source == "Sample: UCI Adult" else "Uploaded CSV",
                "target": target,
                "sensitive": sensitive,
                "positive": positive,
                "fairness_threshold": fairness_threshold,
                "max_drop": max_drop,
            }
    except Exception as e:
        st.session_state.pop("results", None)
        st.error(f"Audit failed: {e}")

res = st.session_state.get("results")
if res:
    comp = res["compliance"]
    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trust Score", f"{comp['trust_score']}/100")
    m2.metric("Rating", comp["rating"])
    m3.metric("Checks passed", f"{comp['passed']}/{comp['assessed']}")
    m4.metric("Model accuracy", f"{res['accuracy']:.1%}")
    st.caption(comp["disclaimer"])
    try:
        pdf_bytes = build_report(res, st.session_state.get("settings", {}))
        st.download_button("Download PDF report", data=pdf_bytes,
                           file_name="autoaudit360_report.pdf", mime="application/pdf")
    except Exception as e:
        st.warning(f"Could not build the PDF: {e}")
    if res["dropped"]:
        st.caption("Skipped from the model (too many distinct values): " + ", ".join(res["dropped"]))

    t_fair, t_exp, t_rob, t_priv, t_comp = st.tabs(
        ["Fairness", "Explainability", "Robustness", "Privacy", "Compliance"]
    )

    with t_fair:
        f = res["fairness"]
        a, b = st.columns(2)
        a.metric("Demographic parity difference", f"{abs(f['demographic_parity_diff']):.3f}")
        b.metric("Equalized odds difference", f"{abs(f['equalized_odds_diff']):.3f}")
        st.write("Result:", "✅ Pass" if f["pass"] else "❌ Fail")
        st.caption("Both gaps must stay under the threshold in the sidebar. "
                   "0 means all groups are treated identically.")
        st.subheader("Accuracy by group")
        st.bar_chart(pd.Series(f["accuracy_by_group"], name="Accuracy"))

    with t_exp:
        e = res["explain"]
        st.metric("Explainability score", e["score"])
        st.write("Sensitive attribute in top 3 drivers:", "⚠️ Yes" if e["sensitive_in_top3"] else "✅ No")
        st.pyplot(e["figure"])

    with t_rob:
        r = res["robustness"]
        st.metric("Robustness score", r["score"])
        st.write("Result:", "✅ Pass" if r["pass"] else "❌ Fail")
        st.pyplot(r["figure"])
        st.dataframe(pd.DataFrame({
            "Noise level": list(r["noisy_accuracy"].keys()),
            "Accuracy": list(r["noisy_accuracy"].values()),
            "Accuracy drop": list(r["accuracy_drop"].values()),
        }), hide_index=True)

    with t_priv:
        p = res["privacy"]
        st.metric("Privacy score", p["score"])
        if p["findings"]:
            st.dataframe(pd.DataFrame(p["findings"]), hide_index=True)
        else:
            st.success("No personal-data columns detected.")
        st.caption("Pattern-based screening only. It cannot detect names or free-text addresses by value.")

    with t_comp:
        icons = {"Pass": "✅ Pass", "Fail": "❌ Fail", "Not assessed": "⚪ Not assessed"}
        st.dataframe(pd.DataFrame([{
            "Status": icons[c["status"]],
            "Requirement": c["requirement"],
            "Evidence": c["evidence"] or "-",
            "Regulations": "; ".join(c["regulations"]),
        } for c in comp["checklist"]]), hide_index=True)
        st.subheader("Module scores")
        st.bar_chart(pd.Series(comp["module_scores"], name="Score"))