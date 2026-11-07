# GitHub state verified 7 November 2026

Historical snapshot: this inspection predates the user-authorised EricccShen fork/PR follow-up. It is evidence of the original run, not the current publication state.

Remote branches: main at 4dc8ce983027cf1efa58c5c107752b4d8c4fa1f6; dataprocess at de0fff48ba7e1b769826bcbd7cf3af294076fd4c. The latter descends from main and contains the newest cleaner and source layout.

All upstream commits (newest first; UTC timestamps):

```text
de0fff48ba7e1b769826bcbd7cf3af294076fd4c	2026-11-06T18:27:04Z	清洗后数据和结果.
bad6ef7a1f12998b38a61b5d65bc461cbd4475f1	2026-11-06T16:11:09Z	Data clean
bbd0e088a1724c2fb6c811b321fe082cd619ee3b	2026-11-06T14:47:15Z	Full data
4dc8ce983027cf1efa58c5c107752b4d8c4fa1f6	2026-11-06T10:49:04Z	基础数据清洗（目标明确）
7ddc77f0ea8f6036c0582f26d85dc94b97891080	2026-11-05T18:46:35Z	Data uploaded
efb528649069417aae4604acd082016cb637672e	2026-11-05T18:45:20Z	first commit
```

README is UTF-16 and describes preprocessing; it does not provide a Q30/Q31 reproduction runner. Latest cleaner: src/clean.py (identical upstream duplicate src/partI_cleaning/clean.py). The newest branch already contains clean.csv, education labels/mapping and a data-quality report in Data/Output and src/partI_cleaning. There is no upstream clean.pkl or reproduce.py. The full current upstream tree is in github_dataprocess_tree.txt.

Live GitHub API inspection: Issue #1 is the only issue, open with 0 comments; the explicit comments endpoint returned an empty list. All-state pull requests endpoint returned an empty list, so there are no PR reviews to inspect. No issue or PR was changed. Public git ls-remote rechecked both branch heads before delivery.

The user chose local branch and patch delivery in this session after browser-tool timeouts prevented switching to the requested GitHub identity. This local work does not create a remote branch or a branch URL. No push, force push, issue closure or merge occurred.
