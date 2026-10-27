import json

from worker import agent
from worker.llm import ScriptedLLM
from worker.memory import Memory
from worker.verifier import deterministic_match, dig, verify


def plan_call(criteria):
    return ('set_plan', {'subgoals': ['do it'], 'criteria': criteria})


def crit(path=None, equals=None, tool='read_store'):
    c = {'description': 'stored value', 'tool': tool, 'args_json': '{}'}
    if equals is not None:
        c.update(expect_path=path, expect_equals=equals)
    return c


def run_policy(policy, tmp_path, **kw):
    return agent.run('Write the value hello', llm=ScriptedLLM(policy), run_dir=tmp_path,
                     ask=lambda q, o=None: 'approve', **kw)


# ----------------------------------------------------------------- verifier
def test_dig_and_matching():
    obs = {'body': [{'amount_cents': 425000}]}
    assert dig(obs, 'body.0.amount_cents') == 425000
    assert deterministic_match(obs, {'path': 'body.0.amount_cents', 'equals': '425000'}) is True
    assert deterministic_match(obs, {'path': 'body.0.amount_cents', 'equals': '1'}) is False
    assert deterministic_match(obs, {'path': 'body.5.x', 'equals': '1'}) is False
    assert deterministic_match(obs, None) is None


def test_verifier_rejects_non_read_checks_and_flags_weak(fake_tools):
    m = Memory('g')
    m.criteria = [{'description': 'bad', 'check': {'tool': 'writer', 'args': {'value': 'x'}}}]
    v = verify(m, ScriptedLLM(lambda: iter(())))
    assert not v['pass'] and fake_tools['writes'] == []        # the write tool was never run
    m.criteria = []
    assert verify(m, ScriptedLLM(lambda: iter(())))['weak_verification'] is True


def test_judge_unavailable_falls_back_to_deterministic(fake_tools):
    class Broken:
        def judge(self, payload):
            raise RuntimeError('quota')
    m = Memory('g')
    m.criteria = [{'description': 'd', 'check': {'tool': 'echo', 'args': {'text': 'a'}},
                   'expect': {'path': 'text', 'equals': 'a'}}]
    v = verify(m, Broken())
    assert v['pass'] and 'judge unavailable' in v['judge_note']


# ----------------------------------------------------------------- agent loop
def test_happy_path_is_verified_against_real_state(tmp_path, fake_tools):
    def policy():
        yield plan_call([crit('value', 'hello')])
        yield ('remember', {'key': 'value', 'value': 'hello', 'source': 'task', 'confidence': 1.0})
        yield ('writer', {'value': 'hello'})
        yield ('finish', {'status': 'done', 'summary': 'wrote it'})
    rep = run_policy(policy, tmp_path)
    assert rep['status'] == 'done' and rep['verification_passed'] and not rep['weak_verification']
    assert fake_tools['writes'] == ['hello']
    assert (tmp_path / 'result.json').exists() and (tmp_path / 'trace.jsonl').exists()


def test_agent_cannot_claim_success_that_did_not_happen(tmp_path, fake_tools):
    def policy():
        yield plan_call([crit('value', 'hello')])
        res = yield ('finish', {'status': 'done', 'summary': 'I did it (I did not)'})
        assert res[0]['error_class'] == 'verification_failed'
        yield ('remember', {'key': 'v', 'value': 'hello', 'source': 'task'})
        yield ('writer', {'value': 'hello'})
        yield ('finish', {'status': 'done', 'summary': 'now really done'})
    rep = run_policy(policy, tmp_path)
    assert rep['status'] == 'done' and fake_tools['writes'] == ['hello']


def test_persistent_false_claim_is_downgraded_to_partial(tmp_path, fake_tools):
    def policy():
        yield plan_call([crit('value', 'hello')])
        for _ in range(5):
            yield ('finish', {'status': 'done', 'summary': 'trust me'})
    rep = run_policy(policy, tmp_path)
    assert rep['status'] == 'partial' and not rep['verification_passed']


