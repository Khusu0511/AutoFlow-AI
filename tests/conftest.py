import pytest

from worker import agent
from worker.context import CTX
from worker.memory import Memory
from worker.tools import REGISTRY
from worker.tools.base import Tool, obj


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    CTX.reset()
    monkeypatch.setattr(agent, 'RETRY_BASE', 0)
    yield
    CTX.reset()


@pytest.fixture
def mem():
    m = Memory('Enter invoice INV-1 for Acme Supplies')
    CTX.memory = m
    return m


@pytest.fixture
def fake_tools(monkeypatch):
    """Register small in-memory tools so the loop can be tested without any service."""
    state = {'flaky_calls': 0, 'writes': [], 'store': {}}

    def echo(text='hi'):
        return {'text': text}

    def flaky(fail_times=2):
        state['flaky_calls'] += 1
        if state['flaky_calls'] <= fail_times:
            raise TimeoutError('simulated timeout')
        return {'ok_after': state['flaky_calls']}

    def writer(value):
        state['writes'].append(value)
        state['store']['value'] = value
        return {'written': value}

    def always_fail():
        raise RuntimeError('boom')

    def read_store():
        return {'value': state['store'].get('value')}

    def add(name, fn, schema, **kw):
        monkeypatch.setitem(REGISTRY, name, Tool(name, name, schema, fn, **kw))

    add('echo', echo, obj({'text': {'type': 'string'}}, []))
    add('flaky', flaky, obj({'fail_times': {'type': 'integer'}}, []))
    add('writer', writer, obj({'value': {'type': 'string'}}), risk='write', idempotent=False,
        ground=lambda a: [a.get('value')])
    add('always_fail', always_fail, obj({}))
    add('read_store', read_store, obj({}))
    return state
