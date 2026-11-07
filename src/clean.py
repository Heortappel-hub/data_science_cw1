
"""
COMP5122M Part I - preprocessing (explicit brief requirements only)

Run:  python src/clean.py --output-dir outputs/clean
      Input defaults to the original SAV under Data/sources, independent of the working directory.
Out:  clean.pkl               cleaned data
      data_quality_report.txt data-quality assessment, organised by the five questions from the
                              Week 1 lecture: structure, granularity, scope, temporality, faithfulness
      educ_labels.txt         every country's education codes, to build the harmonisation map

"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

# =====================================================================================
# 小组尚未决定的规则：先保持 None / {}，确定后记入决策日志
# =====================================================================================

# 已决定：只分两组，所有国家统一 18-29 岁 = Gen Z，30 岁及以上 = Older。
# 理由：澳大利亚只有 "18-29" 年龄段，统一用 18-29 才能让 24 国定义一致。
# 与 Pew 标准定义（1997 年后出生，2025 年为 18-28 岁；Dimock 2019）相比多含 29 岁一岁，报告中需说明。
# 格式：(年龄下限, 年龄上限, 组名)
AGE_GROUPS = [(18, 29, "Gen Z"), (30, 120, "Older")]

# 暂行基线：拒绝提供准确年龄的人不进入代际分析；是否使用无歧义年龄段仍待小组确认。
# 复现 topline 时仍保留全部记录；src/reproduce.py 单独给出年龄段敏感性结果。
USE_AGE_BANDS_FOR_REFUSERS = False

# 只有年龄段的人（现在只剩澳大利亚）取区间最大值。澳大利亚的段 18-29 / 30-49 / 50-64 / 65+
# 正好落在 29/30 分界两侧，所以取最大值还是中点，结果都一样
BAND_RULE = "max"                   # "max"：取最大值 / "mid"：取中点

# 已决定：分析不使用性别，此项不影响结果，保留原值
AUSTRALIA_GENDER_OTHER = "keep"

# 已决定：合并两种量表。两者方向一致：0 = 极左 / 极进步，6 = 极右 / 极保守。
# 合并后 ideology 视为"进步—保守"维度；"左—右"与"进步—保守"并非完全相同的概念，报告中需说明
MERGE_IDEOLOGY_SCALES = True

# 已决定：按 ISCED 2011 统一为三级（UNESCO-UIS 2012）：
#   1 = 低：ISCED 0-2（未完成高中）
#   2 = 中：ISCED 3-4（高中、中学后非高等教育）
#   3 = 高：ISCED 5-8（短期高等教育、本科、硕士、博士）
# 98/99（不知道/拒答）不在映射里，自动为缺失。标 [争议] 的需要在报告中写理由。
def _r(a, b, lvl):
    return {k: lvl for k in range(a, b + 1)}

EDU_MAP = {
    # 4 = 中学未完成；5-7 = 中学毕业及未完成的高等教育（最高完成的仍是 ISCED 3）；8 = 非大学高等教育毕业
    "argentina":   {**_r(1, 4, 1), **_r(5, 7, 2), **_r(8, 11, 3)},
    # [争议] 1 "Secondary school or less" 包含 ISCED 0-3，无法拆分 → 归为中；2 Trade/certificate/diploma 跨 ISCED 4-5 → 归为中
    "australia":   {1: 2, 2: 2, 3: 3},
    # 6 = 高中未完成；7 = 高中毕业；8 = 本科未完成（最高完成 ISCED 3）
    "brazil":      {**_r(1, 6, 1), **_r(7, 8, 2), **_r(9, 12, 3)},
    # 6 = 高中毕业；7 = 技工证书；8 = CEGEP 大学预科（ISCED 4）；9 = 社区学院文凭（ISCED 5）
    "canada":      {**_r(1, 5, 1), **_r(6, 8, 2), **_r(9, 11, 3)},
    # 4 = CAP/BEP（职业高中）；5 = Baccalauréat；6-8 = 中学后非高等；9 = BTS/DUT（ISCED 5）
    "france":      {**_r(1, 3, 1), **_r(4, 8, 2), **_r(9, 13, 3)},
    # 2 = 小学或初中；3 = 短轨中学 + 学徒（双元制，ISCED 3）；4 = 长轨中学 / 大学入学资格
    "germany":     {**_r(1, 2, 1), **_r(3, 4, 2), **_r(5, 7, 3)},
    # 4 = 初中证书；5 = 职业高中 EPAL；6 = 普通高中；7 = IEK 职业培训学院（ISCED 4）
    "greece":      {**_r(1, 4, 1), **_r(5, 7, 2), **_r(8, 12, 3)},
    # 4 = 职业学校（ISCED 3）；5-7 = 高中会考 / 中学后职业培训；8 = 高等技术学校（ISCED 5）
    "hungary":     {**_r(1, 3, 1), **_r(4, 7, 2), **_r(8, 11, 3)},
    # 5 "High School" = 10 年级：印度官方对照 InSCED 2014 归为 ISCED 3（341，不足以完成该级），
    # Eurostat 学历统计把 ISCED 3 的部分完成仍计为 3 级 → 中；6 = 12 年级；7-8 = 技术/专业培训文凭（ISCED 3-4）
    "india":       {**_r(1, 4, 1), **_r(5, 8, 2), **_r(9, 11, 3)},
    # 6 = 高中未完成；7 = 高中毕业；8 = DI-DIII 文凭（ISCED 5）
    "indonesia":   {**_r(1, 6, 1), 7: 2, **_r(8, 12, 3)},
    # [争议] 5-6 = 高中 / 宗教学校完成但无会考证书，仍按 ISCED 3 → 中；11 = 中学后技术员/师范文凭（ISCED 5）；12 = Kolel 宗教进修，无学位 → 中
    "israel":      {**_r(1, 4, 1), **_r(5, 10, 2), 11: 3, 12: 2, **_r(13, 15, 3)},
    # 4 = 高中文凭；5 = 高中后职业专业化（ISCED 4）；6 = 三年制学位
    "italy":       {**_r(1, 3, 1), **_r(4, 5, 2), **_r(6, 8, 3)},
    # 4 = 高中；5 = 高等专门学校；6 = 短期大学 / 专门学校（ISCED 5）
    "japan":       {**_r(1, 3, 1), 4: 2, **_r(5, 9, 3)},
    # [争议] 6 = 青年技工学校（小学后，ISCED 3 职业）；9 TIVET、10 师范/理工学院 跨 ISCED 4-5 → 归为中
    "kenya":       {**_r(1, 5, 1), **_r(6, 10, 2), **_r(11, 13, 3)},
    # 5 = 初中 secundaria 毕业（ISCED 2）；6-9 = 高中 bachillerato / 职业高中；10 = 大学
    "mexico":      {**_r(1, 5, 1), **_r(6, 9, 2), **_r(10, 12, 3)},
    # 3 = MBO 1 入门级（ISCED 2）；5 = HAVO/VWO；6-7 = MBO 2-4；8 = HBO/WO 本科
    "netherlands": {**_r(1, 4, 1), **_r(5, 7, 2), **_r(8, 10, 3)},
    # 5 = 高中；6 = 中等技术学校；7 = 国家文凭 / NCE（ISCED 5）
    "nigeria":     {**_r(1, 4, 1), **_r(5, 6, 2), **_r(7, 11, 3)},
    # 3 = 初中；4 = 职业学校；5-6 = 普通 / 技术高中；7 = 中学后学校（ISCED 4）
    "poland":      {**_r(1, 3, 1), **_r(4, 7, 2), **_r(8, 10, 3)},
    # [争议] 7 = NSC 高中毕业；8 = NC(V)；9-11 NATED N4-N6 是高中后职业证书，跨 ISCED 4-5 → 归为中；12 起为高等教育
    "safrica":     {**_r(1, 6, 1), **_r(7, 11, 2), **_r(12, 20, 3)},
    # 5 = 职业高中；6 = 普通高中；7 = 专科 / 理工学院（ISCED 5）
    "skorea":      {**_r(1, 4, 1), **_r(5, 6, 2), **_r(7, 10, 3)},
    # 5 = 初中阶段；6 = 中级职业教育（ISCED 3）；7 = 高中 Bachillerato；8 = 高级职业培训（ISCED 5）
    "spain":       {**_r(1, 5, 1), **_r(6, 7, 2), **_r(8, 12, 3)},
    # 4 = 高中；5 = 成人国立学校；6 = 高级职业培训 2-3 年（Yrkeshögskola，ISCED 5）
    "sweden":      {**_r(1, 3, 1), **_r(4, 5, 2), **_r(6, 10, 3)},
    # 5-6 = 初中；7 = 高中；8 = 职业高中；9 = 两年制专科或四年制大学
    "turkey":      {**_r(1, 6, 1), **_r(7, 8, 2), **_r(9, 11, 3)},
    # [争议] 3 = GCSE（"any grades"）：同级的苏格兰 National 5 官方归为 ISCED 3 → 中；但低分 GCSE 属 ISCED 2
    # 4 = A-level；5 = NVQ4 / HNC（RQF 4 = ISCED 5）
    "uk":          {**_r(1, 2, 1), **_r(3, 4, 2), **_r(5, 9, 3)},
}

# =====================================================================================
# 官方参考信息：用于核对国家覆盖范围与调查时间，不来自 data.sav
# 来源：Pew Research Center（2025），春季调查方法说明
# https://www.pewresearch.org/wp-content/uploads/sites/20/2025/06/SR_25.06.03_views-of-israel_methodology.pdf
# 每个国家依次记录：官方样本量、调查日期、调查方式、设计效应
# =====================================================================================
OFFICIAL = {
    "Canada": (1024, "Feb 19-Apr 15", "Telephone", 1.36),   "France": (1006, "Feb 7-Apr 24", "Telephone", 1.65),
    "Germany": (1006, "Feb 27-Apr 11", "Telephone", 1.33),  "Greece": (1010, "Feb 24-Apr 11", "Telephone", 1.93),
    "Hungary": (1020, "Feb 18-Apr 1", "Telephone", 1.48),   "Italy": (1007, "Feb 7-Apr 26", "Telephone", 2.18),
    "Netherlands": (1000, "Feb 7-Apr 19", "Telephone", 1.58), "Poland": (1002, "Feb 18-Apr 11", "Telephone", 1.55),
    "Spain": (1001, "Feb 7-Apr 18", "Telephone", 1.80),     "Sweden": (1001, "Feb 24-Apr 13", "Telephone", 1.50),
    "UK": (1006, "Feb 7-Apr 13", "Telephone", 1.78),        "Australia": (1829, "Mar 17-31", "Online panel", 1.21),
    "India": (3545, "Feb 7-Apr 21", "Face-to-face", 3.20),  "Indonesia": (1022, "Jan 8-Feb 23", "Face-to-face", 2.23),
    "Japan": (1006, "Feb 6-Apr 7", "Telephone", 1.47),      "South Korea": (1042, "Feb 28-Mar 29", "Telephone", 1.65),
    "Israel": (998, "Feb 5-Mar 11", "Face-to-face", 1.68),  "Turkey": (1048, "Jan 31-Mar 3", "Face-to-face", 2.10),
    "Kenya": (1049, "Feb 22-Mar 15", "Face-to-face", 2.44), "Nigeria": (1037, "Feb 21-Apr 10", "Face-to-face", 1.90),
    "South Africa": (1570, "Feb 21-Mar 30", "Face-to-face", 1.89), "Argentina": (1001, "Feb 10-Apr 13", "Face-to-face", 1.73),
    "Brazil": (1053, "Feb 20-Apr 7", "Face-to-face", 2.12), "Mexico": (1050, "Feb 12-Mar 25", "Face-to-face", 2.09),
}

# =====================================================================================
# 0. 读取原始数据
# =====================================================================================
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path,
                    default=Path(__file__).resolve().parents[1] / "Data" / "sources" /
                    "Pew Research Center Global Attitudes Spring 2025 Dataset.sav")
parser.add_argument("--output-dir", type=Path, default=Path("outputs/clean"))
args = parser.parse_args()
args.output_dir.mkdir(parents=True, exist_ok=True)
df, meta = pyreadstat.read_sav(str(args.input))
LABELS = meta.variable_value_labels
COUNTRY = {int(k): v for k, v in LABELS["country"].items()}
N_ROWS_IN, N_COLS_RAW = df.shape
AU = df["country"] == 13


def missing_codes(var):
    """Codes whose value label says Don't know / Refused (covers 8, 9, 98, 99). 'Not sure' is NOT included."""
    labs = LABELS.get(var, {})
    return [k for k, l in labs.items()
            if any(s in l.lower() for s in ["don't know", "don’t know", "refused"])]


