"""Compatibility wrapper for the provisioning agent.

The main branch defines a single module at src/agents/provisioning_agent.py,
while the aluminium branch uses the package layout under
src/agents/provisioning_agent/. This shim keeps both import styles working.
"""

from src.agents.provisioning_agent.agent import (
    ProvisioningOutput,
    ProvisioningRequest,
    run,
    run_with_web_price,
)

__all__ = [
    "ProvisioningOutput",
    "ProvisioningRequest",
    "run",
    "run_with_web_price",
]
