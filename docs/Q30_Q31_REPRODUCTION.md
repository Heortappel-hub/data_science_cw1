# Q30 and Q31 reproduction

This branch independently reproduces Pew's Spring 2025 Q30/Q31 toplines for all 24 countries, compares survey-weighted and unweighted estimates, and checks the current cleaner's persisted output. It belongs to Shen's COMP5122M Data Science Part I work. Education harmonisation and the age-gap report remain with their respective owners.

## Run from the repository root

Use Python 3.12. The original SAV, dictionary, questionnaire, data info and topline are already in `Data/sources/` on this branch. Do not rename the SAV or use the provisional pickle from the handoff archive.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-reproduction.txt
python src/clean.py --output-dir outputs/clean
python src/reproduce.py --clean outputs/clean/clean.pkl --output-dir outputs/reproduction
python -m pytest -q
```

`clean.py` accepts `--input PATH` and `--output-dir PATH`. Its default input is resolved from the script location, so it also runs from another working directory. Outputs are relative to the calling directory unless explicitly specified. `reproduce.py` accepts `--input`, `--clean`, `--topline` and `--output-dir`. Load only the pickle generated locally by the cleaning command.

The small path change in `src/clean.py` preserves its preprocessing logic, education map, weights and output schema. The archived copy at `src/partI_cleaning/clean.py` is unchanged; use `src/clean.py` as the entry point. The upstream `src/data.sav` duplicate already existed; this contribution adds no raw data copies.

## What is calculated

For each country and category, weighted percent is `100 * sum(weight for that category) / sum(weight for the country)`. Unweighted percent is `100 * category_count / country_n`. Q30/Q31 codes 8 and 9 are combined as DK/Refused **before** calculating and rounding. Every respondent, including DK/Refused, stays in the official-reproduction denominator. Values 1, 2 and 3 retain questionnaire order. Percentages are rounded to the nearest integer, half up; rounded categories are not forced to sum to 100.

The script parses the actual repository Topline PDF, printed/PDF page 48. It accepts both its default pypdf column extraction and Poppler-style row extraction, and fails if either question lacks 24 unique country rows. The comparison includes signed weighted-minus-unweighted differences, both methods' differences from the official integer, and both rounding-match flags. Unknown/null responses, invalid weights, or incomplete official tables raise an error rather than silently changing denominators. Countries are never pooled into a population estimate.

`reproduce.py` reads the SAV and the saved clean pickle separately, joins on country+id for validation, and reproduces the entire table again from `ai_heard_raw` and `ai_cncexc_raw` in the persisted cleaned data. Q32 code 8 is explicitly tested as substantive Not sure; only code 9 becomes missing.

## Results and outputs

The executed run reproduced all 96 Q30 cells and all 96 Q31 cells after integer rounding. Unweighted estimates matched 29 Q30 cells and 24 Q31 cells. These are deterministic category-percentage checks, not 192 independent statistical tests or proof that every preprocessing choice is substantively valid. The largest absolute weighted-versus-unweighted difference was 7.6793 percentage points, Greece Q30 Nothing at all (16.8872% weighted versus 9.2079% unweighted). The largest absolute weighted-versus-official-integer difference was 0.4968 points, consistent with rounding.

Use the Pew general-population `weight` for population percentages, as required by the Data Info. Keep the unweighted comparison as a sensitivity analysis. For India Q30 A little, weighting changes 37.49% to 31.61%; India Q31 DK/Refused changes 20.93% to 25.63%. These differences have practical value for the decision log.

Generated aggregate results are under `outputs/reproduction/`. A reviewed snapshot is included in `reports/shen_q30_q31/`. The most useful files are:

- `topline_comparison.csv`: all 192 category comparisons, full precision and official matches.
- `report_three_countries.csv`: Canada, Germany and India, including all four response categories per question.
- `validation.csv` and `country_counts.csv`: persisted-output conservation checks.
- `age_band_inventory.csv`, `generation_counts.csv`, `age_policy_effect.csv`: country-specific age codes, exclusions and unambiguous-band sensitivity.
- `generation_sensitivity.csv`, `generation_gaps.csv`, `denominator_effect.csv`: optional inputs for the age-analysis owner, including weights, denominator and awareness-definition alternatives.
- `generation_comparison.png` / `.svg`: suggested two-panel report figure.
- `generation_comparison_a_lot.png` / `.svg`: alternative Q30 awareness-intensity figure, not an additional recommended report figure.
- `run_manifest.json`: dimensions, input/script SHA256 hashes and package versions.

No respondent-level outputs, pickles or virtual environments are added by this contribution. CSVs contain aggregate tables and variable metadata only.

## Age, education and ideology interfaces

The baseline uses Gen Z 18–29 and Non-Gen Z 30+, labelled `Older` in the unchanged cleaned output. Australia is classified directly from its age-band labels; there is no observed exact age for Australia. `age_assigned` in the upstream cleaner contains band endpoints, so it must not be used as measured exact age. Baseline exact-age nonresponse outside Australia remains unclassified, pending group confirmation (reconfirmed by the user in this session).

There are 294 such non-Australian respondents, plus 2 Australians without an age band: **296 unclassified**, not 294 overall. The optional wholly-contained-band sensitivity classifies 252 more people, leaving 44 unclassified: 6 crossing bands, 36 non-Australian DK/refusals to the band question, and the 2 Australians. Crossing codes in actual data are France code 2=25–34 (n=1), Germany code 2=25–44 (n=4), and Italy code 2=25–34 (n=1). Greece, South Korea and Turkey also define crossing 25–34 bands, but have no respondents in those codes here. The full inventory retains unused dictionary codes. The largest change in a weighted generation percentage across the computed metrics is 1.3057 points (Japan Gen Z, Heard a lot); the baseline policy is unchanged.

The newest `dataprocess` script already contains a 24-country, three-level ISCED grouping. This contribution preserves it byte-for-byte and checks the persisted source codes, country keys and mapped values against the upstream tracked `Data/Output/educ_mapping.csv`; it does not establish that Zhang approved the crosswalk. Australia, Israel, Kenya, South Africa and UK have disputed/coarse categories explicitly marked upstream. Zhang should review these, not have them replaced here. `educ_mapping.csv` remains available as a generated trace table.

Dictionary/SAV labels confirm `political_scale2`: 0 Extreme left → 6 Extreme right; `political_scale3`: 0 Extremely progressive → 6 Extremely conservative. Increasing codes align towards conservative/right; no reversal is required. Cleaned source-named fields remove 8/9 and combine into `ideology`; the original values and labels remain in the SAV. This directional alignment does not establish conceptual equivalence. Gender and education/ideology are not dimensions in this statistical reproduction.

## Suggested four-page report use

Use one compact table for the three required countries and the two-panel dumbbell figure for 24-country generation comparisons. In the main figure, awareness means Q30 codes 1+2, Heard at least a little; optimism means Q31 code 1, More excited than concerned. Both use all responses including DK/Refused. Dumbbells show each country's two levels and their gap without 96 bars; identical country ordering across panels makes different gap patterns visible. Q30 awareness is largest in Indonesia (+33.61 points) and smallest by absolute difference in Germany (-0.07). Q31 optimism is largest in Israel (+26.32) and smallest by absolute difference in Indonesia (-0.90). These are descriptive estimates, not significant differences established by hypothesis testing.

The alternative Q30 Heard a lot measures awareness intensity, and changes the largest/smallest countries to Greece (+47.57) and Nigeria (+3.98). Declare the indicator before stating rankings; retain that alternative in the decision log instead of displaying a second near-duplicate figure. Do not add separate official-reproduction bar charts. A short weighting paragraph and selected weighting differences add more value than another full figure. The full 24-country reproduction table remains an audit artifact, since unmarked appendices do not replace the report's required evidence.

For Q30 codes 1+2, Gen Z has a higher point estimate in 22/24 countries; the exceptions are Netherlands (-5.52 points) and Germany (-0.07). For Q31 code 1 it is higher in 23/24, with Indonesia (-0.90) the exception. Heard a lot is higher for Gen Z in all 24. Thus a universal generation-gap claim depends on the awareness definition and is not supported for every indicator. The figure has a native width of 6.8 inches and 11pt labels; use it at that size in the report to preserve readability.

Removing DK/Refused changes the substantive question and can materially inflate percentages: India Non-Gen Z awareness (1+2) rises from 39.47% to 50.77%, +11.30 points. The alternate table records this; the official reproduction always retains DK/Refused. No pooled global average, causal effect, design-adjusted confidence interval or p-value is claimed.

The brief requires at most four body pages, single spacing, minimum 11pt, plus at most one page each for cover, decision log/AI statement and references; figures/tables count in the body. The deadline printed in the brief is 10 November 2026 at 12:00 noon. This is COMP5122M, not COMP5712M. The final submission and consolidated age/education sections remain a group responsibility.