def test_honest_blocked_is_accepted(tmp_path, fake_tools):
    def policy():
        yield plan_call([crit('value', 'hello')])
        yield ('finish', {'status': 'blocked', 'summary': 'cannot do it'})
    assert run_policy(policy, tmp_path)['status'] == 'blocked'


def test_idempotent_tool_is_retried_then_succeeds(tmp_path, fake_tools):
    def policy():
        res = yield ('flaky', {'fail_times': 2})
        assert res[0]['ok'] is True
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    rep = run_policy(policy, tmp_path)
    assert fake_tools['flaky_calls'] == 3 and rep['retries'] == 2


def test_non_idempotent_tool_is_not_auto_retried(tmp_path, fake_tools, monkeypatch):
    calls = []
    from worker.tools import REGISTRY
    orig = REGISTRY['writer'].fn

    def boom(value):
        calls.append(1)
        raise TimeoutError('t')
    monkeypatch.setattr(REGISTRY['writer'], 'fn', boom)

    def policy():
        yield plan_call([])
        yield ('remember', {'key': 'v', 'value': 'hello', 'source': 'task'})
        res = yield ('writer', {'value': 'hello'})
        assert res[0]['error_class'] == 'timeout'
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    run_policy(policy, tmp_path)
    assert len(calls) == 1


def test_write_before_plan_and_ungrounded_write_are_blocked(tmp_path, fake_tools):
    def policy():
        r = yield ('writer', {'value': 'hello'})
        assert r[0]['error_class'] == 'no_plan'
        yield plan_call([])
        r = yield ('writer', {'value': 'EVIL'})
        assert r[0]['error_class'] == 'ungrounded_args'
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    run_policy(policy, tmp_path)
    assert fake_tools['writes'] == []


def test_loop_detection_forces_replan(tmp_path, fake_tools):
    def policy():
        classes = []
        for _ in range(4):
            r = yield ('always_fail', {})
            classes.append(r[0]['error_class'])
        assert classes[-1] == 'loop_detected'
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    run_policy(policy, tmp_path)


def test_unknown_tool_and_bad_args_do_not_crash(tmp_path, fake_tools):
    def policy():
        r = yield ('does_not_exist', {})
        assert r[0]['error_class'] == 'bad_input'
        r = yield ('echo', {'wrong': 1})
        assert r[0]['error_class'] == 'bad_input'
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    assert run_policy(policy, tmp_path)['status'] == 'blocked'


def test_step_budget_and_cost_cap(tmp_path, fake_tools):
    def forever():
        i = 0
        while True:
            i += 1
            yield ('echo', {'text': str(i)})
    assert run_policy(forever, tmp_path / 'a', max_steps=5)['summary'] == 'Step budget exhausted.'

    class Pricey(ScriptedLLM):
        def create(self, *a):
            r = super().create(*a)
            r.usage.input_tokens = 10_000_000
            return r
    rep = agent.run('g', llm=Pricey(forever), run_dir=tmp_path / 'b', max_cost=1.0)
    assert rep['status'] == 'blocked' and 'budget' in rep['summary']


def test_model_api_failure_is_a_clean_blocked_report(tmp_path, fake_tools):
    class Down:
        def create(self, *a):
            raise RuntimeError('403 API key invalid')
    rep = agent.run('g', llm=Down(), run_dir=tmp_path)
    assert rep['status'] == 'blocked' and 'API key' in rep['summary']


def test_model_that_never_calls_tools_is_stopped(tmp_path, fake_tools):
    rep = run_policy(lambda: iter(()), tmp_path)
    assert rep['status'] == 'blocked' and 'stopped calling tools' in rep['summary']


def test_secrets_never_reach_the_trace(tmp_path, fake_tools, monkeypatch):
    from worker import config
    monkeypatch.setitem(config.CREDENTIALS, 'financedesk', ('clerk', 'sup3r-secret-pw'))

    def policy():
        yield ('get_credentials', {'system': 'financedesk'})
        yield ('echo', {'text': 'sup3r-secret-pw'})
        yield ('finish', {'status': 'blocked', 'summary': 'x'})
    run_policy(policy, tmp_path)
    assert 'sup3r-secret-pw' not in (tmp_path / 'trace.jsonl').read_text()
