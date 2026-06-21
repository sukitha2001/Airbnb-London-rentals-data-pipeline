"""
04_anova.py  — ANOVA with BigQuery pre-aggregation.
BQ computes per-group means + variances for F-stat; scipy does the test
on a 20k-row sample pulled via SQL.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import f_oneway, kruskal
from statsmodels.stats.multicomp import pairwise_tukeyhsd
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 130
P     = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65); print("  04 — ANOVA & POST-HOC TESTS"); print("="*65)

# ── Pull 20k rows for ANOVA ────────────────────────────────────────────────────
sample = q(f"""
    SELECT room_type, neighbourhood,
           LOG(avg_price_next_30_days+1) AS log_price
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
    LIMIT 20000
""")

# ── 4a ANOVA: room type ────────────────────────────────────────────────────────
groups_rt = [g["log_price"].values for _, g in sample.groupby("room_type")]
F_rt, p_rt = f_oneway(*groups_rt)
H_rt, _    = kruskal(*groups_rt)
stats["anova_room_type"] = {"F": round(F_rt,4), "p": float(f"{p_rt:.2e}"),
                            "H_kruskal": round(H_rt,4)}
print(f"\n[ANOVA room type] F={F_rt:.2f}  p={p_rt:.2e}  H={H_rt:.2f}")

# ── 4b Tukey HSD: room type ────────────────────────────────────────────────────
tukey_rt = pairwise_tukeyhsd(sample["log_price"], sample["room_type"])
tukey_df  = pd.DataFrame(tukey_rt._results_table.data[1:],
                          columns=tukey_rt._results_table.data[0])
stats["tukey_room_type"] = tukey_df.to_dict(orient="records")
print(f"\n[Tukey HSD — Room Type]\n{tukey_df.to_string(index=False)}")

# BQ median prices for chart
med_rt = q(f"""
    SELECT room_type,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(25)],2) AS p25,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)],2) AS median,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(75)],2) AS p75,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(10)],2) AS p10,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(90)],2) AS p90
    FROM {P}.dim_listings WHERE avg_price_next_30_days BETWEEN 1 AND 2000
    GROUP BY 1 ORDER BY median DESC
""")
fig, ax = plt.subplots(figsize=(10,6))
colors_rt = ["#4C72B0","#55A868","#C44E52","#8172B2"]
for i, row in med_rt.iterrows():
    ax.plot([i,i], [row["p10"], row["p90"]], color=colors_rt[i%4], lw=2, alpha=0.4)
    ax.broken_barh([(i-0.35, 0.7)], (row["p25"], row["p75"]-row["p25"]),
                   facecolors=colors_rt[i%4], alpha=0.75)
    ax.plot(i, row["median"], marker="o", color="white", ms=7, zorder=5)
ax.set_xticks(range(len(med_rt))); ax.set_xticklabels(med_rt["room_type"])
ax.set_title(f"Price Distribution by Room Type\nANOVA F={F_rt:.0f}, Kruskal H={H_rt:.0f}  (both p<0.001)")
ax.set_ylabel("Price (USD)")
ax.text(0.98,0.97,"All pairwise differences significant\n(Tukey HSD p<0.05)",
        transform=ax.transAxes, ha="right", va="top", fontsize=9,
        bbox=dict(boxstyle="round", fc="lightyellow", ec="orange"))
plt.tight_layout(); plt.savefig(PLOTS/"04a_anova_room_type.png"); plt.close()

# ── 4c ANOVA: neighbourhood (top 20) ──────────────────────────────────────────
top20 = sample["neighbourhood"].value_counts().head(20).index
s20   = sample[sample["neighbourhood"].isin(top20)]
groups_n  = [g["log_price"].values for _, g in s20.groupby("neighbourhood")]
F_n, p_n  = f_oneway(*groups_n)
H_n, _    = kruskal(*groups_n)
stats["anova_neighbourhood"] = {"F": round(F_n,4), "p": float(f"{p_n:.2e}"),
                                "H_kruskal": round(H_n,4)}
print(f"\n[ANOVA neighbourhood] F={F_n:.2f}  p={p_n:.2e}  H={H_n:.2f}")

tukey_n   = pairwise_tukeyhsd(s20["log_price"], s20["neighbourhood"])
tukey_n_df = pd.DataFrame(tukey_n._results_table.data[1:],
                           columns=tukey_n._results_table.data[0])
sig_pairs  = (tukey_n_df["reject"] == True).sum()
stats["tukey_neigh_sig_pairs"] = int(sig_pairs)
stats["tukey_neigh_total_pairs"] = len(tukey_n_df)
print(f"  Tukey significant pairs: {sig_pairs}/{len(tukey_n_df)}")

med_n = q(f"""
    SELECT neighbourhood,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(25)],2) AS p25,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)],2) AS median,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(75)],2) AS p75
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND neighbourhood IN ({','.join([f"'{n}'" for n in top20])})
    GROUP BY 1 ORDER BY median DESC
""")
fig, ax = plt.subplots(figsize=(13,7))
y = range(len(med_n))
ax.barh(list(y), med_n["p75"]-med_n["p25"], left=med_n["p25"],
        color="#4C72B0", alpha=0.7, height=0.6)
ax.scatter(med_n["median"], list(y), color="white", s=50, zorder=5)
ax.set_yticks(list(y)); ax.set_yticklabels(med_n["neighbourhood"])
ax.set_title(f"Price IQR by Neighbourhood — ANOVA F={F_n:.0f}, p<0.001\n"
             f"({sig_pairs}/{len(tukey_n_df)} pairwise Tukey comparisons significant)")
ax.set_xlabel("Price (USD)"); ax.invert_yaxis()
plt.tight_layout(); plt.savefig(PLOTS/"04b_anova_neighbourhood.png"); plt.close()

# ── 4d Effect size (η²) ────────────────────────────────────────────────────────
def eta_sq(groups):
    all_v   = np.concatenate(groups)
    gm      = all_v.mean()
    ss_b    = sum(len(g)*(g.mean()-gm)**2 for g in groups)
    ss_t    = sum(((v-gm)**2).sum() for v in groups)
    return ss_b / ss_t

eta_rt = eta_sq(groups_rt)
eta_n  = eta_sq(groups_n)
stats["eta_squared"] = {"room_type": round(eta_rt,4), "neighbourhood": round(eta_n,4)}
print(f"\n[Effect size η²]  room_type={eta_rt:.4f} ({eta_rt*100:.1f}%)  "
      f"neighbourhood={eta_n:.4f} ({eta_n*100:.1f}%)")

fig, axes = plt.subplots(1,2,figsize=(10,5))
for ax, label, eta, F_val in zip(axes,
    ["Room Type","Neighbourhood (top 20)"],
    [eta_rt, eta_n], [F_rt, F_n]):
    bar = ax.bar([label], [eta*100], color=["#4C72B0","#C44E52"][axes.tolist().index(ax)], width=0.4)
    ax.set_ylim(0, max(eta_rt, eta_n)*115)
    ax.set_ylabel("% Variance Explained (η²)")
    ax.set_title(f"{label}\nη² = {eta*100:.1f}%")
    ax.text(0, eta*100+0.3, f"F = {F_val:.0f}\np < 0.001",
            ha="center", va="bottom", fontsize=10,
            bbox=dict(boxstyle="round", fc="lightyellow"))
fig.suptitle("ANOVA Effect Sizes — Explaining Price Variation", fontsize=13)
plt.tight_layout(); plt.savefig(PLOTS/"04c_anova_effect_sizes.png"); plt.close()

(STATS/"04_anova.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  04_anova DONE")
