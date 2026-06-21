"""
01_univariate_eda.py  — all aggregations run IN BigQuery.
Only small summary tables come back to Python for plotting.
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
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.15)
plt.rcParams["figure.dpi"] = 130
P  = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
MAPS  = Path(__file__).parent / "maps";  MAPS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65)
print("  01 — UNIVARIATE EDA  (BigQuery-native)")
print("="*65)

# ── 1a Price distribution — BQ computes percentiles & histogram bins ──────────
price_stats = q(f"""
    SELECT
        ROUND(AVG(avg_price_next_30_days), 2)              AS mean,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)], 2) AS median,
        ROUND(STDDEV(avg_price_next_30_days), 2)           AS std,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(25)], 2) AS p25,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(75)], 2) AS p75,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(99)], 2) AS p99,
        COUNT(*) AS n_listings
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days IS NOT NULL AND avg_price_next_30_days > 0
""")
print(f"\n[Price stats]\n{price_stats.to_string(index=False)}")
stats["price_stats"] = price_stats.iloc[0].to_dict()

# Histogram bins computed in BQ — only 50 count rows downloaded
price_hist = q(f"""
    SELECT
        FLOOR(avg_price_next_30_days / 20) * 20 AS bin_start,
        COUNT(*) AS count
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 1000
    GROUP BY 1 ORDER BY 1
""")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].bar(price_hist["bin_start"], price_hist["count"], width=18, color="#4C72B0", edgecolor="white", lw=0.3)
axes[0].axvline(float(price_stats["median"]), color="coral", lw=2, label=f"Median £{float(price_stats['median']):.0f}")
axes[0].axvline(float(price_stats["mean"]),   color="gold",  lw=2, label=f"Mean £{float(price_stats['mean']):.0f}")
axes[0].set_title("Price Distribution (capped £1–£1000)"); axes[0].set_xlabel("Price (USD)"); axes[0].legend()

log_hist = q(f"""
    SELECT ROUND(LOG(avg_price_next_30_days+1), 1) AS log_bin, COUNT(*) AS count
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days > 0
    GROUP BY 1 ORDER BY 1
""")
axes[1].bar(log_hist["log_bin"], log_hist["count"], width=0.08, color="#55A868", edgecolor="white", lw=0.2)
axes[1].set_title("Log(Price+1) Distribution — approximately normal"); axes[1].set_xlabel("log(Price+1)")
plt.tight_layout(); plt.savefig(PLOTS/"01a_price_distribution.png"); plt.close()

# ── 1b Room type counts ────────────────────────────────────────────────────────
room_counts = q(f"""
    SELECT room_type, COUNT(*) AS count,
           ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) AS pct
    FROM {P}.dim_listings GROUP BY 1 ORDER BY 2 DESC
""")
print(f"\n[Room types]\n{room_counts.to_string(index=False)}")
stats["room_type_counts"] = room_counts.to_dict(orient="records")

colors_rt = ["#4C72B0","#55A868","#C44E52","#8172B2"]
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(room_counts["room_type"], room_counts["count"], color=colors_rt[:len(room_counts)], edgecolor="white")
for bar, row in zip(bars, room_counts.itertuples()):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+200,
            f"{row.count:,}\n({row.pct}%)", ha="center", va="bottom", fontsize=9)
ax.set_title("Listing Count by Room Type"); ax.set_ylabel("Count")
plt.tight_layout(); plt.savefig(PLOTS/"01b_room_type.png"); plt.close()

# ── 1c Top 20 neighbourhoods ───────────────────────────────────────────────────
neigh_counts = q(f"""
    SELECT neighbourhood, COUNT(*) AS count
    FROM {P}.dim_listings GROUP BY 1 ORDER BY 2 DESC LIMIT 20
""")
fig, ax = plt.subplots(figsize=(12, 6))
neigh_counts.sort_values("count").plot(kind="barh", x="neighbourhood", y="count", ax=ax, color="#4C72B0", legend=False)
ax.set_title("Top 20 Neighbourhoods by Listing Count"); ax.set_xlabel("Listings")
plt.tight_layout(); plt.savefig(PLOTS/"01c_neighbourhood_top20.png"); plt.close()
print(f"\n[Top neighbourhood] {neigh_counts.iloc[0]['neighbourhood']} ({neigh_counts.iloc[0]['count']:,} listings)")

# ── 1d Reviews distribution ────────────────────────────────────────────────────
rev_stats = q(f"""
    SELECT
        ROUND(AVG(total_reviews),2) AS mean,
        APPROX_QUANTILES(total_reviews,100)[OFFSET(50)] AS median,
        ROUND(COUNTIF(total_reviews=0)*100.0/COUNT(*),1) AS pct_zero
    FROM {P}.dim_listings
""")
print(f"\n[Reviews]\n{rev_stats.to_string(index=False)}")
stats["review_stats"] = rev_stats.iloc[0].to_dict()

rev_hist = q(f"""
    SELECT LEAST(FLOOR(total_reviews/10)*10, 200) AS bin, COUNT(*) AS count
    FROM {P}.dim_listings GROUP BY 1 ORDER BY 1
