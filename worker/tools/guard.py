"""Allow-list for URLs: the worker may only touch the configured company systems.
This blocks both accidents and prompt-injection attempts to send data elsewhere."""
from .. import config
from ..errors import ToolInputError


def check_url(url):
    allowed = (config.VENDOR_URL, config.FINANCEDESK_URL)
    u = str(url)
    if not any(u == a or u.startswith(a + '/') or u.startswith(a + '?') for a in allowed):
        raise ToolInputError(f'URL not allowed: {u}', 'blocked_url')
