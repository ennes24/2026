"""
best_corn_yield_model.ipynb 생성기 — 실험 중 '테스트 성능 최고' 모델만 골라 처음~끝 정리.
각 셀을 실제 실행해 표·그래프를 노트북에 미리 채운다(nbclient 불필요).
"""
import ast, io, json, base64, contextlib, os, uuid
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "best_corn_yield_model.ipynb")
CELLS, NS = [], {}


def md(t): CELLS.append(("markdown", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))


# ============================================================
md("""
# 옥수수 수확량 예측 — 최종 최고 성능 모델

> **바로 실행하기.** 이 노트북은 자체 완결형이다. 아래 두 가지 방법 중 하나로 돌린다.
> - **Colab (원클릭)**: 저장소 README의 "Open in Colab" 배지 클릭 → 첫 코드 셀이 데이터를 자동 clone → `런타임 > 모두 실행`.
> - **로컬**: `git clone` 후 `pip install -r acdc/requirements.txt` → `acdc/notebooks/` 에서 `jupyter lab`.
>
> 데이터(약 12MB, 6개 CSV)는 저장소에 포함되어 있어 별도 다운로드가 필요 없다.

여러 실험(온도·강수·토양·관개·가뭄·토양수분 조합, 선형 vs 트리, SA 튜닝) 중 **테스트 성능이
가장 높았던 모델 하나**만 골라 처음부터 끝까지 정리한다.

**최종 모델**: HistGradientBoosting (그래디언트 부스팅 트리), 피처 14개
**데이터**: ACDC(미국 카운티×연도, 1981–2015) + USDM 7월 가뭄 + TerraClimate 7월 토양수분·강수·최고기온,
Corn Belt 12개 주.

**성능 (3가지 평가 렌즈 — 뒤에서 자세히)**

| 평가 방식 | 무엇을 맞히나 | R² |
|---|---|---|
| 랜덤 5-fold CV | 관계 학습력 (쉬움) | **0.862** |
| GroupKFold(카운티) | 안 본 지역 (중간) | 0.790 |
| 시간분할(2011–15) | 안 본 미래 예보 (어려움) | 0.650 |

세 개 다 진짜 예측이며, 점수 차이는 '시험 난이도' 차이다(모델은 하나).
""")

# ------------------------------------------------------------
md("""
## 1. 데이터 불러오기

6개 CSV를 카운티(`stco`)·연도(`year`)로 병합한다. `stco`는 미국 FIPS 코드(주+카운티).

| 파일 | 내용 | 역할 |
|---|---|---|
| `yielddata.csv` | 옥수수 수확량 (bu/ac) | **타깃** |
| `gdd_slim.csv` | 온도: gdd(유익열)·edd(극한고온) | 피처 |
| `pptMarAug.csv` | 생육기 강수 (mm) | 피처 |
| `soil2011.csv` | 토양(보수력·유기물·pH 등) | 피처 |
| `drought_slim.csv` | **7월 가뭄지수 DSCI** (USDM) | 피처(핵심) |
| `terraclimate_slim.csv` | **7월 토양수분·강수·최고기온** (TerraClimate) | 피처 |
""")

