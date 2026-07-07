from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance. Lives here (not main.py) so route modules can
# import it without a circular import; main.py attaches it to app.state.
limiter = Limiter(key_func=get_remote_address)
