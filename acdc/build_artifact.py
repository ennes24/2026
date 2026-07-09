"""REPORT.md 의 핵심을 임베디드 차트가 있는 단일 HTML 리포트로 빌드."""
import base64, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures"); OUT = os.path.join(HERE, "outputs")

def img(name):
    with open(os.path.join(FIG, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

corn = json.load(open(os.path.join(OUT, "model_corn.json")))
soy = json.load(open(os.path.join(OUT, "model_soybean.json")))

def figure(name, cap):
    return f'<figure><img src="{img(name)}" alt="{cap}"/><figcaption>{cap}</figcaption></figure>'

html = f"""<style>
:root {{
  --bg:#f6f3ec; --panel:#fffdf8; --ink:#2b2620; --muted:#6f665a; --line:#e2dccf;
  --gold:#b07d16; --gold-soft:#f0e4c6; --red:#a83c26; --red-soft:#f4dcd4;
  --green:#4a7a3e; --soil:#8a7350;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}}
@media (prefers-color-scheme:dark){{
  :root{{ --bg:#1c1913; --panel:#26221a; --ink:#ece5d6; --muted:#a99c86; --line:#3a342a;
    --gold:#d9a63e; --gold-soft:#3a3018; --red:#e07a5f; --red-soft:#3a221a; --green:#8bb36f; }}
}}
:root[data-theme="dark"]{{ --bg:#1c1913; --panel:#26221a; --ink:#ece5d6; --muted:#a99c86; --line:#3a342a;
    --gold:#d9a63e; --gold-soft:#3a3018; --red:#e07a5f; --red-soft:#3a221a; --green:#8bb36f; }}
:root[data-theme="light"]{{ --bg:#f6f3ec; --panel:#fffdf8; --ink:#2b2620; --muted:#6f665a; --line:#e2dccf;
    --gold:#b07d16; --gold-soft:#f0e4c6; --red:#a83c26; --red-soft:#f4dcd4; --green:#4a7a3e; }}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.68;
  font-size:16.5px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:830px;margin:0 auto;padding:0 22px 96px}}
header.hero{{padding:64px 0 30px;border-bottom:3px solid var(--gold)}}
.eyebrow{{font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--gold);font-weight:700}}
h1{{font-family:var(--serif);font-weight:700;font-size:clamp(30px,5vw,44px);line-height:1.1;
  margin:.35em 0 .3em;text-wrap:balance}}
.sub{{color:var(--muted);font-size:17px;max-width:60ch}}
h2{{font-family:var(--serif);font-size:26px;margin:56px 0 6px;padding-top:14px;border-top:1px solid var(--line)}}
h2 .n{{color:var(--gold);font-variant-numeric:tabular-nums;margin-right:.5em}}
h3{{font-size:17.5px;margin:26px 0 4px;color:var(--ink)}}
p{{margin:.55em 0}}
.lead{{color:var(--muted)}}
strong{{color:var(--ink)}}
figure{{margin:22px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:14px;overflow-x:auto}}
figure img{{display:block;width:100%;height:auto;border-radius:4px}}
figcaption{{color:var(--muted);font-size:13.5px;margin-top:10px;text-align:center}}
table{{width:100%;border-collapse:collapse;margin:18px 0;font-size:14.5px;
  font-variant-numeric:tabular-nums}}
th,td{{text-align:right;padding:9px 12px;border-bottom:1px solid var(--line)}}
th:first-child,td:first-child{{text-align:left}}
thead th{{color:var(--muted);font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}}
tbody tr:hover{{background:var(--gold-soft)}}
.callout{{border-left:4px solid var(--red);background:var(--red-soft);border-radius:0 10px 10px 0;
  padding:16px 20px;margin:22px 0}}
.callout .tag{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--red);font-weight:700}}
.callout.ok{{border-color:var(--green);background:transparent;border-left-width:4px}}
.callout.ok .tag{{color:var(--green)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:26px 0}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}}
.kpi .v{{font-family:var(--serif);font-size:30px;font-weight:700;line-height:1}}
.kpi .v.red{{color:var(--red)}} .kpi .v.green{{color:var(--green)}} .kpi .v.gold{{color:var(--gold)}}
.kpi .l{{color:var(--muted);font-size:13px;margin-top:7px}}
.pass{{display:grid;gap:12px;margin:18px 0}}
.pass div{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);
  border-radius:0 8px 8px 0;padding:12px 16px;font-size:14.5px}}
.pass b{{color:var(--gold)}}
code{{background:var(--gold-soft);padding:1px 6px;border-radius:4px;font-size:13.5px}}
.note{{font-size:13.5px;color:var(--muted)}}
footer{{margin-top:60px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}}
</style>

<div class="wrap">
<header class="hero">
  <div class="eyebrow">ACDC · Corn Belt · 1981–2015 · v3</div>
  <h1>옥수수 수확량 예측 & 작물 배분 최적화</h1>
  <p class="sub">카운티×연도 34,627행으로 수확량을 예측(다중모델)하고, 기후 모델 A로
  온난화 시나리오를 만들고, 단작 조합최적화(GA/SA vs MILP)로 작물 배치를 푼다. 핵심은
  <strong>온도(극한고온 EDD)</strong>가 지배 변수라는 것, 그리고 이 데이터의 정직한 한계다.</p>
</header>

<div class="kpis">
  <div class="kpi"><div class="v gold">0.58</div><div class="l">옥수수 테스트 R² (2011–15)<br>온도 추가로 0.52→0.58</div></div>
  <div class="kpi"><div class="v red">EDD</div><div class="l">1위 피처가 된 극한고온<br>= "옥수수엔 온도가 가장 중요"</div></div>
  <div class="kpi"><div class="v red">−8.6%</div><div class="l">온난화(EDD×2) 시 옥수수<br>강수 프록시는 +0.2%였음</div></div>
  <div class="kpi"><div class="v">+29</div><div class="l">2012 여전히 과대예측(bu/ac)<br>계절총합의 시간해상도 한계</div></div>
</div>

<h2><span class="n">01</span>설계를 3번 검토했다</h2>
<p class="lead">"3번 생각하고 만들라"는 요청에 대한 실제 설계 로그.</p>
<div class="pass">
  <div><b>1차 · 순진한 접근</b> — 강수·토양으로 바로 회귀? 문제: 수확량 변화의 절반 이상이
  '그해 날씨'가 아니라 '해마다 좋아지는 기술추세'다. 안 걸러내면 기후 효과가 묻힌다.</div>
  <div><b>2차 · 분해</b> — 수확량을 <strong>기술추세 + 기상충격</strong>으로 나눴다(카운티별
  추세선). 기후 이야기는 전부 '기상충격'에 있다. 모델은 연도를 피처로 줘 추세를 흡수시킨다.</div>
  <div><b>3차 · 정직성 검증</b> — 이 데이터로 온난화를 말할 수 있나? 감이 아니라
  <strong>2012 대가뭄을 얼마나 맞히나</strong>로 실측했다. 이 검증이 이번 분석의 결론이다.</div>
</div>

<h2><span class="n">02</span>EDA — 데이터가 하는 이야기</h2>
<h3>수확량 = 꾸준한 기술추세 + 그해 기상충격</h3>
<p>옥수수 평균은 1981년 ~102 → 2015년 ~157 bu/ac로 <strong>연 +1.7 bu/ac</strong> 상승(기술).
그 위로 1983·1988·1993·2012년에 골이 파인다 = 그해 가뭄/홍수. 우리가 예측하려는 건 이 골이다.</p>
{figure("01_trend_and_shocks.png","추세선(회색 점선) 위로 출렁이는 파란 선이 실제 수확량. 붉은 라벨이 큰 기상충격 해.")}
<h3>강수 반응은 '언덕형' — 최적점이 있다</h3>
<p>추세를 뺀 순수 기상충격을 강수별로 보면 ∩ 모양. 약 800mm에서 최대, 적으면 가뭄·많으면
침수로 둘 다 감소. 직선이 아니라서 <strong>트리 기반 모델</strong>이 맞다.</p>
{figure("02_precip_response.png","생육기 강수 대 수확량 편차. 가운데가 볼록한 언덕형.")}
<h3>어느 주가 날씨에 가장 흔들리나 = 기후 취약도</h3>
<p>변동성 최대는 <strong>사우스다코타</strong>, 최소는 <strong>네브래스카</strong>. <strong>원인은
이 데이터로 확인 불가</strong> — 이 데이터셋엔 관개 등 원인 후보 컬럼이 없고, 실제 관개 데이터는
egress 차단으로 이번 세션에 확보하지 못했다. 원인 규명 없이 "어디가 위험한가"라는 관측 사실만
재배치·보험 논의에 쓴다.</p>
{figure("04_state_vulnerability.png","주별 수확량 기상충격의 표준편차(추세 대비 %).")}
<h3>극한고온(EDD) 타임라인 — 고온해가 흉작과 정렬</h3>
<p>온도가 들어온 뒤에야 보이는 관계. 연도별 극한고온(EDD) 막대와 옥수수 편차를 겹치면
<strong>2012·1988 고온해가 흉작과 정확히 정렬</strong>한다 — 고온이 흉작의 방아쇠다.</p>
{figure("13_edd_timeline.png","연도별 EDD(막대)와 옥수수 수확량 편차(선). 2012·1988에서 고온↑·수확↓.")}
<h3>옥수수는 대두보다 고온에 약하다</h3>
<p>같은 EDD 구간에서 <strong>옥수수의 %손실 기울기가 대두보다 가파르다</strong>. 왜 2012에
옥수수만 무너지고 대두는 버텼는지가 여기서 설명된다.</p>
{figure("15_heat_sensitivity.png","EDD 대 추세대비 %손실. 옥수수(주황)가 대두(녹색)보다 가파르게 감소.")}

<h2><span class="n">03</span>머신러닝 — 무엇을 근거로 예측하나</h2>
<p>입력: 생육기 강수 + <strong>온도(극한고온 EDD·유익열 GDD)</strong> + 토양 + 연도 + 주.
타깃: 카운티 옥수수 수확량. <strong>2010년 이전 학습 / 2011–15 테스트</strong>(예보 방식).</p>
<table>
<thead><tr><th>모델</th><th>RMSE</th><th>MAE</th><th>R²</th></tr></thead>
<tbody>
<tr><td>Hist Gradient Boosting <span class="note">(best)</span></td><td>27.2</td><td>20.9</td><td>0.58</td></tr>
<tr><td>Random Forest</td><td>27.6</td><td>20.9</td><td>0.56</td></tr>
<tr><td>추세만 (baseline)</td><td>36.9</td><td>27.5</td><td>0.22</td></tr>
</tbody>
</table>
<p>온도를 넣자 옥수수 R²가 <strong>0.52 → 0.58</strong>로 오르고, 순열 중요도에서
<strong>EDD(극한고온)가 즉시 1위 피처(0.26)</strong>가 됐다. 온도 없을 때 1위였던
<code>state</code>(지역효과)를 밀어냈다는 건, 그 지역효과의 상당 부분이 실은
<strong>온도였다</strong>는 뜻 — "옥수수엔 온도가 가장 중요하다"가 데이터로 확인된 것.</p>
{figure("06_importance_corn.png","순열 중요도. 온도 추가 후 EDD(극한고온)가 1위로 올라섬.")}
{figure("12_pdp_edd_corn.png","모델이 학습한 관계: 극한고온(EDD)이 커질수록 예측 수확량이 단조 감소.")}
{figure("08_actual_vs_pred_corn.png","실제 대 예측. 낮은 수확량 구간에서 여전히 위로 치우침(다음 절).")}

<h2><span class="n">04</span>데이터 적합성 — 정직한 판정</h2>
<div class="callout ok">
<div class="tag">판정 (1) — 온도가 필수였고, 가설이 확인됐다</div>
<p style="margin:.4em 0">온도를 넣자 옥수수 R²가 오르고 <strong>EDD가 1위 피처</strong>,
온난화 시나리오가 비로소 작동. <strong>"옥수수 생산에 무엇이 가장 중요한가 = (물 다음)
개화기 극한고온"</strong>이 데이터로 증명됐다.</p>
</div>
<table>
<thead><tr><th>항목</th><th>온도 없음</th><th>온도 있음</th></tr></thead>
<tbody>
<tr><td>옥수수 테스트 R²</td><td>0.52</td><td style="color:var(--green)">0.58</td></tr>
<tr><td>1위 피처</td><td>state (지역)</td><td style="color:var(--green)">edd (극한고온)</td></tr>
<tr><td>온난화 시나리오</td><td>+0.2% (무의미)</td><td style="color:var(--green)">EDD×2 → −8.6%</td></tr>
</tbody>
</table>
<div class="callout">
<div class="tag">판정 (2) — 그래도 2012는 못 잡는다</div>
<p style="margin:.4em 0">온도를 넣어도 2012 옥수수는 <strong>여전히 +29 과대예측</strong>
(예측 138 vs 실제 109). 남은 원인은 온도가 아니라 <strong>데이터의 시간해상도</strong>다.</p>
</div>
<table>
<thead><tr><th>작물</th><th>2012 실제</th><th>예측(온도 포함)</th><th>오차</th></tr></thead>
<tbody>
<tr><td>옥수수</td><td>109</td><td>138</td><td style="color:var(--red)">+29</td></tr>
<tr><td>대두</td><td>38</td><td>42</td><td>+3</td></tr>
</tbody>
</table>
<p>2012 피해는 7월 수분기에 고온·가뭄이 <strong>동시에, 평소 안 겪던 핵심 벨트에</strong>
집중됐는데, 우리 피처는 <strong>Mar–Aug 계절 총합</strong>이라 그 7월 집중을 희석한다.
계절합 EDD(31.6, 평년의 2배)가 설명하는 건 붕괴의 3분의 1 정도. <strong>평년·추세·온난화
방향엔 충분하지만, 2012급 tail 극한 재현엔 월 단위(특히 7월) 해상도가 더 필요</strong>하다.</p>

<h2><span class="n">05</span>예측 1 — 생산성 지도</h2>
<p>학습 모델로 카운티 수확량을 예측해 주별로 집계. 해석은 <strong>'재배치의 방향'</strong>:
같은 면적이면 상위 주 비중을 늘릴수록 총생산↑ (실제 최적화에선 전환비용 패널티로 급격한
변화를 억제).</p>
{figure("09_productivity_corn.png","주별 예측 옥수수 수확량. 아이오와 최고(186) ~ 텍사스 최저(111).")}

<h2><span class="n">06</span>예측 2 — 기후 스트레스 시나리오</h2>
<p class="lead">온도 확보로 <strong>EDD(극한고온)를 직접 늘리는 진짜 온난화 시나리오</strong>가 가능해졌다.</p>
<table>
<thead><tr><th>시나리오</th><th>예측 수확량</th><th>기준 대비</th></tr></thead>
<tbody>
<tr><td>baseline</td><td>157.4</td><td>0.0%</td></tr>
<tr><td>가뭄 −30% 강수</td><td>155.4</td><td>−1.3%</td></tr>
<tr><td>온난화 EDD×1.5</td><td>150.6</td><td style="color:var(--red)">−4.3%</td></tr>
<tr><td>온난화 EDD×2.0</td><td>143.8</td><td style="color:var(--red)">−8.6%</td></tr>
<tr><td>온난화+가뭄 복합</td><td>143.5</td><td style="color:var(--red)">−8.8%</td></tr>
</tbody>
</table>
{figure("10_scenario_corn.png","시나리오별 예측 수확량 변화율. 온난화(EDD↑)가 가뭄 단독보다 타격이 크다.")}
{figure("11_drought_by_state_corn.png","가뭄 -30% 시 주별 감소율.")}
<div class="callout ok">
<div class="tag">온도 전/후 대비</div>
<p style="margin:.4em 0">온도 없이 강수만 쓰던 이전 버전의 온난화 시나리오는 <strong>+0.2%</strong>로
무의미했다. 온도 확보 후 <strong>EDD×2 → −8.6%</strong>, 온난화+가뭄 복합 −8.8%로 근거 있는
수치가 나온다. 가뭄 단독(−1.3%)이 작아 보이는 건, 모델이 흉작 원인을 대부분 <strong>동반되는
고온(EDD)</strong>에 귀속시키기 때문 — 현실적 기후변화는 <strong>온난화+가뭄 복합</strong>이다.</p>
</div>

<h2><span class="n">07</span>2단계 최적화 — 전환비용을 감안한 배치</h2>
<p>1단계 예측 수확량을 <strong>목적함수 계수</strong>로 넣어 각 카운티 땅을 옥수수 vs 대두로
배분(PuLP LP). 요청하신 <strong>전환비용 패널티</strong>를 그대로 구현: 현 배치에서 많이
벗어날수록 벌점 <code>λ·|x−x0|</code>. 무게(톤) 대신 <strong>수익($)</strong>으로 비교해야
트레이드오프가 산다(대두가 톤당 값 2배↑).</p>
<table>
<thead><tr><th>λ (전환비용)</th><th>평균 재배치</th><th>수익 증가</th></tr></thead>
<tbody>
<tr><td>0 (이론최적)</td><td>45%</td><td>+9.2%</td></tr>
<tr><td>100</td><td>36%</td><td>+8.4%</td></tr>
<tr><td>150 (무릎)</td><td style="color:var(--green)">18%</td><td style="color:var(--green)">+4.9%</td></tr>
<tr><td>250</td><td>0.4%</td><td>+0.15%</td></tr>
</tbody>
</table>
{figure("17_transition_tradeoff.png","전환비용 트레이드오프. 무릎(λ=150)에서 적은 재배치로 이득 대부분 확보.")}
{figure("18_alloc_shift_by_state.png","λ=150에서 주별 권고 방향: +옥수수(주황) / +대두(녹색).")}
<div class="callout ok">
<div class="tag">핵심 — 이론최적 vs 전환비용 감안</div>
<p style="margin:.4em 0"><strong>λ=0</strong>은 카운티당 45%를 갈아엎어야 +9.2%(비현실적 상한).
<strong>λ=150(무릎)</strong>은 <strong>재배치를 18%로 줄여도 이득의 절반(+4.9%)</strong>을
얻는다. 여기서 더 짜내면 churn만 급증 — "조금만 바꿔도 이득 대부분"이라는 현실적 권고점.
λ만 바꾸면 의사결정자의 '얼마나 급진적으로 바꿀까' 성향을 반영할 수 있다.</p>
</div>
<p class="note">한계: ACDC에 카운티 경작면적이 없어 땅=카운티당 1단위 가정, x0는 과거 수익
비율로 근사. 따라서 gain%의 절대크기보다 <strong>곡선의 모양</strong>이 결론. NASS 면적을
붙이면 절대량까지 신뢰 가능(egress 차단으로 이번 세션엔 미확보).</p>

<h2><span class="n">08</span>v3 — 여러 모델 비교 (트리가 왜 맞는가)</h2>
<p>트리만 쓴 게 아니라 <strong>OLS/Ridge/Lasso/RF/GBM</strong>을 같은 프로토콜로 비교했다.
우리 온도피처 gdd·edd는 이미 Schlenker-Roberts의 유익열/유해열 압축 그 자체다.</p>
<table>
<thead><tr><th>모델</th><th>RMSE</th><th>R²</th></tr></thead>
<tbody>
<tr><td>GBM</td><td>27.2</td><td style="color:var(--green)">0.58</td></tr>
<tr><td>RandomForest</td><td>27.6</td><td>0.56</td></tr>
<tr><td>OLS / Ridge</td><td>31.3</td><td>0.44</td></tr>
<tr><td>Lasso</td><td>33.1</td><td>0.37</td></tr>
</tbody>
</table>
{figure("20_heat_response_models_corn.png","유해고온 반응: 트리(빨강)는 고온의 비대칭 꺾임을 재현, 선형(회색)은 직선뿐.")}
<p>"트리로 예측"이 틀린 게 아니라, <strong>왜 트리가 맞는지를 선형과의 대비로 증명</strong>한 것.
고온의 비선형 손해를 선형은 구조적으로 못 잡는다(H3).</p>

<h2><span class="n">09a</span>트랙 2 — 날씨 예측 EDA & ML (예측 가능한가?)</h2>
<p>수확량이 아니라 <strong>기후 변수(EDD·강수) 자체</strong>를 타깃으로 "미래 날씨를 예측할 수
있나"를 물었다. 답은 데이터가 준다.</p>
{figure("W2_variance_decomp.png","분산분해: EDD 변동의 83%가 '어디(공간)', 연도(시간)는 11%뿐.")}
{figure("23_weather_ml_r2.png","날씨 예측: ML이 단순 climatology(카운티 평년)를 못 이긴다. 작년값(persistence)은 무용.")}
<div class="callout">
<div class="tag">핵심 — 날씨는 점예측 대상이 아니다</div>
<p style="margin:.4em 0">EDD 분산의 <strong>83%가 공간</strong>(어디가 더운가), 연차는 11%.
작년→올해 자기상관은 EDD 0.11·강수 0.02로 <strong>사실상 예측 불가</strong>. 실제로 미래 EDD
예측에서 <strong>단순 평년(climatology) R² 0.75가 ML 0.56을 이기고</strong>, 연차편차 R²은
음수(−0.76). ⇒ 미래 날씨는 <strong>평년 + 추세 + 외생 시나리오</strong>로 다뤄야 한다(H4).</p>
</div>

<h2><span class="n">09b</span>트랙 2 — 기후 모델 A + 핵심 발견</h2>
<div class="callout">
<div class="tag">★ 발견 — Corn Belt "warming hole"</div>
<p style="margin:.4em 0"><strong>1981–2015 옥수수 벨트에서 극한고온(EDD)은 증가하지 않았다</strong>
(추세 −0.046/yr, 평탄~하락). 오히려 강수가 +2.7mm/yr 증가. 즉 <strong>이 지역 관측추세를
외삽하면 온난화 시나리오가 안 나온다.</strong></p>
</div>
{figure("22_climate_model.png","관측 EDD(검정)는 상승 없음. 온난화는 외생(IPCC) 가정으로만 부과 가능(점선).")}
<p>그래서 온난화는 <strong>외생 가정(IPCC)</strong>으로 부과하고 시나리오로 다뤄야 한다(H4) —
v2의 임의 'EDD×2'를 <strong>정당화하면서 교정</strong>한 셈이다.</p>
<table>
<thead><tr><th>시나리오</th><th>옥수수 수확량</th><th>기준 대비</th></tr></thead>
<tbody>
<tr><td>관측추세 외삽 2050</td><td>154.7</td><td>−1.7%</td></tr>
<tr><td>IPCC mild (EDD×1.3)</td><td>153.4</td><td>−2.5%</td></tr>
<tr><td>IPCC severe (EDD×1.8)</td><td>146.8</td><td style="color:var(--red)">−6.7%</td></tr>
</tbody>
</table>

<h2><span class="n">10</span>v3 — 단작 조합최적화 (GA/SA vs MILP)</h2>
<p>연속 LP가 아니라 각 카운티가 <strong>작물 하나만</strong> 고르는 binary 배정 + <strong>대두 35%
윤작 요건</strong>(커플링 제약)으로 진짜 조합최적화를 만들고, 정확해(MILP)와 메타휴리스틱(GA/SA)을 비교.</p>
<table>
<thead><tr><th>방법</th><th>목적값</th><th>시간(s)</th><th>gap%</th></tr></thead>
<tbody>
<tr><td>MILP (정확해)</td><td>431,690</td><td>0.03</td><td>0.00</td></tr>
<tr><td>GA</td><td>424,496</td><td>2.30</td><td style="color:var(--green)">1.67</td></tr>
<tr><td>SA</td><td>422,127</td><td>6.15</td><td style="color:var(--green)">2.22</td></tr>
</tbody>
</table>
{figure("21_meta_convergence.png","GA(파랑)·SA(빨강)가 MILP 최적(검은 점선)에 수렴. 정확해의 1.7~2.2% 이내.")}
<div class="callout ok">
<div class="tag">정직한 결론</div>
<p style="margin:.4em 0">GA/SA가 정확해의 <strong>1.7–2.2% 이내로 수렴</strong>(H5). 다만 이 규모
(659×2작물)에선 <strong>정확 MILP가 더 빠르고 최적</strong> — 강의 서사대로 "작물·카운티가 늘면"
GA/SA 우위가 드러난다. 억지로 MILP를 느리게 만들지 않고 관측 사실을 그대로 보고한다.</p>
</div>

<footer>
데이터: ACDC (Purdue PURR, CC-BY), 1981–2015 · 대상: Corn Belt 12개 주 · 피처: 강수·토양·
<strong>온도(GDD/EDD)</strong>·연도. 온도는 원본 GDD를 Colab에서 옥수수 기준 GDD·EDD로
압축해 확보(Mar–Aug 창) · 재현: <code>cd acdc && python3 run_all.py</code> · 그림·수치 전체는
<code>acdc/figures</code>, <code>acdc/outputs</code>.
</footer>
</div>"""

with open(os.path.join(HERE, "report.html"), "w") as f:
    f.write(html)
print("wrote", os.path.join(HERE, "report.html"), f"({len(html)//1024} KB)")
