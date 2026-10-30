"""Deployment repair entry point. Inspect the deployment before changing it."""
from platform_runtime import restart_worker


def repair(root):
    # The initial operational response was a restart; the incident remains open.
    restart_worker(root)
