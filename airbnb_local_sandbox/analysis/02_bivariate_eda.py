"""
02_bivariate_eda.py  — all aggregations in BigQuery SQL.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 130
P     = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65); print("  02 — BIVARIATE EDA"); print("="*65)

# ── 2a Price by room type — BQ computes quartiles ─────────────────────────────
price_room = q(f"""
    SELECT room_type,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(25)],2) AS p25,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)],2) AS median,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(75)],2) AS p75,
        ROUND(AVG(avg_price_next_30_days),2) AS mean,
        COUNT(*) AS n
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
    GROUP BY 1 ORDER BY median DESC
""")
print(f"\n[Price by room type]\n{price_room.to_string(index=False)}")
stats["price_by_room_type"] = price_room.to_dict(orient="records")

fig, ax = plt.subplots(figsize=(10, 6))
colors_rt = ["#4C72B0","#55A868","#C44E52","#8172B2"]
for i, row in price_room.iterrows():
    ax.broken_barh([(row["p25"], row["p75"]-row["p25"])], (i-0.3, 0.6),
                   facecolors=colors_rt[i % 4], alpha=0.7)
    ax.plot([row["median"], row["median"]], [i-0.3, i+0.3], color="white", lw=2)
    ax.plot(row["mean"], i, marker="D", color="black", ms=6, zorder=5)
    ax.text(row["p75"]+2, i, f"  £{row['median']:.0f} (median)", va="center", fontsize=9)
ax.set_yticks(range(len(price_room))); ax.set_yticklabels(price_room["room_type"])
ax.set_title("Price IQR by Room Type  (◆=mean, bar=IQR, white line=median)")
ax.set_xlabel("Price (USD)"); ax.invert_yaxis()
plt.tight_layout(); plt.savefig(PLOTS/"02a_price_by_room_type.png"); plt.close()

# ── 2b Price by neighbourhood (top 20) ────────────────────────────────────────
price_neigh = q(f"""
    SELECT neighbourhood,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(25)],2) AS p25,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(50)],2) AS median,
        ROUND(APPROX_QUANTILES(avg_price_next_30_days,100)[OFFSET(75)],2) AS p75,
        COUNT(*) AS n
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
    GROUP BY 1 HAVING n >= 100
    ORDER BY median DESC LIMIT 20
""")
print(f"\n[Top 5 priciest neighbourhoods]\n{price_neigh.head(5).to_string(index=False)}")
stats["price_by_neighbourhood"] = price_neigh.to_dict(orient="records")

fig, ax = plt.subplots(figsize=(12, 8))
y = range(len(price_neigh))
ax.barh(list(y), price_neigh["p75"]-price_neigh["p25"],
        left=price_neigh["p25"], color="#4C72B0", alpha=0.7, height=0.6)
ax.scatter(price_neigh["median"], list(y), color="white", s=40, zorder=5)
ax.set_yticks(list(y)); ax.set_yticklabels(price_neigh["neighbourhood"])
ax.set_title("Price IQR by Neighbourhood — Top 20 by Median Price")
ax.set_xlabel("Price (USD)"); ax.invert_yaxis()
plt.tight_layout(); plt.savefig(PLOTS/"02b_price_by_neighbourhood.png"); plt.close()

# ── 2c Price vs Reviews — BQ correlation ──────────────────────────────────────
corr_rev = q(f"""
    SELECT
        ROUND(CORR(LOG(avg_price_next_30_days+1), LOG(total_reviews+1)), 4) AS r_log_log,
        ROUND(CORR(avg_price_next_30_days, total_reviews), 4)               AS r_raw
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days > 0 AND total_reviews >= 0
""")
print(f"\n[Correlation price vs reviews]\n{corr_rev.to_string(index=False)}")
stats["corr_price_reviews"] = corr_rev.iloc[0].to_dict()

scatter_rev = q(f"""
    SELECT LOG(avg_price_next_30_days+1) AS log_price,
           LOG(total_reviews+1) AS log_reviews
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
    LIMIT 10000
""")
fig, ax = plt.subplots(figsize=(9,6))
ax.scatter(scatter_rev["log_reviews"], scatter_rev["log_price"], alpha=0.2, s=8, color="#4C72B0")
m,b = np.polyfit(scatter_rev["log_reviews"], scatter_rev["log_price"], 1)
xs = np.linspace(scatter_rev["log_reviews"].min(), scatter_rev["log_reviews"].max(), 100)
ax.plot(xs, m*xs+b, color="coral", lw=2)
r = float(corr_rev["r_log_log"])
ax.set_title(f"log(Price+1) vs log(Reviews+1)  [Pearson r = {r:.3f}]")
ax.set_xlabel("log(Reviews+1)"); ax.set_ylabel("log(Price+1)")
plt.tight_layout(); plt.savefig(PLOTS/"02c_price_vs_reviews.png"); plt.close()

# ── 2d Price vs Availability ───────────────────────────────────────────────────
corr_av = q(f"""
    SELECT ROUND(CORR(avg_price_next_30_days, availability_rate_next_30_days), 4) AS r
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days > 0 AND availability_rate_next_30_days IS NOT NULL
""")
scatter_av = q(f"""
    SELECT availability_rate_next_30_days AS avail,
           avg_price_next_30_days AS price
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 1000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 10000
""")
r_av = float(corr_av["r"])
stats["corr_price_availability"] = r_av
print(f"\n[Correlation price vs availability]: r={r_av:.4f}")
fig, ax = plt.subplots(figsize=(9,6))
ax.scatter(scatter_av["avail"], scatter_av["price"], alpha=0.2, s=8, color="#55A868")
m2,b2 = np.polyfit(scatter_av["avail"], scatter_av["price"], 1)
xs2 = np.linspace(0, 1, 100)
ax.plot(xs2, m2*xs2+b2, color="coral", lw=2, label=f"r = {r_av:.3f}")
ax.set_title("Price vs 30-Day Availability Rate")
ax.set_xlabel("Availability Rate"); ax.set_ylabel("Price (USD)"); ax.legend()
plt.tight_layout(); plt.savefig(PLOTS/"02d_price_vs_availability.png"); plt.close()

# ── 2e Weekend vs Weekday price ────────────────────────────────────────────────
wknd = q(f"""
    SELECT neighbourhood,
        ROUND(AVG(CASE WHEN is_weekend THEN price_usd END), 2) AS weekend_avg,
        ROUND(AVG(CASE WHEN NOT is_weekend THEN price_usd END), 2) AS weekday_avg,
        ROUND((AVG(CASE WHEN is_weekend THEN price_usd END) /
               NULLIF(AVG(CASE WHEN NOT is_weekend THEN price_usd END),0) - 1)*100, 2) AS premium_pct
    FROM {P}.fct_availability
    WHERE price_usd > 0 AND neighbourhood IS NOT NULL
    GROUP BY 1
    HAVING weekday_avg IS NOT NULL AND weekend_avg IS NOT NULL
    ORDER BY premium_pct DESC
