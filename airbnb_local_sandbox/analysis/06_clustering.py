"""
06_clustering.py  — BigQuery-native.
BQ provides 20k rows for K-Means/DBSCAN; neighbourhood stats fully aggregated in BQ.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import folium
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.decomposition import PCA
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 130
P     = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
MAPS  = Path(__file__).parent / "maps";  MAPS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65); print("  06 — CLUSTERING"); print("="*65)

# ── Pull feature matrix from BQ (20k rows) ─────────────────────────────────────
raw = q(f"""
    SELECT listing_id, neighbourhood, room_type, latitude, longitude,
           avg_price_next_30_days  AS price,
           availability_rate_next_30_days AS avail,
           minimum_nights, total_reviews
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 20000
""")
print(f"\n  Feature matrix pulled: {len(raw):,} rows")

dummies = pd.get_dummies(raw["room_type"], prefix="rt", drop_first=True)
X_df = pd.concat([
    raw[["price","avail","minimum_nights","total_reviews"]].clip(
        upper=raw[["price","avail","minimum_nights","total_reviews"]].quantile(0.99), axis=1),
    dummies
], axis=1).fillna(0)

scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X_df)

# ── 6a Elbow + Silhouette ─────────────────────────────────────────────────────
K_range = range(2,11)
inertias, sils = [], []
for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    inertias.append(km.inertia_)
    sils.append(silhouette_score(X_scaled, labels, sample_size=3000, random_state=42))

best_k = list(K_range)[sils.index(max(sils))]
stats["best_k"] = int(best_k)
stats["best_silhouette"] = round(max(sils), 4)
print(f"\n  Best K={best_k}  silhouette={max(sils):.4f}")

fig, axes = plt.subplots(1,2,figsize=(14,5))
axes[0].plot(list(K_range), inertias, marker="o", color="steelblue", lw=2)
axes[0].axvline(best_k, color="coral", lw=1.5, linestyle="--", label=f"Best K={best_k}")
axes[0].set_title("Elbow Method"); axes[0].set_xlabel("K"); axes[0].set_ylabel("Inertia"); axes[0].legend()
axes[1].plot(list(K_range), sils, marker="s", color="coral", lw=2)
axes[1].axvline(best_k, color="steelblue", lw=1.5, linestyle="--", label=f"Best K={best_k}")
axes[1].set_title("Silhouette Score"); axes[1].set_xlabel("K"); axes[1].set_ylabel("Score"); axes[1].legend()
plt.tight_layout(); plt.savefig(PLOTS/"06a_elbow_silhouette.png"); plt.close()

# ── 6b K-Means final ─────────────────────────────────────────────────────────
km_final      = KMeans(n_clusters=best_k, random_state=42, n_init=10)
cluster_labels = km_final.fit_predict(X_scaled)
raw["cluster"] = cluster_labels
stats["cluster_sizes"] = raw["cluster"].value_counts().sort_index().to_dict()
print(f"\n  Cluster sizes: {stats['cluster_sizes']}")

palette = sns.color_palette("Set2", best_k)
pca     = PCA(n_components=2, random_state=42)
coords  = pca.fit_transform(X_scaled)
stats["pca_variance"] = [round(v,4) for v in pca.explained_variance_ratio_]

fig, ax = plt.subplots(figsize=(11,8))
for k in range(best_k):
    mask = cluster_labels == k
    ax.scatter(coords[mask,0], coords[mask,1], s=8, alpha=0.4,
               color=palette[k], label=f"Cluster {k}")
c2d = pca.transform(km_final.cluster_centers_)
ax.scatter(c2d[:,0], c2d[:,1], marker="X", s=250, c="black", zorder=6, label="Centroid")
ax.set_title(f"K-Means (K={best_k}) — PCA 2-D  "
             f"[PC1 {pca.explained_variance_ratio_[0]*100:.1f}%  PC2 {pca.explained_variance_ratio_[1]*100:.1f}%]")
ax.set_xlabel("PC1"); ax.set_ylabel("PC2"); ax.legend(markerscale=2)
plt.tight_layout(); plt.savefig(PLOTS/"06b_kmeans_pca.png"); plt.close()

# ── 6c Silhouette diagram ─────────────────────────────────────────────────────
sil_vals = silhouette_samples(X_scaled, cluster_labels)
avg_sil  = silhouette_score(X_scaled, cluster_labels, sample_size=5000, random_state=42)
stats["final_silhouette"] = round(avg_sil, 4)

fig, ax = plt.subplots(figsize=(9,6))
y_lo = 10
for k in range(best_k):
    k_sil  = sorted(sil_vals[cluster_labels==k])
    y_hi   = y_lo + len(k_sil)
    ax.fill_betweenx(np.arange(y_lo, y_hi), 0, k_sil, alpha=0.75, color=palette[k], label=f"Cluster {k}")
    ax.text(-0.05, y_lo+0.5*len(k_sil), str(k), fontsize=9)
    y_lo = y_hi + 10
ax.axvline(avg_sil, color="red", lw=2, linestyle="--", label=f"Avg = {avg_sil:.3f}")
ax.set_title(f"Silhouette Plot per Cluster (avg = {avg_sil:.3f})")
ax.set_xlabel("Silhouette Coefficient"); ax.legend()
plt.tight_layout(); plt.savefig(PLOTS/"06c_silhouette_plot.png"); plt.close()

# ── 6d Cluster profile heatmap ────────────────────────────────────────────────
prof_cols = ["price","avail","minimum_nights","total_reviews"]
profile   = raw.groupby("cluster")[prof_cols].mean().round(2)
stats["cluster_profiles"] = profile.to_dict()
profile_z = ((profile - profile.mean()) / profile.std()).astype(float)
print(f"\n  Cluster profiles:\n{profile.to_string()}")

fig, ax = plt.subplots(figsize=(10,4))
sns.heatmap(profile_z.T, cmap="coolwarm", center=0, annot=True, fmt=".2f",
            linewidths=0.5, cbar_kws={"label":"Z-score"}, ax=ax)
ax.set_title(f"Cluster Profiles — Normalised Feature Means (K={best_k})")
ax.set_xlabel("Cluster"); ax.set_ylabel("Feature")
plt.tight_layout(); plt.savefig(PLOTS/"06d_cluster_profile_heatmap.png"); plt.close()

# ── 6e Room type % per cluster ────────────────────────────────────────────────
room_dist = (raw.groupby(["cluster","room_type"]).size()
             .unstack(fill_value=0)
             .apply(lambda x: x/x.sum()*100, axis=1).round(1))
stats["room_pct_per_cluster"] = room_dist.to_dict()
print(f"\n  Room type % per cluster:\n{room_dist.to_string()}")
room_dist.plot(kind="bar", figsize=(10,5), colormap="Set2", edgecolor="white")
plt.title("Room Type % per Cluster"); plt.ylabel("%"); plt.xticks(rotation=0)
plt.legend(title="Room Type", bbox_to_anchor=(1,1))
plt.tight_layout(); plt.savefig(PLOTS/"06e_cluster_room_dist.png"); plt.close()

# ── 6f DBSCAN ─────────────────────────────────────────────────────────────────
X_2d      = PCA(n_components=2, random_state=42).fit_transform(X_scaled)
db        = DBSCAN(eps=0.4, min_samples=15)
db_labels = db.fit_predict(X_2d)
n_db      = len(set(db_labels)) - (1 if -1 in db_labels else 0)
n_noise   = int(np.sum(db_labels==-1))
stats["dbscan"] = {"n_clusters": n_db, "n_noise": n_noise,
                   "noise_pct": round(n_noise/len(db_labels)*100, 2)}
print(f"\n  DBSCAN: {n_db} clusters | {n_noise} noise ({stats['dbscan']['noise_pct']}%)")

palette_db = sns.color_palette("tab10", n_db)
fig, ax = plt.subplots(figsize=(11,8))
for k in sorted(set(db_labels)):
    mask = db_labels==k
    if k==-1:
        ax.scatter(X_2d[mask,0], X_2d[mask,1], c="lightgrey", s=8, alpha=0.3,
                   label=f"Noise ({n_noise:,})", zorder=1)
    else:
        ax.scatter(X_2d[mask,0], X_2d[mask,1], s=10, alpha=0.5,
                   color=palette_db[k], label=f"Cluster {k}", zorder=2)
ax.set_title(f"DBSCAN — {n_db} clusters | {n_noise:,} outliers ({stats['dbscan']['noise_pct']}%)")
ax.set_xlabel("PC1"); ax.set_ylabel("PC2"); ax.legend(markerscale=2)
plt.tight_layout(); plt.savefig(PLOTS/"06f_dbscan.png"); plt.close()

# ── 6g Neighbourhood clustering — fully in BQ ─────────────────────────────────
neigh_stats = q(f"""
    SELECT neighbourhood, avg_price_usd, total_listings, total_hosts,
           min_price_usd, max_price_usd
    FROM {P}.dim_neighbourhoods
