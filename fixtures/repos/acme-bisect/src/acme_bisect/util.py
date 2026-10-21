"""Uses six small packages at import time; none of their version changes in this fixture affects it."""
import certifi
import charset_normalizer
import idna
import packaging.version
import pyparsing

NAMES = (certifi.__name__, charset_normalizer.__name__, idna.__name__, packaging.version.__name__, pyparsing.__name__)
