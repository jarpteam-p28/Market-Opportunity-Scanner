# Notes: Chris Camillo — how he reads comments, seasonal baselines, negative virality (summary in our words)
Source: long-form interview Pablo shared. These are his opinions and methods.

- **Where the signal is.** For ~9 years he has read TikTok comments about 4 hours a night, searching deliberately outside his own feed and demographic.
  - Comments are where people say what they want BEFORE they buy, so they lead sales data. Wall Street largely ignores this, partly because it has no long history to backtest against.
  - Earlier sources were malls and restaurant lines, then Facebook, then Twitter (until it turned to news and politics), now ~90% TikTok.
  - Reddit and specialised forums help for niches.
- **The funnel.** Many changes go in; few come out investable. The change must be:
  - big for a public company,
  - not overshadowed by other news at that company,
  - not yet noticed by Wall Street.
  He used to find 1–2 such trades a year and now finds 4–6, because culture moves faster and more of it is online.
- **Know what normal looks like (seasonal baselines).** Example: every September/October there's a normal level of "Uggs" talk. The UGG Mini launch was clearly above normal.
  - Compare against the SAME weeks in prior years, not just last month.
  - A beginner can build the baseline by looking at old videos and comments from past seasons.
- **Read the meaning, not just the count.** Lots of comments about a brand being "on sale" during peak season can be a red flag (weak demand), even though the talk sounds positive.
- **Breadth of creators.** If only a few creators have covered a product but comment interest is huge, expect more creators to pile in. The trend is still early.
- **Organic vs fake.** Real comments carry emotion and passion; bot or seeded comments mostly don't, yet. Emotion drives buying.
- **Negative virality.** One viral false claim can stall a brand: a misread "arsenic" ingredient for Celsius, "cyanide" rumours for Prime. He watches for early scare chatter (e.g. a viral "satanic" claim about Labubu) as a possible turning point.
- **Event run-ups.** Barbie / Mattel: he bought on months of exceptional buzz and sold almost all on the day the movie came out, as the information became public. Labubu / Pop Mart (Hong Kong-listed) roughly tripled as the craze spread from China.
- **Why stocks move.** New information that the market sees as good or bad, real or not. "Everyone knows it's Christmas" is not new information. He trades one piece of under-appreciated information at a time.

## How the scanner uses this
- **Consumer watch compares searches to the same weeks last year,** not only the prior 12 weeks, and flags 5-year highs.
- **YouTube comments, optional and free.** Needs a YOUTUBE_API_KEY. For each watch term the scanner reads recent video comments and measures buying-intent words ("need this", "sold out", "where can I get") and scare words. TikTok has no open API, so YouTube is the closest automatable stand-in.
- **Scare / negative-virality flag.** Counts posts mentioning a brand together with words like toxic, recall, lawsuit or banned. When it rises, the read becomes "CAUTION: check if it's true".
- **Added to consumer watch:** Labubu (Pop Mart 9992.HK), Uggs (Deckers), Barbie (Mattel).
- **Still manual:** TikTok comment reading itself, and checking how many creators are covering something. Pablo can do these by hand. The agents will say when an idea needs that check.
