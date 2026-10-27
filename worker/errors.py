"""Error classes and the policy hints the agent receives. Tools never raise to the model:
the executor converts every exception into {ok: False, error_class, error, hint}."""
import httpx


class BrowserError(Exception):
    """Raised by the browser client; carries the class reported by the Puppeteer service."""
    def __init__(self, cls, msg):
        super().__init__(msg)
        self.cls = cls


class HttpError(Exception):
    def __init__(self, status, body):
        super().__init__(f'HTTP {status}: {str(body)[:300]}')
        self.status = status
        self.body = body


class ToolInputError(Exception):
    """Bad arguments (unknown criterion tool, blocked URL, missing file...)."""
    def __init__(self, msg, cls='bad_input'):
        super().__init__(msg)
        self.cls = cls


RETRYABLE = {'timeout', 'server_error', 'rate_limited'}

HINTS = {
    'timeout': 'The action timed out. Call browser_read to see the real page state before trying again.',
    'element_not_found': 'Element ids are reassigned on every snapshot. Call browser_read and use a fresh id; '
                         'match buttons by their label or type, not by an id you remember.',
    'server_error': 'The server failed (5xx) even after automatic retries. Try the other channel '
                    '(web UI instead of API, or API instead of UI), or wait and retry once.',
    'session_expired': 'Not logged in or session expired. Call get_credentials, log in again '
                       '(POST /api/login for the API, or the /login form in the browser), then repeat the request.',
    'validation_error': 'The server rejected a value. Read the message, fix the value (for example use '
                        'ISO dates YYYY-MM-DD and plain decimal amounts) and retry once.',
    'duplicate': 'The record may already exist. GET it and compare with your facts before doing anything else.',
    'rate_limited': 'Rate limited. Wait and retry.',
    'client_error': 'The request was rejected (4xx). Re-read the page or API response and adjust.',
    'service_unavailable': 'The service is unreachable. This is likely not recoverable by retrying; report it.',
    'blocked_url': 'Only the configured company systems may be accessed. Do not follow links to other sites.',
    'bad_input': 'The arguments were invalid. Fix them and try again.',
    'file_not_found': 'That file does not exist. Use the path returned by browser_download.',
    'no_plan': 'Call set_plan first (subgoals plus success criteria) before any write.',
    'ungrounded_args': 'Every value you write must come from the task text or from a fact saved with remember(), '
                       'with its source. Save the value with remember() first, or ask the user.',
    'user_denied': 'The user declined this action. Do not retry it; explain and finish as partial or blocked.',
    'loop_detected': 'You have repeated a failing action. Replan: call set_plan with a different approach.',
    'verification_failed': 'Independent verification failed. Fix the listed problems, or finish with status partial.',
}


def classify(e):
    if isinstance(e, BrowserError):
        return e.cls
    if isinstance(e, ToolInputError):
        return e.cls
    if isinstance(e, HttpError):
        c = e.status
        return {401: 'session_expired', 409: 'duplicate', 422: 'validation_error',
                429: 'rate_limited'}.get(c, 'server_error' if c >= 500 else 'client_error')
    if isinstance(e, (httpx.TimeoutException, TimeoutError)):
        return 'timeout'
    if isinstance(e, (httpx.ConnectError, ConnectionError)):
        return 'service_unavailable'
    if isinstance(e, FileNotFoundError):
        return 'file_not_found'
    if isinstance(e, TypeError):
        return 'bad_input'   # wrong or missing tool arguments
    if 'timeout' in str(e).lower():
        return 'timeout'
    return 'unknown'
