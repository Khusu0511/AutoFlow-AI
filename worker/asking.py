"""How the agent asks the human: terminal prompt, or files watched by the Streamlit UI."""
import json
import os
import time


def cli_ask(question, options=None):
    print(f'\n[agent asks] {question}')
    if options:
        print('  options: ' + ' / '.join(options))
    return input('> ').strip()


def file_ask(run_dir, poll=0.5, timeout=1800):
    q_path = os.path.join(run_dir, 'question.json')
    a_path = os.path.join(run_dir, 'answer.json')

    def ask(question, options=None):
        with open(q_path, 'w') as f:
            json.dump({'question': question, 'options': options}, f)
        waited = 0
        while not os.path.exists(a_path):
            time.sleep(poll)
            waited += poll
            if waited > timeout:
                raise TimeoutError('no answer from the user')
        time.sleep(0.1)
        with open(a_path) as f:
            answer = json.load(f)['answer']
        os.remove(a_path)
        os.remove(q_path)
        return answer
    return ask


def scripted_ask(answers, default='deny'):
    """Deterministic answers for evals. `answers` maps a substring of the question to the reply."""
    def ask(question, options=None):
        for key, val in (answers or {}).items():
            if key.lower() in question.lower():
                return val
        return default
    return ask