""")
Xn = StandardScaler().fit_transform(neigh_stats[["avg_price_usd","total_listings","total_hosts","min_price_usd","max_price_usd"]].fillna(0))
neigh_labels = KMeans(n_clusters=3, random_state=42, n_init=20).fit_predict(Xn)
neigh_stats["cluster"] = neigh_labels
neigh_profile = neigh_stats.groupby("cluster")[["avg_price_usd","total_listings","total_hosts"]].mean().round(1)
stats["neighbourhood_cluster_profiles"] = neigh_profile.to_dict()
stats["neighbourhood_clusters"] = neigh_stats.groupby("cluster")["neighbourhood"].apply(list).to_dict()
print(f"\n  Neighbourhood cluster profiles:\n{neigh_profile.to_string()}")

palette_n = sns.color_palette("Set1",3)
fig, ax = plt.subplots(figsize=(12,8))
for k in range(3):
    mask = neigh_stats["cluster"]==k
    sub  = neigh_stats[mask]
    ax.scatter(sub["total_listings"], sub["avg_price_usd"],
               s=150, color=palette_n[k], alpha=0.85, label=f"Cluster {k}",
               edgecolors="white", lw=0.8)
    for _, row in sub.iterrows():
        ax.annotate(row["neighbourhood"][:14], (row["total_listings"],row["avg_price_usd"]),
                    fontsize=7, alpha=0.8, xytext=(3,3), textcoords="offset points")
ax.set_title("Neighbourhood Clusters: Supply vs Avg Price")
ax.set_xlabel("Total Listings"); ax.set_ylabel("Avg Price (USD)"); ax.legend()
plt.tight_layout(); plt.savefig(PLOTS/"06g_neighbourhood_clusters.png"); plt.close()

# ── 6h Folium interactive cluster map ─────────────────────────────────────────
map_data = q(f"""
    SELECT latitude, longitude, room_type
    FROM {P}.dim_listings
    WHERE latitude IS NOT NULL
    LIMIT 8000
""")
map_data["cluster"] = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit_predict(
    StandardScaler().fit_transform(
        pd.get_dummies(map_data["room_type"]).fillna(0)
    )
)
hex_colors = [mcolors.to_hex(c) for c in palette[:best_k]]
m = folium.Map(location=[51.505,-0.118], zoom_start=11, tiles="CartoDB positron")
for _, row in map_data.iterrows():
    c = int(row["cluster"])
    folium.CircleMarker(
        [row["latitude"],row["longitude"]],
        radius=3, color=hex_colors[c], fill=True,
        fill_color=hex_colors[c], fill_opacity=0.7, weight=0,
        tooltip=f"Cluster {c}"
    ).add_to(m)
legend_html = '<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;border:1px solid grey;border-radius:8px;padding:10px;font-size:12px"><b>Clusters</b><br>'
for k, col in enumerate(hex_colors):
    legend_html += f'<i style="background:{col};width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:6px;"></i>Cluster {k}<br>'
legend_html += '</div>'
m.get_root().html.add_child(folium.Element(legend_html))
m.save(MAPS/"06h_listing_clusters_map.html")
print("\n[Map] Folium cluster map saved.")

(STATS/"06_clustering.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  06_clustering DONE")
