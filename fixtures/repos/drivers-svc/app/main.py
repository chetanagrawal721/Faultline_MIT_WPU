"""drivers-svc (Faultline fixture). Uses the shared artifact."""
import acme_drivers.pool as shared

print("loaded", shared.__name__)
