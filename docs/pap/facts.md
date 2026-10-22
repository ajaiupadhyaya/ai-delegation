# Verified facts for the pre-analysis plan (referee item C8)

Checked on 2026-10-21 (Task 15b). Every entry gives its source. Where a source could not confirm
something, this file says so instead of filling the gap. Nothing here reads market data: event
dates are calendar facts, and day-0 trading-day checks against the return files happen only
after `pap-v1`.

AEI data are conversations matched to O\*NET tasks. Nothing here says anything about job risk
or displacement in the labour market.

## 1. Release dates of the occupation inputs

| Input | Release date | Source |
|---|---|---|
| OEWS May 2024 estimates (`oesm24*`) | **2025-04-02**, 10:00 a.m. ET (news release USDL-25-0451, reference period May 2024) | https://www.bls.gov/news.release/archives/ocwage_04022025.htm (header: "For release 10:00 a.m. (ET) Wednesday, April 2, 2025 USDL-25-0451") |
| O\*NET 29.3 database | **May 2025**. The day is **not verified**: the release list and the "What's New" page give only the month and year. | https://www.onetcenter.org/db_releases.html (29.3: May 2025; 29.2: February 2025; 30.0: August 2025); https://www.onetcenter.org/whatsnew.html (month-level headers only) |

Both are after the Design B formation release r2 (2025-03-27). The server's Last-Modified header
on the 29.3 text files (2026-07-23) is a re-upload timestamp. It is not evidence of the release
day.

## 2. OEWS top-code, May 2024 files

Missing-value note **`#`**: "indicates a wage equal to or greater than **$115.00 per hour** or
**$239,200 per year**".

Source: the "Field Descriptions" sheet, Notes block, of `national_M2024_dl.xlsx` (in
`oesm24nat.zip`) and of `nat4d_M2024_dl.xlsx` (in `oesm24in4.zip`). Both files are frozen in
`data/raw/MANIFEST.json`, and the two give identical wording. `file_descriptions.xlsx` in
`oesm24in4.zip` only lists the files and has no top-code note.

## 3. O\*NET 29.3 DWA files (C7)

Both files are in the source registry as `onet_29_3_tasks_to_dwas` and `onet_29_3_dwa_reference`.
They were fetched on 2026-10-21 and recorded in the MANIFEST.

| Key | URL | bytes | SHA-256 prefix |
|---|---|---|---|
| `onet_29_3_tasks_to_dwas` | https://www.onetcenter.org/dl_files/database/db_29_3_text/Tasks%20to%20DWAs.txt | 1,197,935 | `6cb7098b09a6` |
| `onet_29_3_dwa_reference` | https://www.onetcenter.org/dl_files/database/db_29_3_text/DWA%20Reference.txt | 187,200 | `e38a5b529a06` |

The directory index (`.../db_29_3_text/`) returns 403. Both URLs above returned 200 with
`text/plain`, and their headers match the existing `Task Statements.txt` in the same directory.
The headers are `O*NET-SOC Code, Task ID, DWA ID, Date, Domain Source` and
`Element ID, IWA ID, DWA ID, DWA Title`.

## 4. Event dates for D19 (rule P7)

**Named source.** Wikipedia, "List of large language models". The table is pinned at revision
**1381207107** (2026-10-20T17:58:18Z):
https://en.wikipedia.org/w/index.php?title=List_of_large_language_models&oldid=1381207107. The
wikitext of that revision was parsed directly (`action=raw`).

**Rows of the source in [2022-11-30, 2025-03-31] whose developer is OpenAI, Anthropic, Google
DeepMind or Google.** All are listed here. The source gives only a month for most rows, so each
day was verified against the developer's own announcement:

