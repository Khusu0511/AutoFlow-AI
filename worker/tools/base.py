"""Tool registry. Adding a capability = one decorated function; the agent loop never changes."""
import json
from dataclasses import dataclass, field
from typing import Callable, Union

from ..errors import ToolInputError

RISKS = ('read', 'write', 'irreversible')


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable
    risk: Union[str, Callable] = 'read'            # str, or fn(args) -> str for dynamic risk
    idempotent: Union[bool, Callable] = True       # safe to auto-retry? bool or fn(args) -> bool
    ground: Callable = None                        # fn(args) -> list of values that must be traceable to facts

    def risk_for(self, args):
        return self.risk(args) if callable(self.risk) else self.risk

    def is_idempotent(self, args):
        return self.idempotent(args) if callable(self.idempotent) else self.idempotent

    def values_to_ground(self, args):
        return self.ground(args) if self.ground else []

    def coerce(self, args):
        """Gemini returns every number as a float (element id 7 arrives as 7.0). Coerce arguments the schema
        declares as integer back to int so ids compare and serialize correctly."""
        props = (self.schema or {}).get('properties', {})
        out = dict(args or {})
        for k, v in out.items():
            if props.get(k, {}).get('type') == 'integer':
                if isinstance(v, float) and v.is_integer():
                    out[k] = int(v)
                elif isinstance(v, str) and v.strip().lstrip('-').isdigit():
                    out[k] = int(v)
        return out


REGISTRY: dict = {}


def tool(name, description, schema, risk='read', idempotent=True, ground=None):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, schema, fn, risk, idempotent, ground)
        return fn
    return deco


def specs():
    return [{'name': t.name, 'description': t.description, 'input_schema': t.schema}
            for t in REGISTRY.values()]


def obj(props, required=None):
    return {'type': 'object', 'properties': props, 'required': required if required is not None else list(props)}


def json_arg(v, what='argument'):
    """Gemini function schemas cannot describe free-form objects, so object arguments arrive as JSON strings."""
    if isinstance(v, (dict, list)):
        return v
    if v is None or v == '':
        return {}
    try:
        return json.loads(v)
    except ValueError as e:
        raise ToolInputError(f'{what} must be valid JSON: {e}')
