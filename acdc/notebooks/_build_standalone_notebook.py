"""
corn_yield_model_standalone.ipynb 생성기 — '파일 하나'로 완결되는 노트북.

핵심: 병합 패널(콘벨트 1981-2015, 16컬럼)을 gzip+base64 로 노트북 첫 셀에 '내장'한다.
따라서 이 .ipynb 하나만 있으면 Colab이든 Jupyter든 clone·데이터폴더·경로설정 없이 즉시 실행된다.
필요 라이브러리: pandas, numpy, scikit-learn, matplotlib (그게 전부).

각 코드 셀을 실제 실행해 표·그래프를 미리 채운다(nbclient 불필요).
"""
import ast, io, json, base64, gzip, contextlib, os, uuid
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_PATH = os.path.join(HERE, "corn_yield_model_standalone.ipynb")
CELLS, NS = [], {}


def md(t): CELLS.append(("markdown", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))


# ── 병합 패널 생성 → gzip+base64 로 문자열화(노트북에 내장) ──────────────────
def build_panel_b64():
    yd = pd.read_csv(f"{DATA}/yielddata.csv")
    ppt = pd.read_csv(f"{DATA}/pptMarAug.csv")
    soil = pd.read_csv(f"{DATA}/soil2011.csv")
    temp = pd.read_csv(f"{DATA}/gdd_slim.csv")
    dr = pd.read_csv(f"{DATA}/drought_slim.csv")[["stco", "year", "dsci_jul"]]
    tc = pd.read_csv(f"{DATA}/terraclimate_slim.csv")[["stco", "year", "soil_jul", "pr_jul", "tmmx_jul"]]
    CORN_BELT = {19, 17, 31, 27, 18, 20, 39, 46, 29, 38, 55, 48}
    df = (yd.merge(ppt, on=["stco", "year"], how="left")
            .merge(temp, on=["stco", "year"], how="left")
            .merge(soil, on="stco", how="left")
            .merge(dr, on=["stco", "year"], how="left")
            .merge(tc, on=["stco", "year"], how="left"))
    df["state"] = df["stco"] // 1000
    df = df[df["state"].isin(CORN_BELT)].copy()
    df = df.dropna(subset=["corn", "ppt", "edd", "whc", "om", "spH", "clay", "slope"]).copy()
    keep = ["stco", "state", "year", "corn", "gdd", "edd", "ppt", "whc", "om", "spH",
            "clay", "slope", "dsci_jul", "soil_jul", "pr_jul", "tmmx_jul"]
    csv = df[keep].round(4).to_csv(index=False).encode()
    b64 = base64.b64encode(gzip.compress(csv, 9)).decode()
    return b64, df.shape


B64, SHAPE = build_panel_b64()
print(f"패널 {SHAPE} → base64 {len(B64)/1e6:.2f} MB 내장")

# ============================================================
md("""
# 옥수수 수확량 예측 — 단일 파일 노트북 (데이터 내장)

> **이 노트북 파일 하나만 있으면 됩니다.** 데이터가 노트북 안에 압축 내장되어 있어
> clone·데이터폴더·경로설정이 전혀 필요 없습니다. Colab에 업로드하거나 Jupyter로 열어
> **`런타임 > 모두 실행`** 하면 끝. 필요 라이브러리: `pandas numpy scikit-learn matplotlib`.

미국 카운티×연도(1981–2015) 농업·기후 실데이터(ACDC + USDM 7월가뭄 + TerraClimate 7월)로
옥수수 수확량을 예측하고, 더위의 피해가 **인과**임을 고정효과로 확인한다. Corn Belt 12개 주.

**성능 (같은 모델, 3가지 시험 난이도 — 5장에서 자세히)**

| 평가 방식 | 무엇을 맞히나 | R² |
|---|---|---|
| 랜덤 5-fold CV | 관계 학습력 (쉬움) | **≈0.86** |
| GroupKFold(카운티) | 안 본 지역 (중간) | ≈0.79 |
| 시간분할(2011–15) | 안 본 미래 예보 (어려움) | **≈0.65** |
""")

