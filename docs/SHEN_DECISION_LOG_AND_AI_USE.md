# Shen decision log and AI use evidence

Follow-up disclosure: the user later completed GitHub CLI device authorisation as EricccShen and authorised fork/PR collaboration because that account lacks upstream Write permission. The first local-delivery record below predates this follow-up; publication status is available in GitHub and the root Q30_Q31_README.md.

This is a factual working record for the group's one-page decision log and AI use statement. Condense it after group review; do not imply that one member's record covers everyone.

## Decisions and alternatives actually executed

| Decision | Alternative executed | Observed effect | Current use |
|---|---|---|---|
| Use within-country survey weights | Unweighted percentages for every Q30/Q31 category | Weighted rounded matches: 192/192; unweighted: 53/192; largest category shift 7.68 pp, Greece Q30 Nothing at all | Weights for population estimates, as directed by Pew Data Info |
| Keep DK/Refused in denominators | Substantive-answer-only generation percentages | India Non-Gen Z Q30 codes 1+2 changes 39.47% → 50.77%, +11.30 pp | Keep all responses for topline and main descriptive figures; retain alternate as sensitivity |
| Leave non-Australian exact-age nonresponse unclassified pending group confirmation | Use only bands entirely within one generation | 252 additionally classified; unclassified 296 → 44; maximum percentage change 1.31 pp, Japan Gen Z Heard a lot | User reconfirmed pending policy in this session; no crossing band assigned |
| Use Q30 codes 1+2 as awareness in the main figure | Code 1 only, Heard a lot, as intensity | Largest gap Indonesia +33.61 → Greece +47.57; smallest absolute gap Germany -0.07 → Nigeria +3.98 | Report the indicator definition beside the rankings; alternative figure is for review |
| Use Australian bands with the 29/30 boundary | Existing cleaner compares band maxima and midpoints | 0 respondents change generation; 326 Australians in Gen Z; 2 lack bands | Classify by whole bands; do not analyse assigned endpoints as observed ages |
| Preserve latest education mapping | No alternative mapping was executed by Shen | Mapping output identical to the original latest SAV run | Review/approval remains with Zhang; no invented comparison effect |

## Actual AI workflow

Generative tool: Codex, using its coding assistant in this chat. Uses: interpreting the provided brief and Week 1 lecture, inspecting repository history and the latest cleaner, writing a portable path fix and a separate statistics/audit script, generating aggregate tables and scientific figures, drafting run instructions, and a separate read-only code review. Execution used Python, pyreadstat, pandas, NumPy, pypdf, openpyxl, matplotlib and pytest; Git and the GitHub connector were used for repository inspection. A browser login tool was attempted but timed out before a login page opened. No password was saved, no message was sent to group members, and no remote push occurred.

The user prompt supplied the detailed COMP5122M handoff and required: “使用目前最新的脚本”, “必须尽量运行原始 SAV 清洗流程”, “每个国家单独计算”, and “所有结果必须来自实际执行和验证”. A subsequent user response kept band-only respondents unclassified pending group confirmation and chose local branch/patch delivery for this round. These are actual prompt excerpts with authentication details omitted.

Workflow: inspect both live branches and all six existing commits; run the unchanged newest SAV cleaner from `src/`; capture its separate root-directory path failure; change only input/output path handling and the misleading age-policy comment; compare saved outputs exactly with the untouched run; extract and independently cross-check both copies of official PDF page 48; calculate country-specific weighted/unweighted results; re-run the same statistics from persisted clean raw columns; test invalid denominators, corrupt outputs and age boundaries; inspect the rendered source table and generated figures. The handoff's provisional pickle and old manually entered topline numbers were not used as result evidence.

## A real incomplete AI output and its correction

The assistant first chose `pypdf.extract_text(extraction_mode='layout')` to find the official Q30/Q31 table. On these PDFs it returned an empty string for page 48, so the generated extraction produced no Q30/Q31 rows. Independent `pdftotext -layout` extraction showed the complete table was present; checking pypdf's ordinary extraction returned the text, with country names preceding the numeric rows. The assistant corrected the parser to handle that actual layout and reject incomplete 24-country tables, tested India Q30 and Canada Q31 against literal published values, compared both source PDFs, and visually checked page 48. Evidence: `evidence/pdf_extraction_check.json` and the source PDF page render in the local delivery package. This is an actual incomplete extraction in this session, not a hypothetical AI mistake.

The assistant also identified a misleading scope statement in upstream documentation: 294 exact-age refusals does not equal all generation exclusions, because 2 Australians lack age bands. The actual baseline exclusion count is 296. This was found by comparing saved generation values and country-specific age fields; it is a separate preprocessing-documentation correction, not presented as an AI-authored upstream error.

## Verification boundaries

The 192 matching rounded values verify reproduction of those category percentages. They do not validate the substantive ISCED mapping, prove conceptual equivalence of ideology scales, establish causality or prove small generation differences significant. The final group statement must also include the other members' actual tools, prompts and verification experiences. Do not claim every statistical choice was approved by the whole group.