""")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(rev_hist["bin"], rev_hist["count"], width=8, color="#C44E52", edgecolor="white", lw=0.3)
ax.set_title("Total Reviews Distribution (200+ grouped into last bin)")
ax.set_xlabel("Total Reviews"); ax.set_ylabel("Listings")
plt.tight_layout(); plt.savefig(PLOTS/"01d_reviews_distribution.png"); plt.close()

# ── 1e Minimum nights distribution ────────────────────────────────────────────
mn_stats = q(f"""
    SELECT
        APPROX_QUANTILES(minimum_nights,100)[OFFSET(50)] AS median,
        ROUND(COUNTIF(minimum_nights=1)*100.0/COUNT(*),1) AS pct_1_night,
        ROUND(COUNTIF(minimum_nights>=30)*100.0/COUNT(*),1) AS pct_30plus
    FROM {P}.dim_listings
""")
print(f"\n[Min nights]\n{mn_stats.to_string(index=False)}")
stats["min_nights_stats"] = mn_stats.iloc[0].to_dict()

mn_hist = q(f"""
    SELECT LEAST(minimum_nights, 30) AS nights, COUNT(*) AS count
    FROM {P}.dim_listings GROUP BY 1 ORDER BY 1
""")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(mn_hist["nights"], mn_hist["count"], width=0.7, color="#8172B2", edgecolor="white", lw=0.3)
ax.set_title("Minimum Nights Distribution (30+ grouped)"); ax.set_xlabel("Minimum Nights")
plt.tight_layout(); plt.savefig(PLOTS/"01e_minimum_nights.png"); plt.close()

# ── 1f Availability rate distribution ─────────────────────────────────────────
avail_stats = q(f"""
    SELECT
        ROUND(AVG(availability_rate_next_30_days),3) AS mean,
        ROUND(APPROX_QUANTILES(availability_rate_next_30_days,100)[OFFSET(50)],3) AS median
    FROM {P}.dim_listings WHERE availability_rate_next_30_days IS NOT NULL
""")
print(f"\n[Availability]\n{avail_stats.to_string(index=False)}")
stats["availability_stats"] = avail_stats.iloc[0].to_dict()

avail_hist = q(f"""
    SELECT ROUND(availability_rate_next_30_days, 1) AS bin, COUNT(*) AS count
    FROM {P}.dim_listings WHERE availability_rate_next_30_days IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(avail_hist["bin"], avail_hist["count"], width=0.08, color="#CCB974", edgecolor="white", lw=0.3)
ax.axvline(float(avail_stats["mean"]), color="coral", lw=2, label=f"Mean={float(avail_stats['mean']):.2f}")
ax.set_title("Availability Rate — last 30 days of snapshot"); ax.set_xlabel("Fraction Available"); ax.legend()
plt.tight_layout(); plt.savefig(PLOTS/"01f_availability.png"); plt.close()

# ── 1g Static geographic price map (sample 20k lat/lon rows from BQ) ──────────
coords = q(f"""
    SELECT latitude, longitude, avg_price_next_30_days AS price
    FROM {P}.dim_listings
    WHERE latitude IS NOT NULL AND avg_price_next_30_days IS NOT NULL
    LIMIT 20000
""")
coords["price_q"] = pd.qcut(coords["price"], q=5, labels=["Q1 cheapest","Q2","Q3","Q4","Q5 priciest"])
colors_q = ["#2166ac","#74add1","#fee090","#f46d43","#d73027"]
fig, ax = plt.subplots(figsize=(12, 10))
for i, (label, grp) in enumerate(coords.groupby("price_q", observed=True)):
    ax.scatter(grp["longitude"], grp["latitude"], s=2, alpha=0.35, color=colors_q[i], label=label, rasterized=True)
ax.set_title("London Airbnb Listings — Price Quintile Map", fontsize=14)
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
ax.legend(title="Price Quintile", markerscale=5, loc="upper left")
plt.tight_layout(); plt.savefig(PLOTS/"01g_listings_price_map.png", dpi=130); plt.close()

# ── 1h Folium interactive map ──────────────────────────────────────────────────
norm  = plt.Normalize(coords["price"].quantile(0.05), coords["price"].quantile(0.95))
cmap  = plt.cm.RdYlGn_r
m = folium.Map(location=[51.505, -0.118], zoom_start=11, tiles="CartoDB positron")
for _, row in coords.sample(5000, random_state=42).iterrows():
    color = mcolors.to_hex(cmap(norm(row["price"])))
    folium.CircleMarker([row["latitude"], row["longitude"]],
                        radius=3, color=color, fill=True, fill_opacity=0.7, weight=0).add_to(m)
m.save(MAPS/"01h_price_map.html")
print("\n[Maps] Static + Folium maps saved.")

(STATS/"01_univariate.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  01_univariate_eda DONE")