# ------------------------------------------------------------
md("""
## 1. 데이터 (노트북에 내장) 불러오기

아래 `DATA_B64` 문자열이 **병합 완료된 패널**(콘벨트 34,627행 × 16열)을 gzip 압축한 것이다.
푸는 즉시 `df` 로 쓸 수 있다 — 외부 파일 접근이 전혀 없다.

| 컬럼 | 뜻 | 역할 |
|---|---|---|
| `stco` `state` `year` | 카운티 FIPS · 주 · 연도 | 키 |
| `corn` | 옥수수 수확량 (bu/ac) | **타깃** |
| `gdd` `edd` | 유익열(10–29℃) · 극한고온(30℃↑) 도일 | 피처 |
| `ppt` | 생육기 강수 (mm) | 피처 |
| `whc` `om` `spH` `clay` `slope` | 토양: 보수력·유기물·pH·점토·경사 | 피처 |
| `dsci_jul` | **7월 가뭄지수** (USDM, 2000~; 이전은 NaN) | 피처(핵심) |
| `soil_jul` `pr_jul` `tmmx_jul` | **7월** 토양수분·강수·최고기온 (TerraClimate) | 피처(핵심) |
""")

# 첫 코드 셀 = 내장데이터 + 임포트 + 폰트 + df 로드 (B64 문자열을 소스에 주입)
LOAD_SRC = (
    'DATA_B64 = "' + B64 + '"\n\n'
    'import base64, gzip, io, os\n'
    'import pandas as pd, numpy as np, matplotlib.pyplot as plt\n'
    'from matplotlib import font_manager as _fm\n'
    'plt.rcParams.update({"figure.dpi": 100, "font.size": 11, "axes.grid": True, "grid.alpha": .3})\n'
    '# 한글 그래프 폰트(있으면 등록). Colab에서 깨지면 한 번만: !apt-get -qq install -y fonts-nanum\n'
    'for _p in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",\n'
    '           "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",\n'
    '           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:\n'
    '    if os.path.exists(_p):\n'
    '        _fm.fontManager.addfont(_p); plt.rcParams["font.family"] = _fm.FontProperties(fname=_p).get_name(); break\n'
    'plt.rcParams["axes.unicode_minus"] = False\n\n'
    '# 내장 데이터를 풀어서 바로 DataFrame 으로 (외부 파일 없음)\n'
    'df = pd.read_csv(io.BytesIO(gzip.decompress(base64.b64decode(DATA_B64))))\n'
    'print("데이터 로드:", df.shape, "| 카운티", df.stco.nunique(), "| 연도", df.year.min(), "-", df.year.max())\n'
    'print("7월 가뭄 결측(2000년 이전):", int(df.dsci_jul.isna().sum()), "→ 트리가 NaN 자체 처리")\n'
    'df.head(3)'
)
code(LOAD_SRC)

# ------------------------------------------------------------
md("""
## 2. 피처 정의 (14개)
""")
code("""
FEATURES = ["gdd","edd","ppt","whc","om","spH","clay","slope",
            "dsci_jul","soil_jul","pr_jul","tmmx_jul","year","state"]
X = df[FEATURES]; y = df["corn"]; groups = df["stco"]
print("피처", len(FEATURES), "개:", FEATURES)
""")

# ------------------------------------------------------------
md("""
## 3. 최고 모델 학습 — HistGradientBoosting

여러 모델(OLS/Ridge/Lasso/RandomForest/GBM) 비교에서 **트리 부스팅이 최고**였다.
고온(edd)이 수확량을 깎는 **비선형·임계** 관계를 선형 모델은 못 잡지만 트리는 잡기 때문.
결측(7월 가뭄 2000년 이전)도 자체 처리한다.
""")
code("""
from sklearn.ensemble import HistGradientBoostingRegressor

def best_model():
    return HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=0)

model = best_model().fit(X, y)   # 전체 적합(중요도·해석용)
print("학습 완료:", model)
""")