""")
print(f"\n[Weekend premium — top 5]\n{wknd.head(5).to_string(index=False)}")
avg_prem = round(float(wknd["premium_pct"].mean()), 2)
stats["weekend_premium"] = {"avg_pct": avg_prem, "top5": wknd.head(5).to_dict(orient="records")}
print(f"  London-wide avg weekend premium: {avg_prem}%")

top15 = wknd.head(15)
fig, ax = plt.subplots(figsize=(13,6))
x = range(len(top15))
w = 0.35
ax.bar([i-w/2 for i in x], top15["weekday_avg"], w, label="Weekday", color="steelblue")
ax.bar([i+w/2 for i in x], top15["weekend_avg"],  w, label="Weekend",  color="coral")
ax.set_xticks(list(x)); ax.set_xticklabels(top15["neighbourhood"], rotation=40, ha="right", fontsize=8)
ax.set_title("Weekday vs Weekend Avg Price — Top 15 by Weekend Premium")
ax.set_ylabel("Avg Price (USD)"); ax.legend()
plt.tight_layout(); plt.savefig(PLOTS/"02e_weekend_weekday_price.png"); plt.close()

# ── 2f Monthly review trend ───────────────────────────────────────────────────
monthly = q(f"""
    SELECT FORMAT_DATE('%Y-%m', review_date) AS yr_mo, COUNT(*) AS reviews
    FROM {P}.fct_reviews
    WHERE review_date >= '2018-01-01'
    GROUP BY 1 ORDER BY 1
""")
monthly["yr_mo"] = pd.to_datetime(monthly["yr_mo"])
peak = monthly.loc[monthly["reviews"].idxmax(), "yr_mo"]
stats["peak_review_month"] = str(peak)
print(f"\n[Peak review month]: {peak.strftime('%Y-%m')}")
fig, ax = plt.subplots(figsize=(14,5))
ax.plot(monthly["yr_mo"], monthly["reviews"], color="#4C72B0", lw=1.5)
ax.fill_between(monthly["yr_mo"], monthly["reviews"], alpha=0.2, color="#4C72B0")
ax.set_title("Monthly Review Volume (2018–present)"); ax.set_ylabel("Reviews")
plt.tight_layout(); plt.savefig(PLOTS/"02f_monthly_review_trend.png"); plt.close()

# ── 2g Correlation matrix ─────────────────────────────────────────────────────
corr_mat = q(f"""
    SELECT
        ROUND(CORR(current_price, minimum_nights),3)                      AS price_vs_min_nights,
        ROUND(CORR(current_price, total_reviews),3)                       AS price_vs_reviews,
        ROUND(CORR(current_price, availability_rate_next_30_days),3)      AS price_vs_avail,
        ROUND(CORR(minimum_nights, total_reviews),3)                      AS min_nights_vs_reviews,
        ROUND(CORR(minimum_nights, availability_rate_next_30_days),3)     AS min_nights_vs_avail,
        ROUND(CORR(total_reviews, availability_rate_next_30_days),3)      AS reviews_vs_avail
    FROM {P}.dim_listings
    WHERE current_price > 0 AND availability_rate_next_30_days IS NOT NULL
""")
print(f"\n[Correlation matrix]\n{corr_mat.to_string(index=False)}")
stats["correlation_matrix"] = corr_mat.iloc[0].to_dict()

labels = ["Price","Min Nights","Reviews","Avail Rate"]
c = corr_mat.iloc[0]
mat = np.array([
    [1, c["price_vs_min_nights"],  c["price_vs_reviews"],     c["price_vs_avail"]],
    [c["price_vs_min_nights"], 1,  c["min_nights_vs_reviews"],c["min_nights_vs_avail"]],
    [c["price_vs_reviews"], c["min_nights_vs_reviews"], 1,    c["reviews_vs_avail"]],
    [c["price_vs_avail"],   c["min_nights_vs_avail"],  c["reviews_vs_avail"], 1],
])
mask = np.triu(np.ones_like(mat, dtype=bool))
fig, ax = plt.subplots(figsize=(8,6))
sns.heatmap(mat, mask=mask, annot=True, fmt=".2f", cmap="coolwarm",
            center=0, xticklabels=labels, yticklabels=labels, square=True, ax=ax)
ax.set_title("Pearson Correlation Matrix (computed in BigQuery)")
plt.tight_layout(); plt.savefig(PLOTS/"02g_correlation_heatmap.png"); plt.close()

(STATS/"02_bivariate.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  02_bivariate_eda DONE")
