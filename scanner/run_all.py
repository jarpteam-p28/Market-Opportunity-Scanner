"""Run the whole pipeline. Each step fails soft so one broken source never kills the report.
usage: python scanner/run_all.py [--collect-only] [--no-agents]"""
import sys, subprocess, pathlib
HERE = pathlib.Path(__file__).parent
args = set(sys.argv[1:])
steps = ['collect_market', 'collect_reddit', 'collect_trends', 'collect_x', 'collect_news']
if '--collect-only' not in args:
    steps += ['analyze'] + ([] if '--no-agents' in args else ['agents']) + ['report', 'score_journal']
fail = []
for s in steps:
    print(f'=== {s}', flush=True)
    r = subprocess.run([sys.executable, str(HERE / f'{s}.py')], cwd=HERE)
    if r.returncode:
        fail.append(s)
        if s in ('collect_market', 'analyze'):   # nothing to report without prices
            break
print('failed steps:', fail or 'none')
sys.exit(1 if {'collect_market', 'analyze', 'report'} & set(fail) else 0)