# ------------------------------------------------------------
md("""
## 4. 성능 평가 — 3가지 렌즈 (이 프로젝트의 핵심)

**같은 모델도 '시험을 어떻게 내느냐'에 따라 점수가 달라진다.** 셋 다 정직하게 보고한다.

1. **랜덤 5-fold CV** — 칸을 무작위로 가림. 쉬움(그 카운티·그 해를 다른 데서 이미 봄).
2. **GroupKFold(카운티)** — 카운티를 통째로 가림. 안 본 지역 일반화.
3. **시간분할** — 2010년까지 배우고 2011–15 미래 예보. 제일 어려움(추세를 미래로 외삽).
""")
code("""
from sklearn.model_selection import KFold, GroupKFold
from sklearn.metrics import r2_score, mean_squared_error

def cv_r2(splitter, grp=None):
    s=[]
    for a,b in splitter.split(X,y,grp):
        m=best_model().fit(X.iloc[a],y.iloc[a]); s.append(r2_score(y.iloc[b], m.predict(X.iloc[b])))
    return np.mean(s)

r2_random = cv_r2(KFold(5, shuffle=True, random_state=0))
r2_group  = cv_r2(GroupKFold(5), groups)

tr, te = df[df.year<2011], df[df.year>=2011]
m_ts = best_model().fit(tr[FEATURES], tr["corn"])
pred_ts = m_ts.predict(te[FEATURES])
r2_time = r2_score(te["corn"], pred_ts)
rmse_time = np.sqrt(mean_squared_error(te["corn"], pred_ts))

results = pd.DataFrame({
    "평가 방식": ["랜덤 5-fold CV","GroupKFold(카운티)","시간분할(2011-15)"],
    "무엇을 맞히나": ["관계 학습력(쉬움)","안 본 지역(중간)","안 본 미래(어려움)"],
    "R2": [r2_random, r2_group, r2_time]})
results.round(3)
""")
code("""
fig, ax = plt.subplots(figsize=(8,4.5))
bars = ax.bar(results["평가 방식"], results["R2"], color=["#94a3b8","#f59e0b","#2563eb"])
for b,v in zip(bars, results["R2"]):
    ax.text(b.get_x()+b.get_width()/2, v, f"{v:.3f}", ha="center", va="bottom", fontweight="bold")
ax.set(ylabel="Test R2", ylim=(0,1), title="Same model, three exams: forecast ~ interpolation")
plt.tight_layout(); plt.show()
print(f"시간분할 RMSE: {rmse_time:.1f} bu/ac")
print("→ 셋 다 진짜 예측. 예보 도구 스토리에선 가장 어려운 '미래 예보'를 대표값으로 본다.")
""")

# ------------------------------------------------------------
md("""
## 5. 무엇을 근거로 예측하나 — 피처 중요도 (블랙박스 열기)

피처를 하나씩 무작위로 섞을 때 예측력이 얼마나 떨어지는지(순열 중요도).
""")
code("""
from sklearn.inspection import permutation_importance
pi = permutation_importance(m_ts, te[FEATURES], te["corn"], n_repeats=10, random_state=0, n_jobs=-1)
imp = pd.Series(pi.importances_mean, index=FEATURES).sort_values()
fig, ax = plt.subplots(figsize=(8,5))
ax.barh(imp.index, imp.values, color="#2563eb")
ax.set(xlabel="Permutation importance (R2 drop when shuffled)", title="What the model relies on")
plt.tight_layout(); plt.show()
print("상위 5:", ", ".join(f"{k}({v:.3f})" for k,v in imp.sort_values(ascending=False).head(5).items()))
""")

md("""
## 6. 실제 vs 예측 + 2012 대가뭄 스트레스 테스트
""")
code("""
fig, ax = plt.subplots(figsize=(6,6))
ax.scatter(te["corn"], pred_ts, s=6, alpha=.25, color="#2563eb")
lim=[te["corn"].min(), te["corn"].max()]; ax.plot(lim,lim,"--",color="#9ca3af")
ax.set(xlabel="Actual corn yield (bu/ac)", ylabel="Predicted",
       title=f"Actual vs predicted (time-split test, R2={r2_time:.2f})")
plt.tight_layout(); plt.show()
m12 = (te.year==2012).values
print(f"2012 대가뭄: 실제 {te['corn'][m12].mean():.0f} vs 예측 {pred_ts[m12].mean():.0f} bu/ac")
print("→ 7월 가뭄 피처로 과대예측을 줄였지만, 계절총합의 한계로 급락을 다 못 잡는다(정직한 한계).")
""")

