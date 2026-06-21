#!/usr/bin/env zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RUN="conda run -n ml_env python3"

echo "════════════════════════════════════════════════════════════════"
echo "  AIRBNB LONDON — FULL ANALYSIS PIPELINE"
echo "════════════════════════════════════════════════════════════════"

echo "\n▶  [00] Loading data from BigQuery → Parquet cache..."
$RUN 00_load_data.py
echo "\n▶  [01] Univariate EDA..."
$RUN 01_univariate_eda.py
echo "\n▶  [02] Bivariate EDA..."
$RUN 02_bivariate_eda.py
echo "\n▶  [03] Multivariate EDA..."
$RUN 03_multivariate_eda.py
echo "\n▶  [04] ANOVA & Post-hoc tests..."
$RUN 04_anova.py
echo "\n▶  [05] Multilevel Statistical Modelling..."
$RUN 05_multilevel_modeling.py
echo "\n▶  [06] Clustering..."
$RUN 06_clustering.py

echo "\n════════════════════════════════════════════════════════════════"
echo "  ✅  ALL SCRIPTS COMPLETE"
echo "  Plots → $SCRIPT_DIR/plots/"
echo "  Maps  → $SCRIPT_DIR/maps/"
echo "  Stats → $SCRIPT_DIR/stats/"
echo "════════════════════════════════════════════════════════════════"