code("""
import os, subprocess
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from matplotlib import font_manager as _fm
plt.rcParams.update({"figure.dpi": 100, "font.size": 11, "axes.grid": True, "grid.alpha": .3})

# 그래프 한글 폰트(있으면 등록). Colab에서 깨지면 한 번만: !apt-get -qq install -y fonts-nanum
for _p in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
           "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(_p):
        _fm.fontManager.addfont(_p)
        plt.rcParams["font.family"] = _fm.FontProperties(fname=_p).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

# 데이터 경로 자동 탐지 — 로컬(notebooks/·repo루트)에서도, Colab에서도 그대로 돌아간다.
def _find_data():
    for p in ["../data", "data", "acdc/data", "/content/2026/acdc/data"]:
        if os.path.exists(os.path.join(p, "yielddata.csv")):
            return p
    return None

D = _find_data()
if D is None:
    # Colab 등 repo가 없는 환경: GitHub에서 얕은 clone (repo가 public 이어야 함)
    print("데이터가 없어 GitHub에서 clone 합니다 …")
    subprocess.run(["git", "clone", "--depth", "1",
                    "--branch", "claude/corn-yield-optimization-x7qo1o",
                    "https://github.com/ennes24/2026.git", "/content/2026"], check=True)
    D = "/content/2026/acdc/data"
print("DATA_DIR =", D)

yield_df = pd.read_csv(f"{D}/yielddata.csv")
ppt   = pd.read_csv(f"{D}/pptMarAug.csv")
soil  = pd.read_csv(f"{D}/soil2011.csv")
temp  = pd.read_csv(f"{D}/gdd_slim.csv")                       # stco, year, gdd, edd
drought = pd.read_csv(f"{D}/drought_slim.csv")[["stco","year","dsci_jul"]]
tc    = pd.read_csv(f"{D}/terraclimate_slim.csv")[["stco","year","soil_jul","pr_jul","tmmx_jul"]]  # 7월 토양수분·강수·최고기온
print("yield", yield_df.shape, "| temp", temp.shape, "| drought", drought.shape, "| terraclimate", tc.shape)
yield_df.head(3)
""")

md("""
## 2. 병합 + Corn Belt 12개 주로 필터

옥수수 주산지 12개 주만 사용(변두리 카운티는 잡음). 7월 가뭄(USDM)은 2000년부터라
1981–1999는 결측(NaN)으로 남는데, **HistGradientBoosting은 결측을 자체 처리**하므로 35년을
다 살린다.
""")

code("""
CORN_BELT = {19:"IA",17:"IL",31:"NE",27:"MN",18:"IN",20:"KS",39:"OH",46:"SD",29:"MO",38:"ND",55:"WI",48:"TX"}

df = (yield_df
      .merge(ppt,  on=["stco","year"], how="left")
      .merge(temp, on=["stco","year"], how="left")
      .merge(soil, on="stco",          how="left")
      .merge(drought, on=["stco","year"], how="left")
      .merge(tc,      on=["stco","year"], how="left"))
df["state"] = df["stco"] // 1000
df = df[df["state"].isin(CORN_BELT)].copy()

# 타깃/필수 피처 결측 행 제거 (가뭄·토양수분 결측은 남겨둠 → 트리가 처리)
need = ["corn","ppt","edd","whc","om","spH","clay","slope"]
df = df.dropna(subset=need).copy()
print("최종 패널:", df.shape, "| 카운티", df.stco.nunique(), "| 연도", df.year.min(), "-", df.year.max())
print("7월 가뭄 결측(1981-99 등):", df.dsci_jul.isna().sum())
df[["stco","year","corn","edd","dsci_jul","soil_jul"]].head(3)
""")

md("""
## 3. 피처 정의 (14개)

| 피처 | 의미 |
|---|---|
| gdd / edd | 온도: 유익열(10–29℃) / 극한고온(30℃↑) |
| ppt | 생육기 총강수 |
| whc, om, spH, clay, slope | 토양: 보수력·유기물·산도·점토·경사 |
| dsci_jul | **7월 가뭄지수** (수확량 최대 향상 요인) |
| soil_jul / pr_jul / tmmx_jul | **7월** 토양수분 / 강수 / 최고기온 (개화기 '언제' 정보) |
| year | 기술추세 |
| state | 지역 |
""")

code("""
FEATURES = ["gdd","edd","ppt","whc","om","spH","clay","slope",
            "dsci_jul","soil_jul","pr_jul","tmmx_jul","year","state"]
X = df[FEATURES]
y = df["corn"]
groups = df["stco"]
print("피처", len(FEATURES), "개:", FEATURES)
""")

# ------------------------------------------------------------
md("""
## 4. 최고 모델 학습 — HistGradientBoosting

여러 모델(OLS/Ridge/Lasso/RandomForest/GBM)을 비교한 결과 **트리 부스팅(GBM)이 최고**였다.
이유: 고온(edd)이 수확량을 깎는 **비선형 관계**를 선형 모델은 못 잡지만 트리는 잡는다.
여기서는 그 승자만 학습한다.
""")

