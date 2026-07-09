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
  <div class="eyebrow">ACDC · Corn Belt · 1981–2015</div>
  <h1>옥수수 수확량: 데이터가 어디까지 말해주는가</h1>
  <p class="sub">카운티×연도 34,627행으로 옥수수 수확량을 예측하고, 생산성 지도와 기후
  스트레스 시나리오를 만든다. 그리고 이 데이터가 <strong>어디까지 믿을 만한지</strong>를
  2012년 대가뭄으로 정직하게 검증한다.</p>
</header>

<div class="kpis">
  <div class="kpi"><div class="v gold">0.52</div><div class="l">옥수수 테스트 R² (2011–15)<br>추세만 대비 +0.30</div></div>
  <div class="kpi"><div class="v green">+1.7</div><div class="l">bu/ac/년 기술추세<br>(품종·농법 발전)</div></div>
  <div class="kpi"><div class="v red">+26</div><div class="l">2012 가뭄 과대예측(bu/ac)<br>= 온도 데이터 부재의 증거</div></div>
  <div class="kpi"><div class="v">−6.1%</div><div class="l">가뭄 −30% 강수 시<br>예측 수확량 변화</div></div>
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
<p>변동성 최대는 <strong>사우스다코타</strong>, 최소는 <strong>네브래스카</strong>. NE가
안정적인 건 관개 비율이 높기 때문 — 데이터에 관개 컬럼이 없어도 변동성 지도가 그 구조를 드러낸다.</p>
{figure("04_state_vulnerability.png","주별 수확량 기상충격의 표준편차(추세 대비 %).")}

<h2><span class="n">03</span>머신러닝 — 무엇을 근거로 예측하나</h2>
<p>입력: 생육기 강수 + 토양(보수력·유기물·pH·점토·경사) + 연도 + 주. 타깃: 카운티 옥수수
수확량. <strong>2010년 이전 학습 / 2011–15 테스트</strong>(미래를 미리 안 보는 예보 방식).</p>
<table>
<thead><tr><th>모델</th><th>RMSE</th><th>MAE</th><th>R²</th></tr></thead>
<tbody>
<tr><td>Hist Gradient Boosting <span class="note">(best)</span></td><td>28.8</td><td>22.2</td><td>0.52</td></tr>
<tr><td>Random Forest</td><td>29.6</td><td>22.4</td><td>0.50</td></tr>
<tr><td>추세만 (baseline)</td><td>36.9</td><td>27.5</td><td>0.22</td></tr>
</tbody>
</table>
<p>날씨·토양을 넣으면 추세만 대비 <strong>RMSE 8.1 bu/ac 개선</strong> — 기후·토양 정보가
실제로 기여한다. 대두는 R² 0.63으로 더 좋다(고온 민감도가 낮아 강수만으로 잘 설명).</p>
{figure("06_importance_corn.png","순열 중요도. state가 큰 건 지역의 기후·토양 기본수준을 통째로 흡수하기 때문.")}
{figure("08_actual_vs_pred_corn.png","실제 대 예측. 낮은 수확량(가뭄) 구간에서 위로 치우침 = 과대예측.")}

