import json

import httpx

from worker.errors import BrowserError, HttpError, ToolInputError, classify
from worker.memory import Memory, same_value


def test_classify():
    assert classify(BrowserError('element_not_found', 'x')) == 'element_not_found'
    assert classify(HttpError(401, 'no')) == 'session_expired'
    assert classify(HttpError(409, 'dup')) == 'duplicate'
    assert classify(HttpError(422, 'bad')) == 'validation_error'
    assert classify(HttpError(503, 'down')) == 'server_error'
    assert classify(HttpError(404, 'nf')) == 'client_error'
    assert classify(httpx.ConnectTimeout('t')) == 'timeout'
    assert classify(httpx.ConnectError('c')) == 'service_unavailable'
    assert classify(TypeError('missing arg')) == 'bad_input'
    assert classify(ToolInputError('x', 'blocked_url')) == 'blocked_url'
    assert classify(RuntimeError('weird')) == 'unknown'


def test_same_value_is_tolerant():
    assert same_value('4,250.00', 4250)
    assert same_value('4250.0', '4,250.00')
    assert same_value(' Acme  Supplies ', 'acme supplies')
    assert not same_value('4250', '4251')
    assert not same_value('INV-1', 'INV-2')


def test_grounding_from_goal_or_facts():
    m = Memory('Enter invoice INV-1 for Acme Supplies')
    assert m.grounded('Acme Supplies')            # in the goal
    assert m.grounded('inv-1')
    assert not m.grounded('Evil Corp')
    m.remember('amount', '4,250.00', 'invoice.pdf')
    assert m.grounded(4250.0)                     # numeric match to a remembered fact
    assert not m.grounded(9999)


def test_secrets_are_masked_in_prompt_and_facts():
    m = Memory('g')
    m.remember('desk_password', 'hunter2', 'creds')
    assert 'hunter2' not in m.render()
    assert m.facts_dict()['desk_password']['value'] == '***'
    assert m.grounded('hunter2')                  # still usable for grounding


def test_compact_keeps_structure_and_shrinks_old_results():
    m = Memory('g')
    big = json.dumps({'ok': True, 'data': {'page_text': 'x' * 5000}})
    msgs = [{'role': 'user', 'content': 'g'}]
    for i in range(12):
        msgs.append({'role': 'assistant', 'content': ['call']})
        msgs.append({'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': str(i),
                                                  'name': 't', 'content': big}]})
    out = m.compact(msgs, keep=6)
    assert len(out) == len(msgs)
    assert [x['role'] for x in out] == [x['role'] for x in msgs]
    assert len(out[2]['content'][0]['content']) < 200          # old: summarized
    assert out[2]['content'][0]['tool_use_id'] == '0'           # pairing id kept
    assert out[-1]['content'][0]['content'] == big              # recent: untouched