def to_missing(s, var):
    return s.where(~s.isin(missing_codes(var)))


report = []
def log(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    report.append(line)


# =====================================================================================
# 1. 数据质量检查
# =====================================================================================
CORE = ["ai_heard", "ai_cncexc", "aireg_us", "aireg_china", "aireg_eu", "aireg_country"]
edu_all = sorted(c for c in df.columns if c.startswith("d_educ_"))
SUPPLEMENTARY = ("_vocational", "_years")      
edu_cols = [c for c in edu_all if not c.endswith(SUPPLEMENTARY)]

# 1.1 数据结构：有多少行和列，各国变量是否分散存放
log("=== 1.1 STRUCTURE ===")
log(f"Rectangular table: {N_ROWS_IN} rows x {N_COLS_RAW} columns (SPSS .sav with value labels)")
asked_all = [c for c in df.columns if df.groupby("country")[c].apply(lambda s: s.notna().any()).all()]
n_d = sum(c.startswith("d_") for c in df.columns)
log(f"Columns with data in all 24 countries: {len(asked_all)}")
log(f"Untidy layout ('column headers are values'): {n_d} d_* columns hold one variable per COUNTRY,")
log(f"  e.g. education is spread over {len(edu_all)} columns ({len(edu_cols)} main + Germany/Israel supplementary);"
    " each row has at most one non-empty d_educ_* main column")
log(f"  check: rows with >1 main education column filled = {(df[edu_cols].notna().sum(axis=1) > 1).sum()}")
log("Missing values are stored as numeric sentinel codes (8, 9, 98, 99), not as blanks;"
    " left as-is they would be read as real, very large answers")
sent = {v: sorted(int(k) for k in missing_codes(v)) for v in ["ai_heard", "ai_cncexc", "age", "d_educ_uk"]}
log(f"  sentinel codes found via value labels: {sent}")
log("Q32 code 8 is labelled 'Not sure' (a real answer), so a blanket 'recode 8 to missing' would be wrong")

# 1.2 数据粒度：一行代表谁，编号有没有重复
log("\n=== 1.2 GRANULARITY ===")
log("One row = one respondent (individual level).")
log(f"Primary key (country, id) unique: {not df.duplicated(['country', 'id']).any()};"
    f" id unique on its own: {not df['id'].duplicated().any()}")
log(f"Weights differ by row (range {df.weight.min():.3f}-{df.weight.max():.2f}, mean 1.00 within every country):"
    " each row stands for a different number of people; each country's weights sum to its sample size,"
    " NOT to its population (India n = 3,545 would count 3.5x a typical country if countries are pooled)")

# 1.3 覆盖范围：国家和样本是否齐全，人数是否够用
log("\n=== 1.3 SCOPE ===")
n_by = df.groupby(df["country"].astype(int).map(COUNTRY)).size()
off_n = pd.Series({c: v[0] for c, v in OFFICIAL.items()})
cmp = pd.DataFrame({"in_file": n_by, "official": off_n})
cmp["diff"] = cmp["in_file"] - cmp["official"]
log(f"Rows in file vs Pew's published sample sizes (\"how many rows should be here?\"):"
    f" total {cmp.in_file.sum()} vs {cmp.official.sum()}; countries with a mismatch: "
    f"{list(cmp.index[cmp['diff'] != 0]) or 'none'}")
log("24 countries; the U.S. (part of Pew's 25-country AI report) is a separate survey and is NOT in this file")
log("Population: adults 18+ only; national samples, but 'national' differs (see Pew methodology for coverage limits)")
age_raw = df["age"].where(df["age"] <= 97)
young_n = (age_raw <= 29) | (AU & (df["age_australia"] == 1))
yn = young_n.groupby(df["country"].astype(int).map(COUNTRY)).sum().sort_values()
log("Enough data for the question? respondents aged 18-29 per country (smallest five):")
log("  " + ", ".join(f"{c} {int(n)}" for c, n in yn.head(5).items()))
log("Not enough for some questions: Australia has no exact age (bands only) and no internet use;"
    " ideology not asked in India, Indonesia, Kenya")

# 1.4 时间范围：调查是什么时候进行的
log("\n=== 1.4 TEMPORALITY ===")
log(f"Single wave: 'survey' = {sorted(set(LABELS['survey'].values()))}; the file has NO interview-date variable")
log("Fieldwork (from Pew methodology, outside the file): Jan 8 - Apr 26 2025; window differs by country, e.g.")
log("  Indonesia " + OFFICIAL["Indonesia"][1] + " | Turkey " + OFFICIAL["Turkey"][1]
    + " | Australia " + OFFICIAL["Australia"][1] + " | Italy " + OFFICIAL["Italy"][1])
log("Implication: opinions on a fast-moving technology are a snapshot of early 2025; cross-country"
    " differences may partly reflect timing")

# 1.5 数据可靠性：是否符合问卷编码，有没有异常值
log("\n=== 1.5 FAITHFULNESS ===")
log("Values outside the codebook (unrealistic / 'incorrect' values):")
for v in CORE + ["gender", "gender_australia", "age_australia", "internetfreq",
                 "political_scale2", "political_scale3"] + edu_cols:
    bad = set(df[v].dropna().unique()) - set(LABELS.get(v, {}).keys())
    if bad or v in CORE:
        log(f"  {v:20s} {sorted(bad) if bad else 'none'}")
log(f"  also checked (gender, gender_australia, age_australia, internetfreq, political_scale2/3,"
    f" {len(edu_cols)} education columns): any problem would be listed above")
log(f"Age: valid range {age_raw.min():.0f}-{age_raw.max():.0f}; 97 is TOP-CODED ('97 or older'), so not an exact age;"
    f" n aged 97+ = {(df['age'] == 97).sum()}")
log(f"Duplicated answer patterns (all columns except id) = {df.drop(columns='id').duplicated().sum()}"
    " -> no sign of copied/fabricated records")
w_hi = df.groupby(df["country"].astype(int).map(COUNTRY))["weight"].max().sort_values(ascending=False)
log("Large weights (outliers): largest per country, top 3: " + ", ".join(f"{c} {v:.2f}" for c, v in w_hi.head(3).items()))
log("Design effects from Pew (variance inflation from weighting/clustering): "
    + ", ".join(f"{c} {OFFICIAL[c][3]}" for c in ["India", "Kenya", "Indonesia", "Australia", "Germany"]))
log("Survey mode differs (telephone / face-to-face / online panel), which can change how often people say 'don't know':")
mode = df["country"].astype(int).map(COUNTRY).map({c: v[2] for c, v in OFFICIAL.items()})
dk31 = df["ai_cncexc"].isin(missing_codes("ai_cncexc"))
log("  Q31 DK/Refused by mode: " + ", ".join(f"{m} {v:.1f}%" for m, v in (dk31.groupby(mode).mean() * 100).items()))

# 1.6 缺失值：缺失多少，为什么缺失
log("\n=== 1.6 MISSING DATA (lecture: 'Essential question: why are the records missing?') ===")
dk = pd.DataFrame({v: df.groupby(df["country"].astype(int).map(COUNTRY))[v]
                   .apply(lambda s: s.isin(missing_codes(v)).mean() * 100) for v in CORE})
dk["aireg_country_NOTSURE"] = df.groupby(df["country"].astype(int).map(COUNTRY))["aireg_country"].apply(lambda s: (s == 8).mean() * 100)
log("% DK/Refused per country (and % 'Not sure' on Q32d, which is NOT missing):")
log(dk.round(1).to_string())
log("Is missingness related to something of interest? (if yes, dropping DK can bias results)")
heard = df["ai_heard"].map({1: "Q30 a lot", 2: "Q30 a little", 3: "Q30 nothing", 8: "Q30 DK/Ref", 9: "Q30 DK/Ref"})
log("  Q31 DK/Refused rate by Q30 answer: "
    + ", ".join(f"{k} {v:.1f}%" for k, v in (dk31.groupby(heard).mean() * 100).items()))
log(f"  mean age of Q31 DK/Refused = {age_raw[dk31 & ~AU].mean():.1f} vs answered = {age_raw[~dk31 & ~AU].mean():.1f}"
    " (exact-age countries)")
log("Structural missingness (variable not asked / stored elsewhere):")
for v in ["age", "gender", "internetfreq", "political_scale2", "political_scale3"]:
    none = df.groupby(df["country"].astype(int).map(COUNTRY))[v].apply(lambda s: s.notna().mean() == 0)
    log(f"  {v:18s} absent for: {list(none[none].index) or '-'}")
log(f"  exact age DK/Refused outside Australia (only a band in d_age_*): {int((df['age'].isin([98, 99]) & ~AU).sum())}")

# 导出各国教育编码，供填写 EDU_MAP 时参考
with open(args.output_dir / "educ_labels.txt", "w", encoding="utf-8") as f:
    for c in edu_all:
        f.write(f"## {c}  (n = {df[c].notna().sum()})\n")
        for k, l in LABELS.get(c, {}).items():
            f.write(f"  {int(k):3d}  {l}\n")

df["cname"] = df["country"].astype(int).map(COUNTRY)

# =====================================================================================
# 2. 按作业要求进行基础清洗
# =====================================================================================
out = df[["id", "country", "cname", "weight"]].copy()   # 原样保留权重；如何使用权重由小组决定

# 2a. AI 了解程度与态度：不知道/拒答设为缺失，同时保留原始答案
for v in ["ai_heard", "ai_cncexc"]:
    out[v + "_raw"] = df[v]
    out[v] = to_missing(df[v], v)

# 2b. AI 监管问题：只有拒答(9)设为缺失；不确定(8)是有效答案
for v in ["aireg_us", "aireg_china", "aireg_eu", "aireg_country"]:
    out[v] = df[v].where(df[v] != 9)

# 2c. 年龄：98/99 设为缺失，97 表示“97 岁及以上”
# 澳大利亚只有年龄段，单独保留
out["age"] = to_missing(df["age"], "age")
out["age_band_australia"] = df["age_australia"].where(AU)
age_band_cols = [c for c in df.columns if c.startswith("d_age_")]
out["age_band_refusers"] = df[age_band_cols].bfill(axis=1).iloc[:, 0]   # 各国年龄段的数字编码并不完全相同

# 2d. 性别：澳大利亚使用单独字段；不知道/拒答设为缺失
g = df["gender"].copy()
g[AU] = to_missing(df.loc[AU, "gender_australia"], "gender_australia")
out["gender"] = g          # 1 男，2 女，3 其他（仅澳大利亚）

# 2e. 上网频率：不知道/拒答设为缺失；澳大利亚未问此题
out["internetfreq"] = to_missing(df["internetfreq"], "internetfreq")

# 2f. 政治倾向：保留两种量表；印度、印尼、肯尼亚未问
for v in ["political_scale2", "political_scale3"]:
    out[v] = to_missing(df[v], v)

# 2g. 教育：把各国不同的教育列整合为一列，并记录所属国家的编码体系
# 不知道/拒答设为缺失；统一映射前，各国数字编码不能直接比较
edu_raw = pd.Series(np.nan, index=df.index)
for c in edu_cols:
    edu_raw = edu_raw.fillna(to_missing(df[c], c))
out["educ_country_code"] = edu_raw
key_of = {}
for c in edu_cols:
    key_of.update({cn: c.replace("d_educ_", "") for cn in df.loc[df[c].notna(), "cname"].unique()})
out["educ_key"] = out["cname"].map(key_of)

# =====================================================================================
# 3. 需要小组决定后才能生成的变量；未填写的规则先跳过
# =====================================================================================
pending = []

def band_to_age(label, rule):
    """把年龄段标签换成一个年龄：'30-49' → 49（max）或 39.5（mid）；开放区间 '65+' → 65（下限）。"""
    if not isinstance(label, str) or not label[:1].isdigit():
        return np.nan
    if label.endswith("+"):
        return float(label[:-1])
    lo, hi = (float(x) for x in label.split("-"))
    return hi if rule == "max" else (lo + hi) / 2


def assign_age(rule):
    age = out["age"].copy()                                  # 有准确年龄的人
    au_lab = df["age_australia"].map(LABELS["age_australia"])
    age[AU] = au_lab[AU].map(lambda l: band_to_age(l, rule))  # 澳大利亚：只有年龄段
    if USE_AGE_BANDS_FOR_REFUSERS:                           # 拒答准确年龄、但回答了年龄段的人
        for c in age_band_cols:
            lab = df[c].map(LABELS.get(c, {}))               # 98/99 的标签不是数字开头，自动为缺失
            m = age.isna() & lab.notna()
            age[m] = lab[m].map(lambda l: band_to_age(l, rule))
    return age


if AGE_GROUPS:
    bins = [AGE_GROUPS[0][0] - 1] + [hi for _, hi, _ in AGE_GROUPS]
    names = [l for *_, l in AGE_GROUPS]
    out["age_assigned"] = assign_age(BAND_RULE)              # 准确年龄，或由年龄段推算的年龄
    out["age_from_band"] = out["age"].isna() & out["age_assigned"].notna()
    out["generation"] = pd.cut(out["age_assigned"], bins, labels=names).astype(object)

    log(f"\n=== 3. GENERATIONS (band rule = {BAND_RULE}) ===")
    log(f"age taken from a band: {int(out['age_from_band'].sum())} respondents"
        f" (Australia {int(out.loc[AU, 'age_from_band'].sum())}, refusers {int(out.loc[~AU, 'age_from_band'].sum())});"
        f" generation missing: {int(out['generation'].isna().sum())}")
    tab = pd.crosstab(out["cname"], out["generation"])[names]
    log(tab.to_string())
    other = "mid" if BAND_RULE == "max" else "max"
    alt = pd.cut(assign_age(other), bins, labels=names).astype(object)
    log(f"compare: Gen Z n in Australia = {int((out.loc[AU, 'generation'] == 'Gen Z').sum())} ({BAND_RULE})"
        f" vs {int((alt[AU] == 'Gen Z').sum())} ({other});"
        f" respondents whose generation changes between rules = "
        f"{int(((alt != out['generation']) & ~(alt.isna() & out['generation'].isna())).sum())}")
else:
    pending.append("AGE_GROUPS")

if AUSTRALIA_GENDER_OTHER == "missing":
    out.loc[out["gender"] == 3, "gender"] = np.nan
elif AUSTRALIA_GENDER_OTHER is None:
    pending.append("AUSTRALIA_GENDER_OTHER")

if MERGE_IDEOLOGY_SCALES is True:
    out["ideology"] = out["political_scale2"].fillna(out["political_scale3"])
elif MERGE_IDEOLOGY_SCALES is None:
    pending.append("MERGE_IDEOLOGY_SCALES")

if EDU_MAP:
    lvl = pd.Series(np.nan, index=out.index)
    for key, mp in EDU_MAP.items():
        m = out["educ_key"] == key
        lvl[m] = out.loc[m, "educ_country_code"].map(mp)
    out["educ_harmonised"] = lvl
    missing_keys = sorted(set(key_of.values()) - set(EDU_MAP))
    if missing_keys:
        pending.append(f"EDU_MAP missing countries: {missing_keys}")
else:
    pending.append("EDU_MAP (education harmonisation)")

pending.append("survey weights: whether/how to use (analysis step, not here)")

# =====================================================================================
# 4. 流程检查：确认清洗前后没有丢失受访者记录
# =====================================================================================
assert len(out) == N_ROWS_IN, f"lost {N_ROWS_IN - len(out):,} records"
assert out.groupby("cname").size().to_dict() == n_by.to_dict(), "per-country row counts changed"
log(f"\n=== 4. PIPELINE CHECK ===\nrows in = {N_ROWS_IN}, rows out = {len(out)}: no records lost")

out.to_pickle(args.output_dir / "clean.pkl")
out.to_csv(args.output_dir / "clean.csv", index=False, encoding="utf-8-sig")

# 教育映射对照表：国家 / 原始编码 / 原文标签 / 统一等级，供报告写映射理由
LEVEL_NAME = {1: "Low (ISCED 0-2)", 2: "Middle (ISCED 3-4)", 3: "High (ISCED 5-8)"}
rows = []
for c in edu_cols:
    key = c.replace("d_educ_", "")
    for code, lab in LABELS.get(c, {}).items():
        lvl = EDU_MAP.get(key, {}).get(int(code))
        rows.append(dict(country=key, code=int(code), label=lab,
                         level=LEVEL_NAME.get(lvl, "Missing (DK/Refused)"),
                         n=int((df[c] == code).sum())))
pd.DataFrame(rows).to_csv(args.output_dir / "educ_mapping.csv", index=False, encoding="utf-8-sig")
with open(args.output_dir / "data_quality_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print(f"\nSaved clean.pkl, clean.csv, data_quality_report.txt, educ_labels.txt, educ_mapping.csv to {args.output_dir}")
print("Decisions still open (record each in the decision log):")
for p in pending:
    print("  -", p)
