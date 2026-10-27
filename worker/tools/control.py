"""Control tools: planning, memory, asking the user, credentials, and the finish request."""
from .. import config
from ..context import CTX
from ..errors import ToolInputError
from .base import REGISTRY, json_arg, obj, tool

CRITERION = {
    'type': 'object',
    'properties': {
        'description': {'type': 'string', 'description': 'What this check proves.'},
        'tool': {'type': 'string', 'description': 'A READ-ONLY tool that proves it, e.g. http_get.'},
        'args_json': {'type': 'string', 'description': "That tool's arguments as a JSON object string, "
                      "e.g. '{\"url\": \"http://...\"}'."},
        'expect_path': {'type': 'string', 'description': 'Optional dotted path into the tool result, '
                        'e.g. body.0.amount_cents'},
        'expect_equals': {'type': 'string', 'description': 'Optional exact expected value, written as a string.'},
    },
    'required': ['description', 'tool', 'args_json'],
}


@tool('set_plan', 'Record or replace your plan: 2-6 subgoals plus success criteria, each a read-only check '
      'against the real system. Call this FIRST; call again to replan.',
      obj({'subgoals': {'type': 'array', 'items': {'type': 'string'}},
           'criteria': {'type': 'array', 'items': CRITERION}}))
def set_plan(subgoals, criteria):
    parsed = []
    for c in criteria:
        name = c.get('tool')
        t = REGISTRY.get(name)
        if t is None:
            raise ToolInputError(f'criterion uses unknown tool: {name}')
        args = json_arg(c.get('args_json', c.get('args')), 'args_json')
        if t.risk_for(args) != 'read':
            raise ToolInputError(f'criterion checks must be read-only; {name} with these args is not')
        item = {'description': c.get('description', ''), 'check': {'tool': name, 'args': args}}
        if c.get('expect_equals') not in (None, ''):
            item['expect'] = {'path': c.get('expect_path', ''), 'equals': c['expect_equals']}
        parsed.append(item)
    CTX.memory.plan = list(subgoals)
    CTX.memory.criteria = parsed
    return {'plan_saved': True, 'subgoals': len(subgoals), 'criteria': len(parsed)}


@tool('remember', 'Save a fact you will need later, with where it came from and your confidence (0-1). '
      'Use confidence below 0.8 for OCR output or when sources conflict.',
      obj({'key': {'type': 'string'}, 'value': {'type': 'string'}, 'source': {'type': 'string'},
           'confidence': {'type': 'number'}}, required=['key', 'value', 'source']))
def remember(key, value, source, confidence=0.9):
    CTX.memory.remember(key, value, source, confidence)
    return {'saved': key}


@tool('ask_user', 'Ask the user a question and wait. Use when several candidates match, values conflict, '
      'confidence is low, or you are not allowed to proceed safely.',
      obj({'question': {'type': 'string'}, 'options': {'type': 'array', 'items': {'type': 'string'}}},
          required=['question']))
def ask_user(question, options=None):
    return {'answer': CTX.ask(question, options)}


@tool('get_credentials', 'Get the login for a company system: vendor_portal or financedesk.',
      obj({'system': {'type': 'string', 'enum': ['vendor_portal', 'financedesk']}}))
def get_credentials(system):
    if system not in config.CREDENTIALS:
        raise ToolInputError(f'unknown system: {system}')
    user, pw = config.CREDENTIALS[system]
    CTX.memory.remember(f'{system}_username', user, 'get_credentials', 1.0)
    CTX.memory.remember(f'{system}_password', pw, 'get_credentials', 1.0, secret=True)
    return {'username': user, 'password': pw}


@tool('finish', "Declare the task finished. Your claim is independently verified against the real system. "
      "status: done, partial (some of it achieved) or blocked (could not proceed).",
      obj({'status': {'type': 'string', 'enum': ['done', 'partial', 'blocked']}, 'summary': {'type': 'string'}}))
def finish(status, summary):   # intercepted by the agent loop; never executed directly
    raise RuntimeError('finish is handled by the agent loop')
