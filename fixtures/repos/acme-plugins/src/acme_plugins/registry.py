"""Plugin registry (Faultline fixture, Information severity). It looks plugins up on pydantic by name at run time, so no static reading can say which"""
import pydantic


def load(name):
    """Look a plugin up by name on pydantic at run time."""
    return getattr(pydantic, name)()
