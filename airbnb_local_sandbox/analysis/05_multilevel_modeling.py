"""
05_multilevel_modeling.py  — BigQuery-native data pull.
BQ pulls a 20k listing sample + pre-aggregated weekend stats.
statsmodels fits the mixed-effects models locally on the sample.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import statsmodels.formula.api as smf
import folium
from scipy import stats as sp_stats
sys.path.insert(0, str(Path(__file__).parent))
from bq_helper import q, PROJECT_ID, DATASET

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams["figure.dpi"] = 130
P     = f"`{PROJECT_ID}.{DATASET}`"
PLOTS = Path(__file__).parent / "plots"; PLOTS.mkdir(exist_ok=True)
MAPS  = Path(__file__).parent / "maps";  MAPS.mkdir(exist_ok=True)
STATS = Path(__file__).parent / "stats"; STATS.mkdir(exist_ok=True)
stats = {}

print("="*65); print("  05 — MULTILEVEL STATISTICAL MODELLING"); print("="*65)

# ── Pull modelling dataset from BQ (20k rows — enough for LME) ────────────────
df = q(f"""
    SELECT neighbourhood,
           LOG(avg_price_next_30_days+1)  AS log_price,
           LOG(minimum_nights+1)          AS log_min_nights,
           LOG(total_reviews+1)           AS log_reviews,
           availability_rate_next_30_days AS avail,
           room_type,
           CASE WHEN room_type='Entire home/apt' THEN 1.0 ELSE 0.0 END AS is_entire_home
    FROM {P}.dim_listings
    WHERE avg_price_next_30_days BETWEEN 1 AND 2000
      AND availability_rate_next_30_days IS NOT NULL
    LIMIT 20000
""")
print(f"\n  Sample: {len(df):,} listings across {df['neighbourhood'].nunique()} neighbourhoods")
stats["sample_size"] = len(df)
stats["n_neighbourhoods"] = int(df["neighbourhood"].nunique())

# ── Model A: Random intercept ─────────────────────────────────────────────────
print("\n[Model A] Fitting random-intercept model...")
md_A = smf.mixedlm(
    "log_price ~ log_min_nights + log_reviews + avail + C(room_type)",
    data=df, groups=df["neighbourhood"]
)
fit_A = md_A.fit(reml=True, method="lbfgs")
print(fit_A.summary())

stats["model_A"] = {
    "AIC": round(fit_A.aic, 2),
    "group_var": round(float(fit_A.cov_re.values[0][0]), 6),
    "fixed_effects": {k: round(v, 4) for k, v in fit_A.fe_params.items()}
}
print(f"\n  AIC={stats['model_A']['AIC']}  GroupVar={stats['model_A']['group_var']:.6f}")

# ── 5a Random intercepts bar chart ────────────────────────────────────────────
re_df = pd.DataFrame.from_dict(fit_A.random_effects, orient="index",
                                columns=["random_intercept"])
re_df["random_intercept"] = re_df["random_intercept"].astype(float)
re_df["premium_pct"] = (np.expm1(re_df["random_intercept"]) * 100).round(1)
re_df = re_df.sort_values("random_intercept", ascending=False)
stats["top3_premium"]  = list(re_df.head(3).index)
stats["top3_discount"] = list(re_df.tail(3).index)
print(f"\n  Top premium:  {stats['top3_premium']}")
print(f"  Top discount: {stats['top3_discount']}")

colors = ["#d73027" if v > 0 else "#4575b4" for v in re_df["random_intercept"]]
fig, ax = plt.subplots(figsize=(14,6))
ax.bar(range(len(re_df)), re_df["random_intercept"], color=colors)
ax.set_xticks(range(len(re_df)))
ax.set_xticklabels(re_df.index, rotation=50, ha="right", fontsize=8)
ax.axhline(0, color="black", lw=0.8)
ax.set_title("Neighbourhood Random Intercepts\nRed = above London avg | Blue = below London avg")
ax.set_ylabel("Random Intercept (log-price scale)")
ax2 = ax.twinx()
ax2.set_ylim(ax.get_ylim())
ticks = ax.get_yticks()
ax2.set_yticks(ticks)
ax2.set_yticklabels([f"{(np.expm1(v)*100):.0f}%" for v in ticks], fontsize=8)
ax2.set_ylabel("Price Premium/Discount vs London Average")
plt.tight_layout(); plt.savefig(PLOTS/"05a_random_intercepts.png"); plt.close()

# ── 5b Residual diagnostics ───────────────────────────────────────────────────
resid   = fit_A.resid
fitted  = fit_A.fittedvalues
fig, axes = plt.subplots(1,3,figsize=(15,5))
axes[0].scatter(fitted, resid, alpha=0.15, s=5, color="#4C72B0")
axes[0].axhline(0, color="coral", lw=1.5)
axes[0].set_title("Residuals vs Fitted"); axes[0].set_xlabel("Fitted"); axes[0].set_ylabel("Residuals")
sp_stats.probplot(resid, plot=axes[1])
axes[1].set_title("Q-Q Plot of Residuals")
axes[2].hist(resid, bins=60, color="#55A868", edgecolor="white", lw=0.3)
axes[2].set_title("Residual Distribution"); axes[2].set_xlabel("Residual")
plt.tight_layout(); plt.savefig(PLOTS/"05b_residual_diagnostics.png"); plt.close()

# ── Model B: Random slope on is_entire_home ────────────────────────────────────
print("\n[Model B] Random slope on is_entire_home...")
subset_B = df.sample(min(5000, len(df)), random_state=42)
md_B = smf.mixedlm(
    "log_price ~ log_min_nights + log_reviews + avail + is_entire_home",
    data=subset_B, groups=subset_B["neighbourhood"],
    exog_re=subset_B[["is_entire_home"]]
)
fit_B = md_B.fit(reml=True, method="lbfgs")
print(fit_B.summary())
stats["model_B"] = {
    "AIC": round(fit_B.aic,2),
    "fixed_effects": {k: round(v,4) for k, v in fit_B.fe_params.items()}
}

slopes = {}
for nb, eff in fit_B.random_effects.items():
    if "is_entire_home" in eff.index:
        slopes[nb] = float(eff["is_entire_home"])
slope_s = pd.Series(slopes).sort_values(ascending=False)
stats["max_entire_home_slope"] = slope_s.index[0] if len(slope_s) > 0 else "N/A"

if len(slope_s) > 0:
    fig, ax = plt.subplots(figsize=(14,5))
    ax.bar(range(len(slope_s)), slope_s.values,
           color=["#d73027" if v>0 else "#4575b4" for v in slope_s.values])
    ax.set_xticks(range(len(slope_s)))
    ax.set_xticklabels(slope_s.index, rotation=50, ha="right", fontsize=8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Random Slope: Entire-Home Premium per Neighbourhood")
    ax.set_ylabel("Slope deviation (log-price scale)")
    plt.tight_layout(); plt.savefig(PLOTS/"05c_random_slopes.png"); plt.close()

# ── Model C: Weekend pricing (BQ does group aggregation) ──────────────────────
print("\n[Model C] Weekend pricing model from BQ aggregation...")
wknd_data = q(f"""
    SELECT neighbourhood, is_weekend,
           AVG(price_usd) AS avg_price,
           COUNT(*) AS n
    FROM {P}.fct_availability
    WHERE price_usd BETWEEN 1 AND 5000
      AND neighbourhood IS NOT NULL
    GROUP BY 1, 2
