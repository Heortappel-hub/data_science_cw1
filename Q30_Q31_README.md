# Run the Q30 and Q31 reproduction

The contribution branch is on [EricccShen's fork](https://github.com/EricccShen/data_science_cw1/tree/shen-q30-q31-reproduction). It is based on the upstream dataprocess branch, which contains the latest SAV cleaner. Review against dataprocess to see only this contribution.

For a fresh checkout:

```bash
git clone --branch shen-q30-q31-reproduction --single-branch https://github.com/EricccShen/data_science_cw1.git
cd data_science_cw1
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-reproduction.txt
python src/clean.py --output-dir outputs/clean
python src/reproduce.py --clean outputs/clean/clean.pkl --output-dir outputs/reproduction
python -m pytest -q
```

On Windows, create the same Python 3.12 environment and activate it with .venv\Scripts\Activate.ps1 before running the Python commands. The executed verification environment was macOS arm64; Windows has not been independently tested.

The original SAV and supporting source documents are already under Data/sources. No manual data rename or provisional pickle is needed. Generated respondent-level data stay under the ignored outputs directory.

- [Method, results and complete run instructions](docs/Q30_Q31_REPRODUCTION.md)
- [Chinese result summary](reports/shen_q30_q31/SUMMARY_ZH.md)
- [All 192 official category comparisons](reports/shen_q30_q31/topline_comparison.csv)
- [Persisted-clean-output checks](reports/shen_q30_q31/validation.csv)
- [Suggested two-panel figure](reports/shen_q30_q31/generation_comparison.png)
- [Decision log and actual AI-use evidence](docs/SHEN_DECISION_LOG_AND_AI_USE.md)

The original snapshot/evidence files describe the first local-delivery run. The user subsequently authorised fork-and-pull-request collaboration using EricccShen. These earlier snapshots should not be read as the current publication state.

No changes to the upstream main branch or Issue #1 are requested by this contribution. The non-Australian age-band policy and the education owner's substantive ISCED approval remain pending; the existing mapping and baseline generation policy are preserved.