| Source row (developer as listed) | Source date | Verified announcement date (weekday) | Primary source |
|---|---|---|---|
| GPT-4 (OpenAI) | 2023-03 | 2023-03-14 (Tue) | OpenAI news feed https://openai.com/news/rss.xml, item "GPT-4", https://openai.com/index/gpt-4-research, pubDate Tue 14 Mar 2023 |
| PaLM 2 (**Google**, not Google DeepMind) | 2023-05 | 2023-05-10 (Wed) | https://blog.google/technology/ai/google-palm-2-ai-large-language-model/ ("May 10, 2023") |
| Claude 2 (Anthropic) | 2023-07 | 2023-07-11 (Tue) | https://www.anthropic.com/news/claude-2 ("Jul 11, 2023") |
| Claude 2.1 (Anthropic) | 2023-11 | 2023-11-21 (Tue) | https://www.anthropic.com/news/claude-2-1 ("Nov 21, 2023") |
| Gemini 1.0 (Google DeepMind) | 2023-12 | 2023-12-06 (Wed) | https://blog.google/technology/ai/google-gemini-ai/ ("Dec 06, 2023") |
| Gemini Ultra (Google DeepMind, rowspan) | 2024-02 | 2024-02-08 (Thu), Ultra 1.0 available through Gemini Advanced | https://blog.google/products/gemini/bard-gemini-advanced-app/ ("Feb 08, 2024") |
| Gemini 1.5 (Google DeepMind) | 2024-02 | 2024-02-15 (Thu) | https://blog.google/technology/ai/google-gemini-next-generation-model-february-2024/ ("Feb 15, 2024") |
| Gemma (Google DeepMind, rowspan; open-weights small models) | 2024-02 | 2024-02-21 (Wed) | https://blog.google/technology/developers/gemma-open-models/ ("Feb 21, 2024") |
| Claude 3 (Anthropic) | 2024-03 | 2024-03-04 (Mon) | https://www.anthropic.com/news/claude-3-family ("Mar 4, 2024") |
| Claude 3.5 (Anthropic) | 2024-06 | **unresolved: 2024-06-20 (Thu) or 2024-06-21 (Fri)**. The post displays "Jun 21, 2024". The model ID `claude-3-5-sonnet-20240620` and press coverage give June 20. | https://www.anthropic.com/news/claude-3-5-sonnet |
| OpenAI o1 (OpenAI) | 2024-09-12 | 2024-09-12 (Thu) | OpenAI news feed, "Introducing OpenAI o1", https://openai.com/index/introducing-openai-o1-preview, pubDate Thu 12 Sep 2024 |
| Gemini 2.0 (Google DeepMind) | 2025-02-05 | 2025-02-05 (Wed): 2.0 Flash GA, 2.0 Pro Experimental, Flash-Lite. Note that the first Gemini 2.0 announcement (2.0 Flash Experimental) was **2024-12-11** (Wed), https://blog.google/technology/google-deepmind/google-gemini-ai-update-december-2024/. | https://blog.google/technology/google-deepmind/gemini-model-updates-february-2025/ ("Feb 05, 2025") |
| Claude 3.7 (Anthropic) | 2025-02-24 | 2025-02-24 (Mon) | https://www.anthropic.com/news/claude-3-7-sonnet ("Feb 24, 2025") |
| GPT-4.5 (OpenAI) | 2025-02-27 | 2025-02-27 (Thu) | OpenAI news feed, "OpenAI GPT-4.5 System Card", https://openai.com/index/gpt-4-5-system-card, pubDate Thu 27 Feb 2025. openai.com pages return 403 to automated fetches, so the feed was used. |
| Gemini 2.5 (Google DeepMind) | 2025-03-25 | 2025-03-25 (Tue), Gemini 2.5 Pro Experimental | https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/ ("Mar 25, 2025") |

**Not in the named source, but in the current D19 draft list or relevant to it:**

- **ChatGPT, 2022-11-30 (Wed).** OpenAI feed, "Introducing ChatGPT", https://openai.com/index/chatgpt, pubDate Wed 30 Nov 2022. It is absent from the source's table, which mentions it only in a note on the GPT-3 row.
- **GPT-4o, 2024-05-13 (Mon).** OpenAI feed, "Hello GPT-4o", https://openai.com/index/hello-gpt-4o, pubDate Mon 13 May 2024. It is absent from the source's table.
- **OpenAI o3-mini, 2025-01-31 (Fri).** OpenAI feed, https://openai.com/index/openai-o3-mini. It is absent from the source; the source's o3 row is dated 2025-04-16, which is outside the window.
- **DeepSeek-R1, 2025-01-20.** Not one of the three developers named by rule P7, so the rule excludes it. Its date was not re-verified here.

**What is left to the PAP revision.** Which rows count as "flagship" is not decided here. Items
needing a stated rule:

- PaLM 2, which the source lists under "Google";
- Gemma (open weights) and Gemini Ultra (a tier of Gemini 1.0);
- the two Gemini 2.0 dates;
- the Claude 3.5 day;
- the ChatGPT and GPT-4o events, which are missing from the source.

**Trading days.** Every verified date above is a weekday (computed). **Whether any of them is an
NYSE holiday is unverified.** The NYSE holiday calendar
(https://www.nyse.com/markets/hours-calendars, checked 2026-10-21) shows only 2026–2028, and the
Internet Archive could not be reached from this environment. From general calendar knowledge,
none of the dates falls on a standard NYSE holiday, but no source was checked for 2022–2025.
After `pap-v1`, the check is done mechanically against the dates actually present in the frozen
FF49 and factor files, applying P7's next-trading-day rule.

**Confirmatory window ends (for `aideleg.confirm_h5`).**

- **2026-08-31 (Mon) is an NYSE trading day.** The NYSE 2026 calendar on the page above lists no
  August holiday; Labor Day is Monday, September 7, 2026.
- **2025-04-01 (Tue) is a weekday.** It is not on the 2026–2028 calendar, and its holiday status
  is unverified by source. Good Friday 2025 was April 18 (calendar knowledge). If it were
  not a trading day, the script's coverage check (data must start on or before 2025-04-01)
  would still pass, because the files hold earlier dates. The check fails safe only in the
  other direction: missing late data makes it refuse.
