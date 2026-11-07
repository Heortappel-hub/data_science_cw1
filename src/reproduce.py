"""Country-by-country Q30/Q31 reproduction and persisted-clean-output audit.

Run clean.py first. This script never modifies raw data or the education map.
Only aggregated results are written; survey-design significance tests are not implied.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Data/sources'
COUNTRIES = ['Canada', 'France', 'Germany', 'Greece', 'Hungary', 'Italy',
             'Netherlands', 'Poland', 'Spain', 'Sweden', 'UK', 'Australia',
             'India', 'Indonesia', 'Japan', 'South Korea', 'Israel', 'Turkey',
             'Kenya', 'Nigeria', 'South Africa', 'Argentina', 'Brazil', 'Mexico']
QUESTIONS = {'Q30': 'ai_heard', 'Q31': 'ai_cncexc'}
CATEGORIES = {'Q30': ['A lot', 'A little', 'Nothing at all', 'DK/Refused'],
              'Q31': ['More excited than concerned', 'More concerned than excited',
                      'Equally concerned and excited', 'DK/Refused']}
CODES = [1, 2, 3, 8]  # 8 here represents the combined 8+9 category.


def round_percent(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def proportions(answers, weights):
    a, w = np.asarray(answers, dtype=float), np.asarray(weights, dtype=float)
    if len(a) == 0 or len(a) != len(w):
        raise ValueError('Empty sample or response/weight length mismatch')
    if not np.isin(a, [1, 2, 3, 8, 9]).all():
        raise ValueError('Unexpected or null Q30/Q31 response; denominator not changed')
    if not (np.isfinite(w).all() and (w > 0).all()):
        raise ValueError('Weights must be finite, observed and strictly positive')
    a = np.where(a == 9, 8, a)
    return {code: (float(100 * w[a == code].sum() / w.sum()),
                   float(100 * (a == code).mean())) for code in CODES}


def parse_topline_text(text):
    """Parse this Pew PDF's country/value blocks, rejecting partial tables.

    pypdf default extraction places all country names before the numeric rows.
    Poppler layout extraction instead places each country's numbers on its line.
    Both are accepted, but mixed/partial layouts are rejected.
    """
    records = []
    for question in QUESTIONS:
        match = re.search(r'\b' + question + r'\.([\s\S]*?)(?=\bQ\d+[a-z]?\.|\Z)', text)
        if not match:
            raise ValueError(f'Missing {question} in official PDF text')
        block = match.group(1)
        # Anchor trailing whitespace horizontally; \s* could consume a newline.
        country_rows = re.findall(r'^[ \t]*(.+?)[ \t]+Spring,[ \t]*2025[ \t]*([^\n]*)$', block, re.M)
        names = [name.strip() for name, _ in country_rows]
        if len(names) != 24 or set(names) != set(COUNTRIES):
            raise ValueError(f'{question}: expected all 24 unique countries, got {len(names)}')
        if all(values.strip() for _, values in country_rows):
            numbers = [list(map(int, values.split())) for _, values in country_rows]
        elif all(not values.strip() for _, values in country_rows):
            numbers = [list(map(int, row.split())) for row in re.findall(
                r'^[ \t]*(\d+[ \t]+\d+[ \t]+\d+[ \t]+\d+[ \t]+100)[ \t]*$', block, re.M)]
        else:
            raise ValueError(f'{question}: mixed table extraction layout')
        if len(numbers) != 24:
            raise ValueError(f'{question}: expected 24 value rows, got {len(numbers)}')
        for name, nums in zip(names, numbers, strict=True):
            if len(nums) != 5 or nums[-1] != 100 or any(x < 0 or x > 100 for x in nums) or not 98 <= sum(nums[:4]) <= 102:
                raise ValueError(f'{question}/{name}: malformed official row {nums}')
            for code, category, value in zip(CODES, CATEGORIES[question], nums[:4], strict=True):
                records.append(dict(country=name, question=question, code=code,
                                    category=category, official_pct=value))
    return pd.DataFrame(records)


def parse_topline(path):
    reader = PdfReader(path)
    pages = [(i + 1, p.extract_text() or '') for i, p in enumerate(reader.pages)]
    relevant = [(i, t) for i, t in pages if re.search(r'\bQ30\.', t) or re.search(r'\bQ31\.', t)]
    result = parse_topline_text('\n'.join(t for _, t in relevant))
    for question in QUESTIONS:
        loc = [i for i, t in relevant if re.search(r'\b' + question + r'\.', t)]
        if len(loc) != 1:
            raise ValueError(f'{question}: ambiguous source PDF page')
        result.loc[result.question == question, 'pdf_page'] = loc[0]
    result['pdf_page'] = result.pdf_page.astype(int)
    return result


def band_generation(label):
    if not isinstance(label, str):
        return None
    m = re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)', label.strip())
    if m:
        lo, hi = map(int, m.groups())
        if lo > hi:
            return None
    else:
        m = re.fullmatch(r'(\d+)\+', label.strip())
        if not m:
            return None
        lo, hi = int(m.group(1)), float('inf')
    if 18 <= lo <= hi <= 29:
        return 'Gen Z'
    if 30 <= lo <= hi:
        return 'Non-Gen Z'
    return None


def generations(raw, labels, use_unambiguous_bands=False):
    gen = pd.Series(np.nan, index=raw.index, dtype=object)
    gen.loc[raw.age.between(18, 29)] = 'Gen Z'
    gen.loc[raw.age.between(30, 97)] = 'Non-Gen Z'
    au_codes = [k for k, v in labels['country'].items() if v == 'Australia']
    au = raw.country.isin(au_codes)
    gen.loc[au] = raw.loc[au, 'age_australia'].map(labels['age_australia']).map(band_generation)
    if use_unambiguous_bands:
        for col in sorted(c for c in raw if c.startswith('d_age_')):
            derived = raw[col].map(labels[col]).map(band_generation)
            mask = gen.isna() & ~au
            gen.loc[mask] = derived.loc[mask]
    return gen


def topline_comparison(raw, labels, official):
    country_labels = labels['country']
    if (raw.country.isna().any() or set(raw.country.unique()) != set(country_labels)
            or len(country_labels) != 24 or set(country_labels.values()) != set(COUNTRIES)):
        raise ValueError('SAV country codes/labels must cover exactly the expected 24 countries')
    rows = []
    for country_code, country in labels['country'].items():
        group = raw.loc[raw.country == country_code]
        if group.empty:
            raise ValueError(f'No records for {country}')
        for question, var in QUESTIONS.items():
            for code, (weighted, unweighted) in proportions(group[var], group.weight).items():
                rows.append(dict(country=country, question=question, code=code, n=len(group),
                                 weight_sum=group.weight.sum(), weighted_pct=weighted,
                                 unweighted_pct=unweighted))
    result = pd.DataFrame(rows).merge(official, on=['country', 'question', 'code'],
                                      validate='one_to_one', how='outer', indicator=True)
    if len(result) != 192 or not (result['_merge'] == 'both').all():
        raise ValueError('Official table and SAV country coverage differ')
    result = result.drop(columns='_merge')
    result['weighted_minus_unweighted_pp'] = result.weighted_pct - result.unweighted_pct
    for method in ['weighted', 'unweighted']:
        result[method + '_minus_official_pp'] = result[method + '_pct'] - result.official_pct
        result[method + '_rounded'] = result[method + '_pct'].map(round_percent)
        result[method + '_matches_official'] = result[method + '_rounded'] == result.official_pct
    return result


def age_inventory(raw, labels):
    rows = []
    for col in sorted(c for c in raw if c.startswith('d_age_')):
        for code, label in labels[col].items():
            mask = raw[col] == code
            for country_code in raw.loc[mask, 'country'].unique():
                n = int((mask & (raw.country == country_code) & ~raw.age.between(18, 97)).sum())
                rows.append(dict(country=labels['country'][country_code], variable=col,
                                 code=int(code), label=label, n_total=int((mask & (raw.country == country_code)).sum()),
                                 n_without_exact_age=n, unambiguous_generation=band_generation(label)))
        # Retain unused dictionary codes and variables as evidence, too.
        for code, label in labels[col].items():
            if not (raw[col] == code).any():
                rows.append(dict(country=col.removeprefix('d_age_'), variable=col,
                                 code=int(code), label=label, n_total=0, n_without_exact_age=0,
                                 unambiguous_generation=band_generation(label)))
    return pd.DataFrame(rows)


def audit(raw, clean, labels):
    checks = []
    def check(name, ok, detail):
        checks.append(dict(check=name, status='PASS' if bool(ok) else 'FAIL', detail=str(detail)))
    check('total_records', len(raw) == len(clean), f'raw={len(raw)}, clean={len(clean)}')
    check('raw_primary_key', not raw[['country', 'id']].isna().any().any() and not raw.duplicated(['country', 'id']).any(), 'country+id non-null and unique')
    check('clean_primary_key', not clean[['country', 'id']].isna().any().any() and not clean.duplicated(['country', 'id']).any(), 'country+id non-null and unique')
    check('country_counts', raw.groupby('country').size().to_dict() == clean.groupby('country').size().to_dict(), 'all 24 country counts compared')
    check('key_set', set(map(tuple, raw[['country', 'id']].values)) == set(map(tuple, clean[['country', 'id']].values)), 'no added or missing keys')
    expected_columns = {'id', 'country', 'cname', 'weight', 'ai_heard_raw', 'ai_heard',
                        'ai_cncexc_raw', 'ai_cncexc', 'aireg_us', 'aireg_china', 'aireg_eu',
                        'aireg_country', 'age', 'age_band_australia', 'age_band_refusers',
                        'gender', 'internetfreq', 'political_scale2', 'political_scale3',
                        'educ_country_code', 'educ_key', 'age_assigned', 'age_from_band',
                        'generation', 'ideology', 'educ_harmonised'}
    check('clean_schema', set(clean.columns) == expected_columns and len(clean.columns) == 26,
          f'expected 26 baseline columns; actual={len(clean.columns)}; missing={sorted(expected_columns-set(clean.columns))}; extra={sorted(set(clean.columns)-expected_columns)}')
    if any(c['status'] == 'FAIL' for c in checks):
        return pd.DataFrame(checks)
    r = raw.set_index(['country', 'id']).sort_index()
    c = clean.set_index(['country', 'id']).sort_index()
    def same(a, b):
        return bool(((a == b) | (a.isna() & b.isna())).all())
    def recode(series, var):
        missing = [k for k, label in labels.get(var, {}).items()
                   if any(s in label.lower() for s in ["don't know", 'don’t know', 'refused'])]
        return series.where(~series.isin(missing))
    check('weight_unchanged', same(r.weight, c.weight), 'exact numeric equality after key join')
    check('weight_valid', np.isfinite(r.weight).all() and (r.weight > 0).all(), f'range={r.weight.min():.8f}..{r.weight.max():.8f}')
    check('country_names', same(r.index.to_frame(index=False).country.map(labels['country']).set_axis(c.index), c.cname), 'SAV value labels')
    for var in QUESTIONS.values():
        check(var + '_raw_exact', same(r[var], c[var + '_raw']), 'all raw answers preserved including 8/9')
        check(var + '_recoding', same(r[var].where(~r[var].isin([8, 9])), c[var]), f'DK/Refused count={int(r[var].isin([8,9]).sum())}')
        check(var + '_valid_codes', r[var].isin([1, 2, 3, 8, 9]).all(), 'no null or unknown raw responses')
    for var in ['aireg_us', 'aireg_china', 'aireg_eu', 'aireg_country']:
        check(var + '_not_sure_preserved', same(r[var].where(r[var] != 9), c[var]), f'code 8 retained n={int((r[var] == 8).sum())}')
    expected_gen = generations(raw, labels).set_axis(pd.MultiIndex.from_frame(raw[['country', 'id']])).sort_index()
    check('generation_thresholds', same(expected_gen, c.generation.replace({'Older': 'Non-Gen Z'})), '18-29 vs 30+; Australia uses wholly contained bands; non-AU age refusals unclassified')
    check('age_recoding', same(r.age.where(~r.age.isin([98, 99])), c.age), '97 remains top-coded; 98/99 missing')
    au_codes = [k for k, v in labels['country'].items() if v == 'Australia']
    au = r.index.get_level_values('country').isin(au_codes)
    check('age_band_australia', same(r.age_australia.where(au), c.age_band_australia), 'original Australia band codes and missingness preserved')
    band_cols = [col for col in raw if col.startswith('d_age_')]
    check('age_band_refusers', same(r[band_cols].bfill(axis=1).iloc[:, 0], c.age_band_refusers), 'country-specific original band codes; no common numeric scale implied')
    assigned = recode(r.age, 'age').copy()
    # Verify the upstream baseline max-endpoint representation without endorsing it as exact age.
    endpoints = {}
    for code, label in labels['age_australia'].items():
        closed = re.fullmatch(r'(\d+)-(\d+)', label)
        opened = re.fullmatch(r'(\d+)\+', label)
        endpoints[code] = float(closed.group(2)) if closed else float(opened.group(1)) if opened else np.nan
    assigned.loc[au] = r.loc[au, 'age_australia'].map(endpoints)
    check('assigned_age_provenance', same(assigned, c.age_assigned), 'baseline exact age outside Australia; max band endpoint in Australia, not an observed exact age')
    check('age_from_band', same(recode(r.age, 'age').isna() & assigned.notna(), c.age_from_band), 'derived band provenance flag exact')
    gender = r.gender.copy()
    gender.loc[au] = recode(r.loc[au, 'gender_australia'], 'gender_australia')
    check('gender_preserved', same(gender, c.gender), 'existing baseline: original non-AU field, Australia-specific recoding; excluded from analysis')
    check('internetfreq_recoding', same(recode(r.internetfreq, 'internetfreq'), c.internetfreq), 'country structural missingness and DK/Refused recoding preserved')
    for var in ['political_scale2', 'political_scale3']:
        check(var + '_direction_and_values', labels[var][0].lower().endswith(('left', 'progressive')) and labels[var][6].lower().endswith(('right', 'conservative')) and same(r[var].where(~r[var].isin([8, 9])), c[var]), '0 left/progressive -> 6 right/conservative; source originals remain in SAV')
    check('ideology_combination', same(c.political_scale2.fillna(c.political_scale3), c.ideology), 'directionally aligned; conceptual equivalence is not established')
    check('education_output_domain', c.educ_harmonised.dropna().isin([1, 2, 3]).all(), 'existing crosswalk preserved; substantive ISCED approval belongs to education owner')
    edu_cols = [col for col in raw if col.startswith('d_educ_') and not col.endswith(('_vocational', '_years'))]
    edu_code = pd.Series(np.nan, index=r.index)
    key_by_country = {}
    for col in edu_cols:
        edu_code = edu_code.fillna(recode(r[col], col))
        for country in r.index.get_level_values('country')[r[col].notna()].unique():
            key_by_country[country] = col.removeprefix('d_educ_')
    edu_key = pd.Series(r.index.get_level_values('country').map(key_by_country), index=r.index)
    check('education_source_code', same(edu_code, c.educ_country_code), 'country-specific original completed-education codes after label-defined missing recoding')
    check('education_country_key', same(edu_key, c.educ_key), 'country-specific education field provenance preserved')
    reference_path = ROOT / 'Data/Output/educ_mapping.csv'
    reference = pd.read_csv(reference_path)
    if reference.duplicated(['country', 'code']).any():
        raise ValueError('Duplicate keys in upstream education mapping reference')
    levels = reference.level.map({'Low (ISCED 0-2)': 1, 'Middle (ISCED 3-4)': 2, 'High (ISCED 5-8)': 3})
    mapping = dict(zip(zip(reference.country, reference.code), levels, strict=True))
    expected_edu = pd.Series([mapping.get((key, code), np.nan) for key, code in zip(edu_key, edu_code, strict=True)], index=r.index)
    check('education_existing_mapping', same(expected_edu, c.educ_harmonised), 'mechanical equality to tracked upstream Data/Output/educ_mapping.csv; not substantive ISCED approval')
    return pd.DataFrame(checks)


def generation_statistics(raw, labels):
    """Optional figures/sensitivity for the age-analysis owner, not a replacement report."""
    rows = []
    for policy, use_bands in [('baseline', False), ('unambiguous_bands_sensitivity', True)]:
        gen = generations(raw, labels, use_bands)
        for country_code, country in labels['country'].items():
            for generation in ['Gen Z', 'Non-Gen Z']:
                g = raw.loc[(raw.country == country_code) & (gen == generation)]
                for q, var in QUESTIONS.items():
                    for metric, positive in ([('Heard a lot', [1]), ('Heard at least a little', [1, 2])] if q == 'Q30' else [('More excited than concerned', [1])]):
                        for denominator in ['all_including_dk', 'substantive_only']:
                            g2 = g if denominator == 'all_including_dk' else g.loc[g[var].isin([1, 2, 3])]
                            if g2.empty:
                                raise ValueError(f'Empty generation denominator: {country}/{generation}')
                            y = g2[var].isin(positive)
                            rows.append(dict(policy=policy, country=country, generation=generation,
                                             question=q, metric=metric, denominator=denominator,
                                             n=len(g2), n_dk=int(g2[var].isin([8, 9]).sum()),
                                             weight_sum=g2.weight.sum(),
                                             weighted_pct=float(100 * g2.loc[y, 'weight'].sum() / g2.weight.sum()),
                                             unweighted_pct=float(100 * y.mean())))
    return pd.DataFrame(rows)


def figures(stats, outdir, awareness='Heard at least a little', suffix=''):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 11, 'axes.labelsize': 11,
                         'xtick.labelsize': 11, 'ytick.labelsize': 11})
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 8.4), sharey=True)
    metrics = [('Q30', awareness, 'A. Awareness\n' + awareness),
               ('Q31', 'More excited than concerned', 'B. Optimism\nMore excited than concerned')]
    filtered = stats.query("policy == 'baseline' and denominator == 'all_including_dk'")
    q30 = filtered.loc[filtered.metric == awareness].pivot(index='country', columns='generation', values='weighted_pct')
    order = (q30['Gen Z'] - q30['Non-Gen Z']).sort_values(ascending=False).index.tolist()
    for ax, (question, metric, title) in zip(axes, metrics, strict=True):
        p = filtered.loc[(filtered.question == question) & (filtered.metric == metric)].pivot(index='country', columns='generation', values='weighted_pct').loc[order]
        for y, (_, row) in enumerate(p.iterrows()):
            ax.plot([row['Non-Gen Z'], row['Gen Z']], [y, y], color='#adb5bd', linewidth=1.6, zorder=1)
        ax.scatter(p['Gen Z'], range(24), color='#0072B2', s=32, label='Gen Z (18-29)', zorder=2)
        ax.scatter(p['Non-Gen Z'], range(24), color='#D55E00', marker='s', s=24, label='Non-Gen Z (30+)', zorder=2)
        ax.set_title(title, loc='left', fontsize=11, weight='bold', pad=12)
        ax.set_xlim(-1, 101)
        ax.set_xticks(range(0, 101, 20))
        ax.set_xlabel('Weighted percent')
        ax.grid(axis='x', alpha=.2)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='y', length=0)
    axes[0].set_yticks(range(24), order)
    axes[0].invert_yaxis()
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='upper center', bbox_to_anchor=(.55, .95),
               ncol=2, frameon=False, fontsize=11)
    fig.suptitle('Generation differences in AI awareness and optimism', x=.02, ha='left', fontsize=13, weight='bold', y=.99)
    fig.text(.02, .025, 'Pew Spring 2025. Weighted within country; all responses include DK/Refused.\nNon-Australian exact-age refusals unclassified; Australia uses age bands.\nCountries ordered by Q30 gap. Descriptive estimates; no significance tests.', fontsize=11)
    fig.tight_layout(rect=(0, .115, 1, .91), w_pad=1)
    fig.savefig(outdir / f'generation_comparison{suffix}.png', dpi=220)
    fig.savefig(outdir / f'generation_comparison{suffix}.svg')
    plt.close(fig)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sensitivity_tables(stats, raw, labels, outdir):
    keys = ['policy', 'country', 'question', 'metric', 'denominator']
    gaps = stats.pivot(index=keys, columns='generation', values=['weighted_pct', 'unweighted_pct', 'n'])
    result = gaps.index.to_frame(index=False)
    for method in ['weighted', 'unweighted']:
        result[method + '_gen_z_pct'] = gaps[(method + '_pct', 'Gen Z')].values
        result[method + '_non_gen_z_pct'] = gaps[(method + '_pct', 'Non-Gen Z')].values
        result[method + '_gap_pp'] = result[method + '_gen_z_pct'] - result[method + '_non_gen_z_pct']
    result['gen_z_n'] = gaps[('n', 'Gen Z')].values.astype(int)
    result['non_gen_z_n'] = gaps[('n', 'Non-Gen Z')].values.astype(int)
    result.to_csv(outdir / 'generation_gaps.csv', index=False)
    idx = ['country', 'generation', 'question', 'metric', 'denominator']
    effects = stats.pivot(index=idx, columns='policy', values='weighted_pct')
    effects['sensitivity_minus_baseline_pp'] = effects.unambiguous_bands_sensitivity - effects.baseline
    effects.to_csv(outdir / 'age_policy_effect.csv')
    idx = ['policy', 'country', 'generation', 'question', 'metric']
    denom = stats.pivot(index=idx, columns='denominator', values='weighted_pct')
    denom['substantive_minus_all_pp'] = denom.substantive_only - denom.all_including_dk
    denom.to_csv(outdir / 'denominator_effect.csv')
    rows = []
    for policy, bands in [('baseline', False), ('unambiguous_bands_sensitivity', True)]:
        gen = generations(raw, labels, bands)
        for code, country in labels['country'].items():
            for group in ['Gen Z', 'Non-Gen Z', 'Unclassified']:
                mask = (raw.country == code) & (gen.isna() if group == 'Unclassified' else gen == group)
                rows.append(dict(policy=policy, country=country, generation=group, n=int(mask.sum())))
    pd.DataFrame(rows).to_csv(outdir / 'generation_counts.csv', index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=SOURCE / 'Pew Research Center Global Attitudes Spring 2025 Dataset.sav')
    parser.add_argument('--clean', type=Path, default=Path('outputs/clean/clean.pkl'))
    parser.add_argument('--topline', type=Path, default=SOURCE / 'Pew Research Center Global Attitudes Spring 2025 Topline.pdf')
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/reproduction'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw, meta = pyreadstat.read_sav(str(args.input))
    # Only load the locally generated pickle from the documented cleaning command.
    clean = pd.read_pickle(args.clean)
    labels = meta.variable_value_labels
    checks = audit(raw, clean, labels)
    checks.to_csv(args.output_dir / 'validation.csv', index=False)
    if (checks.status == 'FAIL').any():
        print(checks.to_string(index=False))
        return 1
    official = parse_topline(args.topline)
    official.to_csv(args.output_dir / 'official_topline_from_pdf.csv', index=False)
    results = topline_comparison(raw, labels, official)
    results.to_csv(args.output_dir / 'topline_comparison.csv', index=False, float_format='%.10f')
    # Reproduce again from the persisted clean raw columns, preventing a raw-only audit claim.
    clean_raw = clean.rename(columns={v: v + '_cleaned' for v in QUESTIONS.values()})
    clean_raw = clean_raw.rename(columns={v + '_raw': v for v in QUESTIONS.values()})
    again = topline_comparison(clean_raw, labels, official)
    pd.testing.assert_frame_equal(results, again)
    example = results.loc[results.country.isin(['Canada', 'Germany', 'India'])]
    example.to_csv(args.output_dir / 'report_three_countries.csv', index=False, float_format='%.4f')
    weight_summary = results.assign(abs_weight_effect=lambda x: x.weighted_minus_unweighted_pp.abs()).groupby(['country', 'question']).agg(n=('n', 'first'), max_abs_weight_effect_pp=('abs_weight_effect', 'max'), weighted_matches=('weighted_matches_official', 'sum'), unweighted_matches=('unweighted_matches_official', 'sum')).reset_index()
    weight_summary.to_csv(args.output_dir / 'weight_effect_by_country.csv', index=False)
    age_inventory(raw, labels).to_csv(args.output_dir / 'age_band_inventory.csv', index=False)
    stats = generation_statistics(raw, labels)
    stats.to_csv(args.output_dir / 'generation_sensitivity.csv', index=False, float_format='%.8f')
    sensitivity_tables(stats, raw, labels, args.output_dir)
    figures(stats, args.output_dir)
    figures(stats, args.output_dir, awareness='Heard a lot', suffix='_a_lot')
    country_counts = raw.groupby('country').size().rename('raw_n').to_frame().join(clean.groupby('country').size().rename('clean_n'))
    country_counts.index = country_counts.index.map(labels['country'])
    country_counts.to_csv(args.output_dir / 'country_counts.csv')
    pd.DataFrame({'raw_variable': raw.columns, 'raw_dtype': [str(raw[c].dtype) for c in raw], 'raw_nulls': [int(raw[c].isna().sum()) for c in raw]}).to_csv(args.output_dir / 'raw_variable_inventory.csv', index=False)
    pd.DataFrame({'clean_variable': clean.columns, 'clean_dtype': [str(clean[c].dtype) for c in clean], 'clean_nulls': [int(clean[c].isna().sum()) for c in clean]}).to_csv(args.output_dir / 'clean_variable_inventory.csv', index=False)
    baseline_gen = generations(raw, labels)
    alternate_gen = generations(raw, labels, True)
    manifest = dict(run_utc=datetime.now(timezone.utc).isoformat(), python=sys.version, platform=platform.platform(),
                    argv=sys.argv, dependencies={x: importlib.metadata.version(x) for x in ['numpy', 'pandas', 'pyreadstat', 'pypdf', 'matplotlib', 'openpyxl']},
                    inputs={(str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p)): sha256(p)
                            for p in [args.input, args.clean, args.topline, Path(__file__), ROOT / 'src/clean.py', ROOT / 'Data/Output/educ_mapping.csv']},
                    dimensions=dict(raw=list(raw.shape), clean=list(clean.shape)),
                    weighted_cells_match=int(results.weighted_matches_official.sum()),
                    unweighted_cells_match=int(results.unweighted_matches_official.sum()),
                    total_cells=len(results),
                    max_abs_weight_effect_pp=float(results.weighted_minus_unweighted_pp.abs().max()),
                    max_abs_weighted_official_pp=float(results.weighted_minus_official_pp.abs().max()),
                    generation_unclassified_baseline=int(baseline_gen.isna().sum()),
                    generation_unclassified_unambiguous_sensitivity=int(alternate_gen.isna().sum()),
                    pending=['Group confirmation of non-Australian band-only policy', 'Education owner approval of existing ISCED crosswalk'],
                    clean_raw_topline_equals_sav=True)
    (args.output_dir / 'run_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ['inputs', 'argv', 'dependencies', 'python', 'platform']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
