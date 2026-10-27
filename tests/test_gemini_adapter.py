"""Offline tests of the Gemini adapter using a fake client and real google-genai types."""
import json

import pytest
from google.genai import errors, types

from worker.llm import Block, GeminiLLM
from worker.tools import REGISTRY, specs


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({'model': model, 'contents': contents, 'config': config})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def response(parts, usage=(10, 5, 7)):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role='model', parts=parts))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=usage[0], candidates_token_count=usage[1], thoughts_token_count=usage[2]))


def fc(name, **args):
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def llm(responses):
    g = GeminiLLM(api_key='test', client=FakeClient(responses))
    g.retry_base = 0
    return g


def test_every_registered_tool_converts_to_a_valid_declaration():
    decls = llm([]).declarations(specs())[0].function_declarations
    assert {d.name for d in decls} == set(REGISTRY)
    by_name = {d.name: d for d in decls}
    assert by_name['browser_read'].parameters_json_schema is None          # no-arg tool: no parameters object
    assert by_name['http_post'].parameters_json_schema['properties']['body']['type'] == 'string'
    # no free-form nested objects anywhere (Gemini schemas cannot express them)
    def walk(s):
        if isinstance(s, dict):
            assert not (s.get('type') == 'object' and not s.get('properties') and 'properties' in s)
            for v in s.values():
                walk(v)
        elif isinstance(s, list):
            for v in s:
                walk(v)
    for d in decls:
        walk(d.parameters_json_schema)


def test_parse_function_calls_text_and_usage():
    g = llm([response([types.Part(text='thinking...', thought=True), types.Part(text='Plan: go'),
                       fc('browser_goto', url='http://localhost:8001/login'), fc('browser_read')])])
    r = g.create('sys', specs(), [{'role': 'user', 'content': 'goal'}])
    kinds = [(b.type, b.name or b.text) for b in r.content]
    assert kinds == [('text', 'Plan: go'), ('tool_use', 'browser_goto'), ('tool_use', 'browser_read')]
    assert r.content[1].input == {'url': 'http://localhost:8001/login'}
    assert r.usage.input_tokens == 10 and r.usage.output_tokens == 12     # candidates + thinking tokens
    assert r.raw is not None


def test_request_config_disables_automatic_function_calling():
    g = llm([response([fc('browser_read')])])
    g.create('SYSTEM TEXT', specs(), [{'role': 'user', 'content': 'goal'}])
    call = g.client.models.calls[0]
    assert call['model'] == g.model
    assert call['config'].system_instruction == 'SYSTEM TEXT'
    assert call['config'].automatic_function_calling.disable is True
    assert call['contents'][0].role == 'user' and call['contents'][0].parts[0].text == 'goal'


def test_history_round_trip_replays_raw_content_and_builds_function_responses():
    g = llm([response([fc('remember', key='a', value='1', source='s')]),
             response([fc('browser_read')])])
    r1 = g.create('s', specs(), [{'role': 'user', 'content': 'goal'}])
    msgs = [{'role': 'user', 'content': 'goal'},
            {'role': 'assistant', 'content': r1.content, 'raw': r1.raw},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': r1.content[0].id,
                                          'name': 'remember', 'content': json.dumps({'ok': True, 'data': 1})}]}]
    g.create('s', specs(), msgs)
    sent = g.client.models.calls[1]['contents']
    assert sent[1] is r1.raw                                   # replayed verbatim (keeps thought signatures)
    fr = sent[2].parts[0].function_response
    assert fr.name == 'remember' and fr.response == {'result': {'ok': True, 'data': 1}}


def test_history_without_raw_is_rebuilt_from_blocks():
    g = llm([response([fc('browser_read')])])
    msgs = [{'role': 'user', 'content': 'goal'},
            {'role': 'assistant', 'content': [Block('text', text='hmm'),
                                              Block('tool_use', id='x', name='echo', input={'text': 'a'})]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'x', 'name': 'echo',
                                          'content': '{"ok": true}'}]}]
    g.create('s', specs(), msgs)
    sent = g.client.models.calls[0]['contents']
    assert sent[1].role == 'model' and sent[1].parts[1].function_call.name == 'echo'


def test_empty_response_becomes_a_text_block():
    empty = types.GenerateContentResponse(candidates=[types.Candidate(finish_reason='SAFETY')])
    r = llm([empty]).create('s', specs(), [{'role': 'user', 'content': 'g'}])
    assert r.content[0].type == 'text' and 'empty model response' in r.content[0].text and r.raw is None


def test_rate_limit_is_retried_but_auth_errors_are_not():
    rate = errors.APIError(429, {'error': {'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
    g = llm([rate, rate, response([fc('browser_read')])])
    assert g.create('s', specs(), [{'role': 'user', 'content': 'g'}]).content[0].name == 'browser_read'
    assert len(g.client.models.calls) == 3
    bad = errors.APIError(403, {'error': {'message': 'API key invalid', 'status': 'PERMISSION_DENIED'}})
    g2 = llm([bad, response([fc('browser_read')])])
    with pytest.raises(errors.APIError):
        g2.create('s', specs(), [{'role': 'user', 'content': 'g'}])
    assert len(g2.client.models.calls) == 1


def test_judge_parses_json_even_with_fences():
    verdict = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role='model', parts=[types.Part(text='```json\n{"pass": false, "failures": ["wrong amount"]}\n```')]))])
    assert llm([verdict]).judge({'goal': 'g'}) == {'pass': False, 'failures': ['wrong amount']}
