"""Disabled optional routes do not import unstable SDKs or touch application startup."""

import os


def samsung_status():
    if os.getenv("SAMSUNG_SYNC_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    return {
        "status": "not_implemented",
        "detail": "Requires encrypted token/cache adaptation and verified metric units before activation.",
    }


def open_wearables_status():
    return {
        "status": "deferred",
        "detail": "Only build a separately version-pinned mobile companion if the Health Connect bridge is insufficient.",
    }
