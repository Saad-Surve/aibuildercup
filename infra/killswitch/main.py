import base64
import json
import logging
import os

import functions_framework
import google.auth
from googleapiclient import discovery

PROJECT_ID = os.environ["PROJECT_ID"]
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("budget-killswitch")


def _disable_billing():
    credentials, _ = google.auth.default()
    service = discovery.build(
        "cloudbilling", "v1", credentials=credentials, cache_discovery=False
    )
    name = f"projects/{PROJECT_ID}"
    body = {"billingAccountName": ""}
    service.projects().updateBillingInfo(name=name, body=body).execute()


@functions_framework.cloud_event
def disable_billing_on_budget(cloud_event):
    raw = (cloud_event.data or {}).get("message", {}).get("data", "")
    if not raw:
        log.warning("empty budget message")
        return

    payload = json.loads(base64.b64decode(raw).decode("utf-8"))
    cost = float(payload.get("costAmount", 0) or 0)
    budget = float(payload.get("budgetAmount", 0) or 0)
    log.info("budget update cost=%s budget=%s", cost, budget)

    if budget <= 0 or cost < budget:
        log.info("under budget, nothing to do")
        return

    if DRY_RUN:
        log.warning("DRY_RUN: would disable billing for project %s", PROJECT_ID)
        return

    log.error("budget exceeded, disabling billing for project %s", PROJECT_ID)
    _disable_billing()
    log.error("billing disabled for project %s", PROJECT_ID)
