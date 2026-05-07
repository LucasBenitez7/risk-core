from prometheus_client import Counter

claims_filed_total = Counter(
    "riskcore_claims_filed_total",
    "Total claims filed",
    ["incident_type"],
)

claims_status_changed_total = Counter(
    "riskcore_claims_status_changed_total",
    "Total claim status transitions",
    ["from_status", "to_status"],
)