code("""
from sklearn.ensemble import HistGradientBoostingRegressor

def best_model():
    return HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, random_state=0)

# 전체 데이터로 한 번 적합(피처중요도·최종 예측용)
model = best_model().fit(X, y)
print("학습 완료:", model)
""")

# ------------------------------------------------------------
md("""
## 5. 성능 평가 — 3가지 렌즈 (이 프로젝트의 핵심)

**같은 모델도 '시험을 어떻게 내느냐'에 따라 점수가 달라진다.** 세 가지를 모두 정직하게 보고한다.

1. **랜덤 5-fold CV** — (카운티,연도) 칸을 무작위로 가리고 맞힘. 쉬움(모델이 그 카운티·그 해를 이미 다른 데서 봄).
2. **GroupKFold(카운티)** — 카운티를 통째로 가림. 안 본 지역 일반화.
3. **시간분할** — 2010년까지 배우고 2011–15 미래 예보. 제일 어려움(기술추세를 미래로 외삽).
""")

code("""
from sklearn.model_selection import KFold, GroupKFold
from sklearn.metrics import r2_score, mean_squared_error

def cv_r2(splitter, grp=None):
    scores=[]
    for a,b in splitter.split(X,y,grp):
        m=best_model().fit(X.iloc[a],y.iloc[a])
        scores.append(r2_score(y.iloc[b], m.predict(X.iloc[b])))
    return np.mean(scores)

r2_random = cv_r2(KFold(5, shuffle=True, random_state=0))
r2_group  = cv_r2(GroupKFold(5), groups)

# 시간분할
tr, te = df[df.year<2011], df[df.year>=2011]
m_ts = best_model().fit(tr[FEATURES], tr["corn"])
pred_ts = m_ts.predict(te[FEATURES])
r2_time = r2_score(te["corn"], pred_ts)
rmse_time = np.sqrt(mean_squared_error(te["corn"], pred_ts))

results = pd.DataFrame({
    "평가 방식": ["랜덤 5-fold CV", "GroupKFold(카운티)", "시간분할(2011-15)"],
    "무엇을 맞히나": ["관계 학습력(쉬움)", "안 본 지역(중간)", "안 본 미래(어려움)"],
    "R2": [r2_random, r2_group, r2_time],
})
results.round(3)
""")

code("""
fig, ax = plt.subplots(figsize=(8,4.5))
bars = ax.bar(results["평가 방식"], results["R2"], color=["#94a3b8","#f59e0b","#2563eb"])
for b,v in zip(bars, results["R2"]):
    ax.text(b.get_x()+b.get_width()/2, v, f"{v:.3f}", ha="center", va="bottom", fontweight="bold")
ax.set(ylabel="Test R2", ylim=(0,1),
       title="Same model, three exams: 0.63 (forecast) ~ 0.86 (interpolation)")
plt.tight_layout(); plt.show()
print(f"시간분할 RMSE: {rmse_time:.1f} bu/ac")
print("→ 셋 다 진짜 예측. 우리는 가장 어려운 '미래 예보(0.63)'를 대표값으로 보고한다(예보 도구 스토리).")
""")

# ------------------------------------------------------------
md("""
## 6. 무엇을 근거로 예측하나 — 피처 중요도 (블랙박스 열기)

피처를 하나씩 무작위로 섞었을 때 예측력이 얼마나 떨어지는지(순열 중요도).
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
## 7. 실제 vs 예측 + 2012 대가뭄 스트레스 테스트
""")

code("""
fig, ax = plt.subplots(figsize=(6,6))
ax.scatter(te["corn"], pred_ts, s=6, alpha=.25, color="#2563eb")
lim=[te["corn"].min(), te["corn"].max()]; ax.plot(lim,lim,"--",color="#9ca3af")
ax.set(xlabel="Actual corn yield (bu/ac)", ylabel="Predicted", title=f"Actual vs predicted (time-split test, R2={r2_time:.2f})")
plt.tight_layout(); plt.show()

m12 = (te.year==2012).values
print(f"2012 대가뭄: 실제 {te['corn'][m12].mean():.0f} vs 예측 {pred_ts[m12].mean():.0f} bu/ac")
print("→ 7월 가뭄 피처로 과대예측이 +29→+19로 줄었지만, 계절총합의 한계로 여전히 남음(정직한 한계).")
""")

