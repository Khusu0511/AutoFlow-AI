import json

import pytest

from worker.context import CTX
from worker.errors import ToolInputError
from worker.gate import check_gate
from worker.tools import REGISTRY
from worker.tools.base import json_arg
from worker.tools.guard import check_url


def asker(answer, log):
    def ask(q, options=None):
        log.append(q)
        return answer
    return ask


def test_read_tools_pass_without_plan(mem):
    assert check_gate(REGISTRY['http_get'], {'url': 'x'}, mem, asker('approve', [])) is None


def test_write_needs_plan(mem):
    r = check_gate(REGISTRY['browser_click'], {'id': 1}, mem, asker('approve', []))
    assert r['error_class'] == 'no_plan'


def test_ungrounded_value_is_blocked(mem):
    mem.plan = ['x']
    r = check_gate(REGISTRY['browser_type'], {'id': 1, 'text': 'Evil Corp'}, mem, asker('approve', []))
    assert r['error_class'] == 'ungrounded_args'


def test_grounded_value_passes_and_password_is_exempt(mem):
    mem.plan = ['x']
    assert check_gate(REGISTRY['browser_type'], {'id': 1, 'text': 'Acme Supplies'}, mem, asker('no', [])) is None
    CTX.last_snapshot = {'elements': [{'id': 2, 'type': 'password', 'label': 'Password'}]}
    assert check_gate(REGISTRY['browser_type'], {'id': 2, 'text': 'secret-from-creds'}, mem, asker('no', [])) is None


def test_low_confidence_fact_triggers_approval(mem):
    mem.plan = ['x']
    mem.remember('amount', '980.00', 'scan', confidence=0.5)
    log = []
    body = json.dumps({'amount': 980.0})
    assert check_gate(REGISTRY['http_post'], {'url': 'http://localhost:8002/api/payables', 'body': body},
                      mem, asker('approve', log)) is None
    assert len(log) == 1 and 'low-confidence' in log[0]
    r = check_gate(REGISTRY['http_post'], {'url': 'http://localhost:8002/api/payables', 'body': body},
                   mem, asker('deny', []))
    assert r['error_class'] == 'user_denied'


def test_irreversible_always_asks(mem):
    mem.plan = ['x']
    log = []
    args = {'url': 'http://localhost:8002/api/payables/1/mark_paid', 'body': '{}'}
    assert REGISTRY['http_post'].risk_for(args) == 'irreversible'
    r = check_gate(REGISTRY['http_post'], args, mem, asker('deny', log))
    assert r['error_class'] == 'user_denied' and log


def test_approve_writes_mode_asks_before_commit_button(mem):
    mem.plan = ['x']
    CTX.last_snapshot = {'elements': [{'id': 7, 'label': 'Save Payable'}, {'id': 8, 'label': 'Payables'}]}
    log = []
    check_gate(REGISTRY['browser_click'], {'id': 8}, mem, asker('approve', log), 'writes')
    assert not log                                  # ordinary link: no question
    check_gate(REGISTRY['browser_click'], {'id': 7}, mem, asker('approve', log), 'writes')
    assert len(log) == 1                            # commit-style button: asks


def test_url_allowlist():
    check_url('http://localhost:8001/vendors')
    check_url('http://localhost:8002')
    for bad in ('http://evil.example.com/x', 'http://localhost:8001.evil.com/', 'file:///etc/passwd'):
        with pytest.raises(ToolInputError) as e:
            check_url(bad)
        assert e.value.cls == 'blocked_url'


def test_json_arg():
    assert json_arg('{"a": 1}') == {'a': 1}
    assert json_arg({'a': 1}) == {'a': 1}
    assert json_arg('') == {}
    with pytest.raises(ToolInputError):
        json_arg('{not json')


def test_set_plan_flattens_and_enforces_read_only(mem, fake_tools):
    out = REGISTRY['set_plan'].fn(['a'], [{'description': 'd', 'tool': 'read_store', 'args_json': '{}',
                                           'expect_path': 'value', 'expect_equals': 'x'}])
    assert out['criteria'] == 1
    assert mem.criteria[0]['check'] == {'tool': 'read_store', 'args': {}}
    assert mem.criteria[0]['expect'] == {'path': 'value', 'equals': 'x'}
    with pytest.raises(ToolInputError):
        REGISTRY['set_plan'].fn(['a'], [{'description': 'd', 'tool': 'writer', 'args_json': '{}'}])
    with pytest.raises(ToolInputError):
        REGISTRY['set_plan'].fn(['a'], [{'description': 'd', 'tool': 'nope', 'args_json': '{}'}])


def test_integer_arguments_are_coerced_from_gemini_floats():
    t = REGISTRY['browser_click']
    assert t.coerce({'id': 7.0}) == {'id': 7} and isinstance(t.coerce({'id': 7.0})['id'], int)
    assert t.coerce({'id': '12'}) == {'id': 12}
    assert t.coerce({'id': 7.5}) == {'id': 7.5}            # non-integral values are left for validation
    assert REGISTRY['browser_type'].coerce({'id': 3.0, 'text': 'x'}) == {'id': 3, 'text': 'x'}


def test_file_ask_round_trip(tmp_path):
    import json
    import threading
    import time
    from worker.asking import file_ask
    ask = file_ask(str(tmp_path), poll=0.05)

    def human():
        while not (tmp_path / 'question.json').exists():
            time.sleep(0.02)
        q = json.loads((tmp_path / 'question.json').read_text())
        (tmp_path / 'answer.json').write_text(json.dumps({'answer': q['options'][1]}))
    threading.Thread(target=human, daemon=True).start()
    assert ask('Which one?', ['A', 'B']) == 'B'
    assert not (tmp_path / 'question.json').exists() and not (tmp_path / 'answer.json').exists()


def test_placeholder_api_key_counts_as_unset(monkeypatch):
    import importlib
    from worker import config
    monkeypatch.setenv('GEMINI_API_KEY', 'your-gemini-api-key')
    importlib.reload(config)
    assert config.GEMINI_API_KEY == ''
    monkeypatch.setenv('GEMINI_API_KEY', 'AIza-real-looking-key')
    importlib.reload(config)
    assert config.GEMINI_API_KEY == 'AIza-real-looking-key'
    monkeypatch.delenv('GEMINI_API_KEY')
    importlib.reload(config)
