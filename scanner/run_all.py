"""Run the whole pipeline. Each step fails soft so one broken source never kills the report.
usage: python scanner/run_all.py [--collect-only] [--no-agents]"""
import sys, subprocess, pathlib
HERE = pathlib.Path(__file__).parent
args = set(sys.argv[1:])
steps = ['collect_market', 'collect_reddit', 'collect_trends', 'collect_x', 'collect_youtube', 'collect_news', 'collect_crypto', 'collect_extras']
if '--collect-only' not in args:
    steps += ['analyze'] + ([] if '--no-agents' in args else ['agents']) + ['report', 'score_journal']
sys.path.insert(0, str(HERE))
from common import day_dir
log = open(day_dir() / 'run_log.txt', 'a')   # saved to the repo so failures can be read later
fail = []
for s in steps:
    print(f'=== {s}', flush=True); log.write(f'=== {s}\n'); log.flush()
    r = subprocess.run([sys.executable, str(HERE / f'{s}.py')], cwd=HERE, capture_output=True, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    print(out, flush=True); log.write(out[-20000:] + f'\n(exit {r.returncode})\n'); log.flush()
    if r.returncode:
        fail.append(s)
        if s in ('collect_market', 'analyze'):   # nothing to report without prices
            break
print('failed steps:', fail or 'none')
sys.exit(1 if {'collect_market', 'analyze', 'report'} & set(fail) else 0)
