# Market-Opportunity-Scanner

A weekly "where are we and what's working" read on the stock market. It compares **what people are talking about** (Reddit, Google Trends, optionally X through Grok, headlines) with **what prices are actually doing** (S&P 500, sectors, the Magnificent 7, the top 10 stocks in each sector, and AI-supply-chain themes like chips, data centers, power, nuclear, water, cooling and copper). A team of research agents then writes a thesis and a watch list, and every idea is logged and scored later against the S&P.

Research only. Not investment advice.

## What it answers
1. **Where are we?** Risk-on or risk-off: S&P vs its 50- and 200-day averages, VIX, credit appetite, rates, the dollar.
2. **Is it only the Magnificent 7?** Mag 7 vs the S&P vs the average stock (equal-weight RSP), plus breadth.
3. **Which sectors are leading, and which are moving up the leaderboard vs last week?**
4. **Top 10 by market cap in each sector**, ranked live, with how each is doing.
5. **Talk vs tape for each theme:**
   - **CONFIRMED:** talk and price are both rising.
   - **EARLY:** talk is rising but price hasn't moved yet. This is the social-arbitrage watch.
   - **STEALTH:** price is rising while talk stays quiet.
   - **FADING:** talk and price are both cooling.
6. **The agents' thesis:** where we are, opportunities (each with what would confirm or kill it), the skeptic's risks, and a watch list.

## How it runs
GitHub Actions in `.github/workflows/scan.yml` runs it on a schedule:
- **Weekdays at about 5:35 pm New York:** collect data only. This builds the "talk" baseline, so the scanner can tell a real increase from normal chatter.
- **Saturdays at about 9:50 am New York:** full report, agents and Telegram summary.
- **Any time:** Actions tab → market-scan → Run workflow.

Results are committed back to the repo:
- `reports/latest.md` is the newest report. `reports/<date>.md` keeps the history.
- `data/<date>/*.json` holds the raw inputs.
- `journal/theses.csv` and `journal/scored.csv` log every watch-list idea and how it did after 1, 3 and 6 months vs the S&P.

## Setup: secrets
Add these under GitHub → Settings → Secrets and variables → Actions. All are optional; anything missing is skipped and the report still runs.

| Secret | What it unlocks | Cost |
|---|---|---|
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Reddit talk. Create a "script" app at reddit.com/prefs/apps. | free |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Phone summary (same bot as the stock scanner). | free |
| `ANTHROPIC_API_KEY` | The research agents' written thesis. | pay per use |
| `XAI_API_KEY` | X posts through Grok. Also set `x_grok.enabled: true` in config.yaml. | pay per use |

Prices come from Yahoo Finance and Google Trends comes from pytrends; neither needs a key. Google Trends sometimes rate-limits and is skipped quietly when it does.

## Change what it scans
Edit `config.yaml`: sectors, candidate stocks, Mag 7, themes (ETFs, tickers, keywords, search terms), subreddits, news feeds and agent settings. No code changes are needed.

## Add your own playbook
Put notes or transcripts as `.md` files in `playbook/`. The agents read them as context.

## Run locally
```
pip install -r requirements.txt
python scanner/run_all.py              # everything
python scanner/run_all.py --no-agents  # data report only
python tests/fake_run.py               # offline test with fake data
```

## Layout
```
config.yaml           what to scan
scanner/              collect_market, collect_reddit, collect_trends, collect_x, collect_news,
                      analyze, agents, report, score_journal, run_all
agents/               one prompt per research agent (regime, sectors, sentiment, themes, skeptic, synthesizer)
playbook/             your notes and transcripts for the agents
data/  reports/  journal/   outputs, committed by the workflow
```
