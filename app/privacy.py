import re
import pandas as pd

# Patterns are matched against a whole cell value (fullmatch), so a 10-digit phone
# number is not confused with part of a 12-digit Aadhaar number.
PATTERNS = {
    "Aadhaar": re.compile(r"[2-9]\d{3}\s?\d{4}\s?\d{4}"),
    "PAN": re.compile(r"[A-Z]{5}\d{4}[A-Z]"),
    "Phone": re.compile(r"(?:\+91[\s-]?|0)?[6-9]\d{9}"),
    "Email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
}

# Column-name words that suggest personal data
NAME_HINTS = {
    "name", "email", "mail", "phone", "mobile", "contact", "aadhaar", "aadhar",
    "uid", "pan", "address", "dob", "birth", "passport", "ssn",
}


def privacy_audit(df, sample_size=1000, match_share=0.2):
    """Scan column names and values for personal data (PII).

    A column is flagged by value if at least `match_share` of its sampled
    values match a PII pattern. It is flagged by name if the column name
    contains a hint word such as "email" or "phone".
    """
    findings = []

    for col in df.columns:
        # Name-based check: split "Phone_No" into ["phone", "no"]
        tokens = set(re.split(r"[^a-z0-9]+", str(col).lower()))
        name_hit = sorted(tokens & NAME_HINTS)

        # Value-based check on a sample of non-empty values
        values = df[col].dropna().astype(str).str.strip()
        values = values.str.replace(r"\.0$", "", regex=True)  # CSV phone numbers often load as 123.0
        values = values.head(sample_size)

        value_hit = None
        if len(values) > 0:
            for pii_type, pattern in PATTERNS.items():
                share = values.map(lambda v: bool(pattern.fullmatch(v))).mean()
                if share >= match_share:
                    value_hit = (pii_type, float(share))
                    break

        if value_hit:
            findings.append({
                "column": col,
                "type": value_hit[0],
                "evidence": f"{value_hit[1]:.0%} of values match the {value_hit[0]} pattern",
                "severity": "high",
            })
        elif name_hit:
            findings.append({
                "column": col,
                "type": "Possible PII (column name)",
                "evidence": f"Column name contains: {', '.join(name_hit)}",
                "severity": "medium",
            })

    high = sum(f["severity"] == "high" for f in findings)
    medium = sum(f["severity"] == "medium" for f in findings)
    score = max(0, 100 - 25 * high - 10 * medium)

    return {
        "findings": findings,
        "pii_columns": [f["column"] for f in findings],
        "high_severity_count": high,
        "medium_severity_count": medium,
        "score": score,
        "pass": high == 0,
    }


