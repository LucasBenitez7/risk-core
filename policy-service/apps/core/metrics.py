from prometheus_client import Counter

policies_created_total = Counter(
    "riskcore_policies_created_total",
    "Total policies created",
    ["policy_type"],
)

policies_cancelled_total = Counter(
    "riskcore_policies_cancelled_total",
    "Total policies cancelled",
)
