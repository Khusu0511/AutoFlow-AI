"""LLM access.

GeminiLLM  - Google Gemini via the google-genai SDK (function calling, manual loop).
ScriptedLLM - deterministic stand-in used by unit tests and the offline demo (--mock).

The agent loop only needs .create(system, tools, messages) -> Resp and .judge(payload) -> dict, so a
different provider is a one-class change. Messages use a neutral format:
  {'role': 'user', 'content': str | [tool_result dicts]}
  {'role': 'assistant', 'content': [Block], 'raw': provider-native content (kept verbatim)}
"""
import json
import re
import time
import uuid
from dataclasses import dataclass, field

from . import config
from .prompts import JUDGE


@dataclass
class Block:
    type: str
    text: str = None
    id: str = None
    name: str = None
    input: dict = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Resp:
    content: list
    usage: Usage = field(default_factory=Usage)
    raw: object = None


class GeminiLLM:
    RETRY_CODES = (429, 500, 502, 503, 504)

    def __init__(self, model=None, api_key=None, client=None):
        from google import genai
        from google.genai import types
        self.types = types
        key = api_key or config.GEMINI_API_KEY
        if client is None and not key:
            raise RuntimeError('GEMINI_API_KEY is not set')
        self.client = client or genai.Client(api_key=key)
        self.model = model or config.MODEL
        self.retry_base = 2.0

    # -- request conversion ---------------------------------------------------
    def declarations(self, tools):
        """Neutral tool specs -> Gemini function declarations (JSON-schema parameters)."""
        t = self.types
        decls = []
        for spec in tools:
            kw = {'name': spec['name'], 'description': spec['description']}
            if spec['input_schema'].get('properties'):
                kw['parameters_json_schema'] = spec['input_schema']
            decls.append(t.FunctionDeclaration(**kw))
        return [t.Tool(function_declarations=decls)]

    def contents(self, messages):
        t = self.types
        out = []
        for m in messages:
            if m['role'] == 'assistant':
                if m.get('raw') is not None:      # replay verbatim: keeps Gemini 3 thought signatures
                    out.append(m['raw'])
                    continue
                parts = []
                for b in m['content']:
                    if b.type == 'text' and b.text:
                        parts.append(t.Part(text=b.text))
                    elif b.type == 'tool_use':
                        parts.append(t.Part(function_call=t.FunctionCall(name=b.name, args=b.input or {})))
                out.append(t.Content(role='model', parts=parts or [t.Part(text='(no output)')]))
            elif isinstance(m['content'], str):
                out.append(t.Content(role='user', parts=[t.Part(text=m['content'])]))
            else:
                parts = []
                for b in m['content']:
                    if b.get('type') == 'tool_result':
                        try:
                            payload = json.loads(b['content'])
                        except ValueError:
                            payload = {'raw': str(b['content'])}
                        parts.append(t.Part(function_response=t.FunctionResponse(
                            name=b.get('name', ''), response={'result': payload})))
                    else:
                        parts.append(t.Part(text=str(b.get('text', b))))
                out.append(t.Content(role='user', parts=parts))
        return out

    # -- calls ------------------------------------------------------------------
    def _retry(self, fn):
        from google.genai import errors
        delay = self.retry_base
        for attempt in range(5):
            try:
                return fn()
            except errors.APIError as e:
                if getattr(e, 'code', None) in self.RETRY_CODES and attempt < 4:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise

    def create(self, system, tools, messages):
        t = self.types
        cfg = t.GenerateContentConfig(
            system_instruction=system,
            tools=self.declarations(tools),
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
            tool_config=t.ToolConfig(function_calling_config=t.FunctionCallingConfig(mode='AUTO')),
            max_output_tokens=8192,
        )
        contents = self.contents(messages)
        resp = self._retry(lambda: self.client.models.generate_content(
            model=self.model, contents=contents, config=cfg))
        return self.parse(resp)

    def parse(self, resp):
        cand = resp.candidates[0] if getattr(resp, 'candidates', None) else None
        content = cand.content if cand is not None else None
        parts = list(content.parts) if content is not None and content.parts else []
        blocks = []
        for p in parts:
            fc = getattr(p, 'function_call', None)
            if fc:
                blocks.append(Block('tool_use', id=getattr(fc, 'id', None) or f'call_{uuid.uuid4().hex[:8]}',
                                    name=fc.name, input=dict(fc.args or {})))
            elif getattr(p, 'text', None) and not getattr(p, 'thought', False):
                blocks.append(Block('text', text=p.text))
        if not blocks:
            reason = getattr(cand, 'finish_reason', None) if cand is not None else 'no candidates'
            blocks = [Block('text', text=f'(empty model response: {reason})')]
        um = getattr(resp, 'usage_metadata', None)
        usage = Usage(
            input_tokens=(getattr(um, 'prompt_token_count', 0) or 0) if um else 0,
            output_tokens=((getattr(um, 'candidates_token_count', 0) or 0) +
                           (getattr(um, 'thoughts_token_count', 0) or 0)) if um else 0)
        return Resp(blocks, usage, raw=content if parts else None)

    def judge(self, payload):
        t = self.types
        cfg = t.GenerateContentConfig(system_instruction=JUDGE, response_mime_type='application/json',
                                      max_output_tokens=2048)
        r = self._retry(lambda: self.client.models.generate_content(
            model=self.model, contents=json.dumps(payload, default=str), config=cfg))
        m = re.search(r'\{.*\}', r.text or '', re.S)
        return json.loads(m.group(0))


class ScriptedLLM:
    """`policy` is a generator function. It yields one (name, input) tool call, or a list of them, and
    receives the list of parsed tool results via send(). When it returns, the model 'stops calling tools'."""

    def __init__(self, policy, judge_result=None):
        self.gen = policy()
        self.started = False
        self.n = 0
        self.judge_result = judge_result or {'pass': True, 'failures': []}

    def create(self, system, tools, messages):
        results = None
        last = messages[-1]
        if last['role'] == 'user' and isinstance(last['content'], list):
            results = [json.loads(b['content']) for b in last['content'] if b.get('type') == 'tool_result']
        try:
            calls = self.gen.send(results) if self.started else next(self.gen)
            self.started = True
        except StopIteration:
            return Resp([Block('text', text='(scripted policy ended)')])
        if isinstance(calls, tuple):
            calls = [calls]
        blocks = []
        for name, inp in calls:
            self.n += 1
            blocks.append(Block('tool_use', id=f'call_scripted_{self.n}', name=name, input=inp))
        return Resp(blocks)

    def judge(self, payload):
        return self.judge_result
