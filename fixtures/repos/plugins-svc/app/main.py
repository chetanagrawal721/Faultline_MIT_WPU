"""plugins-svc (Faultline fixture). Uses the shared artifact."""
import acme_plugins.registry as shared

print("loaded", shared.__name__)
