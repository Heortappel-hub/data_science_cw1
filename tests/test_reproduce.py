import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def module():
    import reproduce
    return reproduce


def test_weighted_denominator_keeps_dk_and_refused():
    # Dropping 8/9 would incorrectly produce 100% rather than 10% for code 1.
    got = module().proportions(pd.Series([1, 8, 9]), pd.Series([1., 4., 5.]))
    assert got[1] == pytest.approx((10., 100 / 3))
    assert got[8] == pytest.approx((90., 200 / 3))
    assert got[2] == (0., 0.)


@pytest.mark.parametrize('answers,weights', [
    ([1, 7], [1, 1]), ([1, np.nan], [1, 1]),
    ([1, 2], [1, 0]), ([1, 2], [1, np.nan]), ([1, 2], [1, np.inf]),
])
def test_invalid_inputs_cannot_silently_change_denominator(answers, weights):
    with pytest.raises(ValueError):
        module().proportions(pd.Series(answers), pd.Series(weights))


def test_half_up_rounding():
    assert module().round_percent(12.5) == 13
    assert module().round_percent(0.5) == 1


@pytest.mark.parametrize('label,want', [
    ('18-29', 'Gen Z'), ('30-49', 'Non-Gen Z'), ('65+', 'Non-Gen Z'),
    ('18-24', 'Gen Z'), ('25-34', None), ('25-44', None),
    ('Refused (DO NOT READ)', None), ('17-25', None),
])
def test_age_band_must_lie_wholly_within_one_group(label, want):
    assert module().band_generation(label) == want


def test_generation_uses_exact_age_before_bands():
    raw = pd.DataFrame({'country': [2, 2, 2, 13], 'age': [29, 30, 99, np.nan],
                        'age_australia': [np.nan, np.nan, np.nan, 1],
                        'd_age_canada': [np.nan, np.nan, 2, np.nan]})
    labels = {'country': {2: 'Canada', 13: 'Australia'},
              'age_australia': {1: '18-29'}, 'd_age_canada': {2: '30-39'}}
    base = module().generations(raw, labels)
    assert base.iloc[[0, 1, 3]].tolist() == ['Gen Z', 'Non-Gen Z', 'Gen Z']
    assert pd.isna(base.iloc[2])
    assert module().generations(raw, labels, use_unambiguous_bands=True).iloc[2] == 'Non-Gen Z'


def test_topline_column_order_and_combined_dk_from_real_pdf():
    root = Path(__file__).resolve().parents[1]
    got = module().parse_topline(root / 'Data/sources/Pew Research Center Global Attitudes Spring 2025 Topline.pdf')
    assert len(got) == 192
    assert got.query("country == 'India' and question == 'Q30'").official_pct.tolist() == [14, 32, 35, 19]
    assert got.query("country == 'Canada' and question == 'Q31'").official_pct.tolist() == [9, 45, 45, 1]
    assert set(got.pdf_page) == {48}


def test_incomplete_pdf_extraction_is_rejected():
    with pytest.raises(ValueError):
        module().parse_topline_text('Q30.\nCanada Spring, 2025\n41 51 8 0 100\nQ31.')


@pytest.fixture(scope='module')
def actual_data():
    import pyreadstat
    root = Path(__file__).resolve().parents[1]
    raw, meta = pyreadstat.read_sav(str(root / 'Data/sources/Pew Research Center Global Attitudes Spring 2025 Dataset.sav'))
    clean = pd.read_csv(root / 'Data/Output/clean.csv')
    return raw, clean, meta.variable_value_labels


def test_audit_uses_keys_rather_than_row_order(actual_data):
    raw, clean, labels = actual_data
    checks = module().audit(raw, clean.sample(frac=1, random_state=1), labels)
    assert not (checks.status == 'FAIL').any()


@pytest.mark.parametrize('mutation,failed_check', [
    ('drop', 'total_records'), ('duplicate', 'clean_primary_key'),
    ('weight', 'weight_unchanged'), ('raw_answer', 'ai_heard_raw_exact'),
    ('cleaned_answer', 'ai_cncexc_recoding'), ('q32_not_sure', 'aireg_us_not_sure_preserved'),
    ('education_missing', 'education_existing_mapping'), ('education_code', 'education_source_code'),
    ('age_assigned', 'assigned_age_provenance'), ('age_flag', 'age_from_band'),
    ('age_band', 'age_band_refusers'), ('gender', 'gender_preserved'),
    ('internet', 'internetfreq_recoding'),
])
def test_audit_detects_actual_data_corruption(actual_data, mutation, failed_check):
    raw, baseline, labels = actual_data
    clean = baseline.copy()
    if mutation == 'drop':
        clean = clean.iloc[1:]
    elif mutation == 'duplicate':
        clean.loc[1, ['country', 'id']] = clean.loc[0, ['country', 'id']].values
    elif mutation == 'weight':
        clean.loc[0, 'weight'] += .01
    elif mutation == 'raw_answer':
        clean.loc[0, 'ai_heard_raw'] = 7
    elif mutation == 'cleaned_answer':
        clean.loc[clean.ai_cncexc_raw.isin([8, 9]), 'ai_cncexc'] = 3
    elif mutation == 'q32_not_sure':
        clean.loc[clean.aireg_us == 8, 'aireg_us'] = np.nan
    elif mutation == 'education_missing':
        clean['educ_harmonised'] = np.nan
    elif mutation == 'education_code':
        clean['educ_country_code'] = 999
    elif mutation == 'age_assigned':
        clean['age_assigned'] = 20
    elif mutation == 'age_flag':
        clean['age_from_band'] = False
    elif mutation == 'age_band':
        clean['age_band_refusers'] = 999
    elif mutation == 'gender':
        clean['gender'] = 99
    elif mutation == 'internet':
        clean['internetfreq'] = 999
    checks = module().audit(raw, clean, labels).set_index('check')
    assert checks.loc[failed_check, 'status'] == 'FAIL'


def test_extra_country_cannot_disappear_in_official_merge(actual_data):
    from copy import deepcopy
    raw, _, baseline_labels = actual_data
    labels = deepcopy(baseline_labels)
    labels['country'][999] = 'Unexpected country'
    extra = raw.iloc[[0]].copy()
    extra['country'] = 999
    raw = pd.concat([raw, extra], ignore_index=True)
    official = module().parse_topline(Path(__file__).resolve().parents[1] / 'Data/sources/Pew Research Center Global Attitudes Spring 2025 Topline.pdf')
    with pytest.raises(ValueError, match='country|countries'):
        module().topline_comparison(raw, labels, official)