<h2><span class="n">04</span>데이터 적합성 — 정직한 판정</h2>
<div class="callout">
<div class="tag">핵심 결론</div>
<p style="margin:.4em 0"><strong>평년 예측엔 적합하다. 그러나 온난화가 정작 중요해지는
'극한 고온해'엔 불충분하다 — 온도(GDD/EDD) 데이터가 없기 때문이다.</strong></p>
</div>
<p>감이 아니라 <strong>2012 대가뭄 스트레스 테스트</strong>로 증명:</p>
<table>
<thead><tr><th>작물</th><th>2012 실제</th><th>2012 예측</th><th>오차</th></tr></thead>
<tbody>
<tr><td>옥수수</td><td>109</td><td>135</td><td style="color:var(--red)">+26 (가뭄 과소평가)</td></tr>
<tr><td>대두</td><td>38</td><td>41</td><td>+3 (거의 맞음)</td></tr>
</tbody>
</table>
<p>2012년은 강수 부족 + <strong>개화기 극한 고온</strong>이 겹친 사건인데, 강수(473mm)만으로는
그 파국을 예상 못 한다. 실제 원인인 '수분기 고온'이 피처에 없기 때문. 대두가 잘 맞은 것도
같은 논리(고온 민감도 낮음) — <strong>차이의 원인이 정확히 '온도'임을 교차 확인</strong>했다.</p>
<div class="callout ok">
<div class="tag">해결책 (코드에 반영됨)</div>
<p style="margin:.4em 0"><code>acdc/data/gddAprOct.csv</code>를 넣고 <code>run_all.py</code>만
다시 돌리면 GDD(10–29°C)·EDD(30°C+) 피처와 진짜 온난화 시나리오가 자동으로 켜진다.
사용자가 못 올린 그 온도 파일이 <strong>선택이 아니라 필수</strong>임이 데이터로 증명된 것.</p>
</div>

<h2><span class="n">05</span>예측 1 — 생산성 지도</h2>
<p>학습 모델로 카운티 수확량을 예측해 주별로 집계. 해석은 <strong>'재배치의 방향'</strong>:
같은 면적이면 상위 주 비중을 늘릴수록 총생산↑ (실제 최적화에선 전환비용 패널티로 급격한
변화를 억제).</p>
{figure("09_productivity_corn.png","주별 예측 옥수수 수확량. 아이오와 최고(184) ~ 텍사스 최저(114).")}

<h2><span class="n">06</span>예측 2 — 기후 스트레스 시나리오</h2>
<table>
<thead><tr><th>시나리오</th><th>예측 수확량</th><th>기준 대비</th></tr></thead>
<tbody>
<tr><td>baseline</td><td>156.8</td><td>0.0%</td></tr>
<tr><td>가뭄 −15% 강수</td><td>156.6</td><td>−0.2%</td></tr>
<tr><td>가뭄 −30% 강수</td><td>147.3</td><td style="color:var(--red)">−6.1%</td></tr>
<tr><td>온난화 +2°C (프록시)</td><td>157.2</td><td>+0.2%</td></tr>
<tr><td>온난화 +3°C+가뭄 (프록시)</td><td>151.1</td><td>−3.6%</td></tr>
</tbody>
</table>
{figure("10_scenario_corn.png","시나리오별 예측 수확량 변화율.")}
{figure("11_drought_by_state_corn.png","가뭄 -30% 시 주별 감소율. SD가 가장 취약.")}
<div class="callout">
<div class="tag">한계 · 반드시 읽을 것</div>
<p style="margin:.4em 0">가뭄(강수↓)은 직접 모의 가능하나, <strong>온난화(기온↑)는 프록시로만</strong>
넣었다. 결과가 +0.2%로 거의 반응 없는 것 자체가 발견이다 — <strong>강수만으로는 온난화
피해가 안 잡히고 심지어 +로 뒤집힌다.</strong> 3절의 '온도 없음' 문제가 시나리오에서도 재현됐다.
진짜 온난화 분석은 온도 파일 투입 후 EDD 시나리오로 해야 한다.</p>
</div>

<footer>
데이터: ACDC (Purdue PURR, CC-BY), 1981–2015 · 대상: Corn Belt 12개 주 ·
재현: <code>cd acdc && python3 run_all.py</code> · 온도 파일 미확보(egress 차단)로
온난화 트랙은 프록시. 그림·수치 전체는 <code>acdc/figures</code>, <code>acdc/outputs</code>.
</footer>
</div>"""

with open(os.path.join(HERE, "report.html"), "w") as f:
    f.write(html)
print("wrote", os.path.join(HERE, "report.html"), f"({len(html)//1024} KB)")
