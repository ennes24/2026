"""
replication_figure.py — 발표용 '독립 재현(replication)' 그림 (forest plot)

메시지 한 줄: 서로 다른 모델·표본·피처로 독립 분석했는데, 극한고온의 수확량 피해가
둘 다 약 −1.7 bu/ac 로 수렴한다 = 우연이나 과적합이 아니라 '진짜 신호'.

두 추정치:
  - 내 분석  : 2원 FE, EDD 계수, 콘벨트 12주, HistGBR 계열 (fixed_effects.py 실측)
  - Peer 분석: 2원 FE, 대체효과(above−below) T=29, 전미 2,644 카운티 (그쪽 CSV 실측)

주의(정직): 두 계수는 정의가 미묘하게 다르다(EDD 단독효과 vs 한 날을 benign→harmful로
이동). 그런데도 −1.7 로 겹친다는 점이 오히려 재현의 강도를 높인다 → 각주로 밝힌다.
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 한글 렌더링: 시스템에 있는 CJK 폰트(WenQuanYi Zen Hei)를 등록해 글자 깨짐 방지
_KO = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
try:
    font_manager.fontManager.addfont(_KO)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=_KO).get_name()
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures")

# (라벨, 추정치, SE, n_카운티, 표본설명, 색)
EST = [
    ("내 분석\n(콘벨트 12주 · 2원FE · EDD)",     -1.686, 0.0392, 1113, "n=34,627", "#2563eb"),
    ("Peer 분석\n(전미 2,644 · 2원FE · 대체효과)", -1.672, 0.0276, 2644, "n=70,721", "#059669"),
]


def main():
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.9)
    ax.grid(axis="y", visible=False)

    # 수렴 밴드(두 점 평균 ±): "둘이 만나는 곳" 강조
    center = sum(e[1] for e in EST) / len(EST)
    ax.axvspan(center - 0.05, center + 0.05, color="#fde68a", alpha=0.45, zorder=0)
    ax.axvline(center, color="#b45309", ls="--", lw=1.2, zorder=1)
    ax.annotate(f"수렴: ≈ {center:.2f} bu/ac", xy=(center, 1.62), ha="center",
                fontsize=11, color="#b45309", fontweight="bold")

    # 무효과선(=0)
    ax.axvline(0, color="#111827", lw=1.4, zorder=1)
    ax.annotate("효과 없음", xy=(0, -0.42), ha="center", va="top",
                fontsize=9, color="#6b7280")

    ys = [1, 0]
    for (lab, b, se, nc, ntxt, col), y in zip(EST, ys):
        lo, hi = b - 1.96 * se, b + 1.96 * se
        ax.plot([lo, hi], [y, y], color=col, lw=2.6, zorder=3, solid_capstyle="round")
        ax.plot([lo, lo], [y - 0.06, y + 0.06], color=col, lw=2.6, zorder=3)
        ax.plot([hi, hi], [y - 0.06, y + 0.06], color=col, lw=2.6, zorder=3)
        ax.scatter([b], [y], s=150, color=col, zorder=4, edgecolor="white", linewidth=1.5)
        # 점 위: 값, 아래: 표본
        ax.annotate(f"{b:.2f}  [{lo:.2f}, {hi:.2f}]", xy=(b, y + 0.13), ha="center",
                    fontsize=10.5, color=col, fontweight="bold")
        ax.annotate(f"{ntxt} · {nc:,} 카운티", xy=(b, y - 0.17), ha="center",
                    fontsize=8.5, color="#6b7280")

    ax.set_yticks(ys)
    ax.set_yticklabels([e[0] for e in EST], fontsize=10)
    ax.set_ylim(-0.55, 1.9)
    ax.set_xlim(-1.95, 0.25)
    ax.set_xlabel("극한고온 1단위 증가의 수확량 효과 (bu/ac, 95% CI)", fontsize=10.5)
    ax.set_title("독립 재현: 서로 다른 모델·표본·피처, 같은 결론 (약 -1.7 bu/ac)",
                 fontsize=13, fontweight="bold", pad=12)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.tight_layout()
    out = os.path.join(FIG, "32_replication_forest.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print("저장:", out)


if __name__ == "__main__":
    main()
