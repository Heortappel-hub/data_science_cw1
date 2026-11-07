import subprocess
import sys
from pathlib import Path

import pandas as pd


def test_cleaner_runs_from_arbitrary_cwd_and_persists_sav_values(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'src/clean.py'),
                             '--output-dir', str(tmp_path / 'cleaned')],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    clean = pd.read_pickle(tmp_path / 'cleaned/clean.pkl')
    assert clean.shape == (28333, 26)
    assert not clean.duplicated(['country', 'id']).any()
    assert int(clean.ai_heard_raw.isin([8, 9]).sum()) == int(clean.ai_heard.isna().sum())