""")
wknd_pivot = wknd_data.pivot(index="neighbourhood", columns="is_weekend", values="avg_price")
wknd_pivot.columns = ["Weekday","Weekend"]
wknd_pivot = wknd_pivot.dropna()
wknd_pivot["premium_pct"] = ((wknd_pivot["Weekend"]/wknd_pivot["Weekday"])-1)*100
avg_wknd_premium = round(wknd_pivot["premium_pct"].mean(), 2)
stats["model_C_weekend_premium_pct"] = avg_wknd_premium
print(f"\n  London-wide weekend premium (from BQ): {avg_wknd_premium}%")

# For the mixed-effects model: pull 50k rows from fct_availability
av_sample = q(f"""
    SELECT neighbourhood, room_type, price_usd,
           CASE WHEN is_weekend THEN 1.0 ELSE 0.0 END AS is_weekend
    FROM {P}.fct_availability
    WHERE price_usd BETWEEN 1 AND 5000
      AND neighbourhood IS NOT NULL
    LIMIT 50000
""")
av_sample["log_price"] = np.log1p(av_sample["price_usd"])
md_C = smf.mixedlm("log_price ~ is_weekend + C(room_type)", data=av_sample,
                    groups=av_sample["neighbourhood"])
fit_C = md_C.fit(reml=True, method="lbfgs")
wknd_coef = fit_C.fe_params.get("is_weekend", 0)
stats["model_C"] = {
    "weekend_coef": round(wknd_coef,6),
    "weekend_premium_pct": round(np.expm1(wknd_coef)*100, 2),
    "AIC": round(fit_C.aic, 2)
}
print(fit_C.summary())
print(f"\n  Model C weekend premium: {stats['model_C']['weekend_premium_pct']}%  AIC={stats['model_C']['AIC']}")

# ── 5d Folium neighbourhood premium map ───────────────────────────────────────
centroids = q(f"""
    SELECT neighbourhood, AVG(latitude) AS lat, AVG(longitude) AS lon
    FROM {P}.dim_listings WHERE latitude IS NOT NULL
    GROUP BY 1
""")
cent_idx = centroids.set_index("neighbourhood")
norm = mcolors.Normalize(re_df["random_intercept"].min(), re_df["random_intercept"].max())
cmap = plt.cm.RdYlGn
m = folium.Map(location=[51.505,-0.118], zoom_start=11, tiles="CartoDB positron")
for neigh, row in re_df.iterrows():
    if neigh not in cent_idx.index: continue
    lat, lon = cent_idx.loc[neigh,["lat","lon"]]
    color = mcolors.to_hex(cmap(norm(row["random_intercept"])))
    folium.CircleMarker(
        location=[lat,lon], radius=max(8, abs(row["premium_pct"])/5),
        color=color, fill=True, fill_color=color, fill_opacity=0.8, weight=1,
        tooltip=f"{neigh}: {row['premium_pct']:+.1f}% vs London avg"
    ).add_to(m)
m.save(MAPS/"05d_neighbourhood_premium_map.html")
print("\n[Map] Neighbourhood premium Folium map saved.")

(STATS/"05_multilevel.json").write_text(json.dumps(stats, indent=2, default=str))
print("\n✅  05_multilevel_modeling DONE")