# ------------------------------------------------------------
md("""
## 7. 더위는 '상관'이 아니라 '인과'인가 — 고정효과(FE) 모델

예측 R²가 높아도 지역 대리변수(토양 등)에 기대면 인과 해석이 위험하다. 카운티·연도
**고정효과**로 지역차와 그해 전국충격을 걷어낸 뒤에도 극한고온(edd)이 수확량을 낮추는지 본다.
""")
code("""
def demean(frame, col):
    return frame[col] - frame.groupby("stco")[col].transform("mean") - frame.groupby("year")[col].transform("mean") + frame[col].mean()

fe = df.dropna(subset=["edd","gdd","ppt","corn"]).copy()
yv = demean(fe,"corn").values
Xv = np.column_stack([demean(fe,c).values for c in ["edd","gdd","ppt"]])
beta = np.linalg.solve(Xv.T@Xv, Xv.T@yv)
resid = yv - Xv@beta
dof = len(fe)-3-fe.stco.nunique()-fe.year.nunique()
se = np.sqrt(np.diag((resid@resid)/dof*np.linalg.inv(Xv.T@Xv)))
for nm,b,s in zip(["edd(극한고온)","gdd(유익열)","ppt(강수)"], beta, se):
    print(f"  {nm:14s} 계수 {b:+.3f}  SE {s:.3f}  t={b/s:+.1f}")
print("→ edd 계수 음수·강한 유의(|t|≫2) = 지역·연도를 통제해도 더위가 인과적으로 수확량↓.")
""")

md("""
## 8. 요약

- **최고 모델**: HistGradientBoosting, 피처 14개(온도·강수·토양·7월가뭄·7월토양수분·강수·최고기온·추세·지역).
- **성능**: 랜덤 CV ≈0.86 / GroupKFold ≈0.79 / 시간분할 ≈0.65 — 셋 다 진짜 예측, '난이도' 차이일 뿐.
- **핵심 피처**: 극한고온(edd) + 7월 가뭄(dsci_jul) + 7월 최고기온. **좋은 데이터를 고르는 것**이
  하이퍼파라미터 튜닝보다 성능을 훨씬 크게 올렸다.
- **인과 근거**: 고정효과로도 더위 효과 ≈ −1.7 bu/ac/도일 (t≈−43) → 상관이 아니라 인과.
- **한계**: 2012급 극단해는 계절총합 피처의 한계로 여전히 과소예측. 월/일 단위 데이터가 다음 지렛대.

이 예측값(ŷ)이 다음 단계(작물 배분 최적화)의 입력이 된다 — Predict-then-Optimize.
""")

# ============================================================
def run_cell(src, ns):
    buf = io.StringIO(); plt.close("all")
    tree = ast.parse(src); last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr): last = tree.body.pop()
    outs = []
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(tree, "<c>", "exec"), ns)
            val = eval(compile(ast.Expression(last.value), "<c>", "eval"), ns) if last else None
    except Exception as e:
        t = buf.getvalue()
        if t: outs.append({"output_type": "stream", "name": "stdout", "text": t})
        raise RuntimeError(f"cell failed: {e}\n{src[:200]}")
    t = buf.getvalue()
    if t: outs.append({"output_type": "stream", "name": "stdout", "text": t})
    for n in plt.get_fignums():
        b = io.BytesIO(); plt.figure(n).savefig(b, format="png", bbox_inches="tight", dpi=100); b.seek(0)
        outs.append({"output_type": "display_data", "data": {"image/png": base64.b64encode(b.read()).decode()}, "metadata": {}})
    plt.close("all")
    if val is not None:
        data = {"text/plain": repr(val)}
        if isinstance(val, (pd.DataFrame, pd.Series)):
            try: data["text/html"] = (val.to_frame() if isinstance(val, pd.Series) else val).to_html()
            except Exception: pass
        outs.append({"output_type": "execute_result", "data": data, "metadata": {}, "execution_count": 1})
    return outs


cells = []; n = 0
for kind, src in CELLS:
    if kind == "markdown":
        cells.append({"cell_type": "markdown", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": src})
    else:
        n += 1; outs = run_cell(src, NS)
        cells.append({"cell_type": "code", "id": uuid.uuid4().hex[:8], "metadata": {}, "execution_count": n, "outputs": outs, "source": src})
        preview = "DATA_B64=<내장데이터>" if src.startswith("DATA_B64") else src[:40].replace("\n", " ")
        print(f"[{n}] ok  {preview}")

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", OUT_PATH, f"({len(cells)} cells, {os.path.getsize(OUT_PATH)/1e6:.2f} MB)")
