"""
03_multivariate_eda.py  — BigQuery-native.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 130
P     = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65); print("  03 — MULTIVARIATE EDA"); print("="*65)

# ── 3a Pair-plot: sample 5k rows from BQ ──────────────────────────────────────
sample = q(f"""
    SELECT LOG(avg_price_next_30_days+1) AS log_price,
           LOG(minimum_nights+1) AS log_min_nights,
           LOG(total_reviews+1) AS log_reviews,
           availability_rate_next_30_days AS avail,
           room_type
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 5000
""")
g = sns.pairplot(sample, hue="room_type", diag_kind="kde",
                 vars=["log_price","log_min_nights","log_reviews","avail"],
                 plot_kws=dict(alpha=0.3, s=8), palette="Set2")
g.figure.suptitle("Pair-plot: log(Price), log(Min Nights), log(Reviews), Availability — by Room Type",
                   y=1.01, fontsize=11)
plt.savefig(PLOTS/"03a_pairplot.png", bbox_inches="tight"); plt.close()
print("[3a] Pair-plot saved.")

# ── 3b Pivot heatmap: median price by room_type × neighbourhood (top 15) ──────
pivot_data = q(f"""
    SELECT neighbourhood, room_type,
           ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)],0) AS median_price
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND neighbourhood IN (
          SELECT neighbourhood FROM {P}.dim_listings
          GROUP BY neighbourhood ORDER BY COUNT(*) DESC LIMIT 15
      )
    GROUP BY 1,2
""")
pivot = pivot_data.pivot(index="neighbourhood", columns="room_type", values="median_price")
stats["pivot_shape"] = list(pivot.shape)
print(f"\n[3b] Pivot table shape: {pivot.shape}")
fig, ax = plt.subplots(figsize=(11,8))
sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd",
            linewidths=0.4, cbar_kws={"label":"Median Price (USD)"}, ax=ax)
ax.set_title("Median Price by Neighbourhood × Room Type (Top 15 Neighbourhoods)")
plt.tight_layout(); plt.savefig(PLOTS/"03b_price_pivot_heatmap.png"); plt.close()

# ── 3c PCA biplot — 4 features, download 20k rows ─────────────────────────────
pca_data = q(f"""
    SELECT avg_price_next_30_days AS price,
           minimum_nights, total_reviews,
           availability_rate_next_30_days AS avail,
           room_type
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 20000
""")
feat_cols = ["price","minimum_nights","total_reviews","avail"]
X = StandardScaler().fit_transform(pca_data[feat_cols].fillna(0))
pca = PCA(n_components=2, random_state=42)
comps = pca.fit_transform(X)
stats["pca_explained_variance"] = [round(v,4) for v in pca.explained_variance_ratio_]
print(f"\n[3c] PCA variance: {stats['pca_explained_variance']}")

palette = {"Entire home/apt":"#4C72B0","Private room":"#55A868",
           "Hotel room":"#C44E52","Shared room":"#8172B2"}
fig, ax = plt.subplots(figsize=(10,7))
for rt, idx in pca_data.groupby("room_type").groups.items():
    ax.scatter(comps[idx,0], comps[idx,1], s=5, alpha=0.35,
               color=palette.get(rt,"grey"), label=rt)
loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
for i, feat in enumerate(feat_cols):
    ax.annotate("", xy=(loadings[i,0]*4, loadings[i,1]*4), xytext=(0,0),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
    ax.text(loadings[i,0]*4.5, loadings[i,1]*4.5, feat, fontsize=9, ha="center")
ax.set_title(f"PCA Biplot — PC1 {pca.explained_variance_ratio_[0]*100:.1f}%  "
             f"PC2 {pca.explained_variance_ratio_[1]*100:.1f}%")
ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
ax.legend(title="Room Type", markerscale=4, fontsize=9)
ax.axhline(0,lw=0.5,color="grey"); ax.axvline(0,lw=0.5,color="grey")
plt.tight_layout(); plt.savefig(PLOTS/"03c_pca_biplot.png"); plt.close()

# ── 3d 3-variable bubble: price × availability, bubble = √reviews ─────────────
bubble = q(f"""
    SELECT avg_price_next_30_days AS price,
           availability_rate_next_30_days AS avail,
           total_reviews, room_type
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 1000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 5000
""")
fig, ax = plt.subplots(figsize=(10,7))
for rt, grp in bubble.groupby("room_type"):
    ax.scatter(grp["avail"], grp["price"],
               s=np.sqrt(grp["total_reviews"].clip(upper=500))*5,
               alpha=0.4, color=palette.get(rt,"grey"), label=rt)
ax.set_title("Price × Availability — bubble size = √Reviews")
ax.set_xlabel("Availability Rate"); ax.set_ylabel("Price (USD, capped £1000)")
ax.legend(title="Room Type", markerscale=0.7)
plt.tight_layout(); plt.savefig(PLOTS/"03d_bubble_chart.png"); plt.close()

# ── 3e Neighbourhood-level multivariate — BQ fully aggregated ─────────────────
neigh_multi = q(f"""
    SELECT n.neighbourhood,
           n.avg_price_usd, n.total_listings, n.total_hosts,
           ROUND(n.total_listings / NULLIF(n.total_hosts,0),1) AS listings_per_host,
           ROUND((n.max_price_usd - n.min_price_usd),0) AS price_range
    FROM {P}.dim_neighbourhoods n
    ORDER BY n.avg_price_usd DESC
""")
stats["neighbourhood_price_range"] = neigh_multi.set_index("neighbourhood")["avg_price_usd"].to_dict()
print(f"\n[3e] Neighbourhood stats:\n{neigh_multi.head(5).to_string(index=False)}")

fig, ax = plt.subplots(figsize=(12,8))
sc = ax.scatter(neigh_multi["total_listings"], neigh_multi["avg_price_usd"],
                s=neigh_multi["listings_per_host"]*30,
                c=neigh_multi["price_range"], cmap="viridis", alpha=0.85,
                edgecolors="white", lw=0.8)
cbar = plt.colorbar(sc, ax=ax); cbar.set_label("Price Range (max−min USD)")
for _, row in neigh_multi.iterrows():
    ax.annotate(row["neighbourhood"][:14], (row["total_listings"], row["avg_price_usd"]),
                fontsize=7, alpha=0.8, xytext=(3,3), textcoords="offset points")
ax.set_title("Neighbourhood: Supply × Avg Price\nbubble size = listings per host | colour = price range")
ax.set_xlabel("Total Listings"); ax.set_ylabel("Avg Price (USD)")
plt.tight_layout(); plt.savefig(PLOTS/"03e_neighbourhood_multivariate.png"); plt.close()

(STATS/"03_multivariate.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  03_multivariate_eda DONE")