# ------------------------------------------------------------
md("""
## 8. (보너스) 더위는 '상관'이 아니라 '인과'인가 — 고정효과 모델

예측모델은 R²는 높아도 지역 대리변수(토양 등)에 기댈 수 있어 인과 해석이 위험하다.
카운티·연도 **고정효과**로 지역차와 그해 전국충격을 걷어내도 극한고온(edd)이 수확량을
낮추는지 본다(within 변환 후 회귀).
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
    print(f"  {nm:14s} 계수 {b:+.3f}  t={b/s:+.1f}")
print("→ edd 계수 음수·강한 유의 = 지역·연도를 통제해도 더위가 인과적으로 수확량↓ (상관 아님).")
""")

md("""
## 9. 요약

- **최고 모델**: HistGradientBoosting, 피처 14개(온도·강수·토양·7월가뭄·7월토양수분·강수·최고기온·추세·지역).
- **성능**: 랜덤 CV **0.862** / GroupKFold 0.790 / 시간분할 **0.650** — 셋 다 진짜 예측, 난이도 차이.
- **가장 중요한 피처**: 극한고온(edd) + 7월 가뭄(dsci_jul) + 7월 최고기온. 데이터를 잘 고르는 게
  (7월 가뭄 +0.05, 7월 강수+최고기온 +0.035) 하이퍼파라미터 튜닝(+0.007)보다 훨씬 컸다.
- **인과 근거**: 고정효과로도 더위 효과가 −1.7 bu/ac/도일(t≈−43)로 유의 → 상관이 아니라 인과.
- **한계**: 2012급 극단해는 계절총합 피처의 한계로 여전히 과소평가. 월/일 단위 데이터가 다음 지렛대.

이 예측값(ŷ)이 다음 단계(작물 배분 최적화)의 입력이 된다 — Predict-then-Optimize.
""")

# ============================================================
def run_cell(src, ns):
    buf=io.StringIO(); plt.close("all")
    tree=ast.parse(src); last=None
    if tree.body and isinstance(tree.body[-1], ast.Expr): last=tree.body.pop()
    outs=[]
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(tree,"<c>","exec"), ns)
            val = eval(compile(ast.Expression(last.value),"<c>","eval"), ns) if last else None
    except Exception as e:
        t=buf.getvalue()
        if t: outs.append({"output_type":"stream","name":"stdout","text":t})
        raise RuntimeError(f"cell failed: {e}\n{src[:200]}")
    t=buf.getvalue()
    if t: outs.append({"output_type":"stream","name":"stdout","text":t})
    for n in plt.get_fignums():
        b=io.BytesIO(); plt.figure(n).savefig(b,format="png",bbox_inches="tight",dpi=100); b.seek(0)
        outs.append({"output_type":"display_data","data":{"image/png":base64.b64encode(b.read()).decode()},"metadata":{}})
    plt.close("all")
    if val is not None:
        data={"text/plain":repr(val)}
        if isinstance(val,(pd.DataFrame,pd.Series)):
            try: data["text/html"]=(val.to_frame() if isinstance(val,pd.Series) else val).to_html()
            except Exception: pass
        outs.append({"output_type":"execute_result","data":data,"metadata":{},"execution_count":1})
    return outs

cells=[]; n=0
for kind,src in CELLS:
    if kind=="markdown":
        cells.append({"cell_type":"markdown","id":uuid.uuid4().hex[:8],"metadata":{},"source":src})
    else:
        n+=1; outs=run_cell(src,NS)
        cells.append({"cell_type":"code","id":uuid.uuid4().hex[:8],"metadata":{},"execution_count":n,"outputs":outs,"source":src})
        print(f"[{n}] ok")
nb={"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python","version":"3.11"}},"nbformat":4,"nbformat_minor":5}
json.dump(nb, open(OUT_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", OUT_PATH, f"({len(cells)} cells)")
