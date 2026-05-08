"""
Entry point for locust UI mode (make load-test-ui).

Imports all user classes so they appear in the web interface for
manual selection. For headless runs per scenario use the dedicated
scenario_N_*.py files directly via -f flag.
"""

from scenario_1_policy_creation import PolicyCreationUser  # noqa: F401
from scenario_2_claims_filing import ClaimsFilingUser  # noqa: F401
from scenario_3_audit_read import AuditReadUser  # noqa: F401
from scenario_4_spike import SpikeUser  # noqa: F401
from scenario_5_stress import StressUser  # noqa: F401
