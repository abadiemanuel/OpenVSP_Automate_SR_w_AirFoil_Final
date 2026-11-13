"""
Aircraft_Design_w_Airfoils — Post-Generation Analysis & Visualization

Reads the optimization history saved by Pymoo.py and produces:
  1. Aircraft_Design_w_Airfoils.csv - Complete design table with all parameters + objectives
  2. Convergence plots (min/avg/max per generation for each objective)
  3. Hypervolume convergence plot
  4. Airfoil usage frequency across generations
  5. Parallel coordinates plot of final Pareto-front designs
  6. Pairwise objective scatter (Pareto front)

All outputs are saved to Post_Gen_Data/
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe for headless runs
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "Post_Gen_Data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── Helper ───────────────────────────────────────────────────────────────────
def save_fig(fig, name):
    """Save a matplotlib figure to Post_Gen_Data/<name>.png"""
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("Post-Generation Analysis — Aircraft Design w/ Airfoils")
print("=" * 60)

# Final Pareto-optimal population
final_pop_path = os.path.join(SCRIPT_DIR, "final_population.csv")
if os.path.exists(final_pop_path):
    final_df = pd.read_csv(final_pop_path)
    print(f"Loaded final population: {final_df.shape[0]} designs, {final_df.shape[1]} columns")
else:
    print("WARNING: final_population.csv not found — run Pymoo.py first.")
    final_df = pd.DataFrame()

# Convergence data
conv_avg_path = os.path.join(SCRIPT_DIR, "Convergence_avg.csv")
conv_min_path = os.path.join(SCRIPT_DIR, "Convergence_min.csv")
conv_max_path = os.path.join(SCRIPT_DIR, "Convergence_max.csv")
hv_path = os.path.join(SCRIPT_DIR, "HV_normalised.csv")

conv_avg = pd.read_csv(conv_avg_path) if os.path.exists(conv_avg_path) else None
conv_min = pd.read_csv(conv_min_path) if os.path.exists(conv_min_path) else None
conv_max = pd.read_csv(conv_max_path) if os.path.exists(conv_max_path) else None
hv_df = pd.read_csv(hv_path) if os.path.exists(hv_path) else None

# All-generations history
all_gens_path = os.path.join(SCRIPT_DIR, "all_generations.csv")
last10_path = os.path.join(SCRIPT_DIR, "last10_gens.csv")
if os.path.exists(all_gens_path):
    all_gens_df = pd.read_csv(all_gens_path)
elif os.path.exists(last10_path):
    all_gens_df = pd.read_csv(last10_path)
else:
    all_gens_df = None


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  MASTER DESIGN TABLE — Aircraft_Design_w_Airfoils.csv
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating Aircraft_Design_w_Airfoils.csv ---")
if not final_df.empty:
    # Add a design ID column
    final_df.insert(0, "Design_ID", range(1, len(final_df) + 1))
    master_path = os.path.join(OUTPUT_DIR, "Aircraft_Design_w_Airfoils.csv")
    final_df.to_csv(master_path, index=False)
    print(f"  Saved: {master_path}  ({final_df.shape[0]} rows × {final_df.shape[1]} cols)")

    # Print column inventory
    print(f"  Columns: {list(final_df.columns)}")
    airfoil_cols = [c for c in final_df.columns if "Airfoil" in str(c)]
    if airfoil_cols:
        print(f"  Airfoil columns present: {airfoil_cols}")
    else:
        print("  WARNING: No airfoil columns found — check that Pymoo.py names columns correctly")
else:
    print("  Skipped (no final population data)")


# ═══════════════════════════════════════════════════════════════════════════════
#  3.  CONVERGENCE PLOTS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating convergence plots ---")

objective_labels = {
    "Area": ("Wetted Area (m²)", "lower is better"),
    "L2D": ("Lift-to-Drag Ratio", "higher is better"),
    "Config": ("Configuration Score", "higher is better"),
}

if conv_avg is not None and conv_min is not None and conv_max is not None:
    n_gens = len(conv_avg)
    gens = np.arange(1, n_gens + 1)

    # Individual objective convergence with min/avg/max bands
    for obj_key, (ylabel, direction) in objective_labels.items():
        avg_col = f"Avg_{obj_key}"
        min_col = f"min_{obj_key}"
        max_col = f"max_{obj_key}"

        if avg_col in conv_avg.columns and min_col in conv_min.columns and max_col in conv_max.columns:
            fig, ax = plt.subplots(figsize=(8, 5))
            avg_vals = conv_avg[avg_col].to_numpy()
            min_vals = conv_min[min_col].to_numpy()
            max_vals = conv_max[max_col].to_numpy()

            ax.fill_between(gens, min_vals, max_vals, alpha=0.2, color="steelblue", label="Min–Max range")
            ax.plot(gens, avg_vals, "o-", color="steelblue", linewidth=2, markersize=5, label="Average")
            ax.plot(gens, min_vals, "v--", color="green", linewidth=1, markersize=4, label="Min")
            ax.plot(gens, max_vals, "^--", color="red", linewidth=1, markersize=4, label="Max")
            ax.set_xlabel("Generation", fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            ax.set_title(f"{obj_key} Convergence ({direction})", fontsize=13)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            save_fig(fig, f"Convergence_{obj_key}")

    # Combined convergence (all objectives normalized)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Objective Convergence Over Generations", fontsize=15, fontweight="bold")
    for ax, (obj_key, (ylabel, direction)) in zip(axes.flat, objective_labels.items()):
        avg_col = f"Avg_{obj_key}"
        if avg_col in conv_avg.columns:
            ax.plot(gens, conv_avg[avg_col].values, "o-", linewidth=2, markersize=4)
            ax.set_title(f"{obj_key} ({direction})", fontsize=11)
            ax.set_xlabel("Generation")
            ax.set_ylabel(ylabel)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            ax.grid(True, alpha=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_fig(fig, "Convergence_All_Objectives")
else:
    print("  Convergence CSVs not found — skipping convergence plots")


# ═══════════════════════════════════════════════════════════════════════════════
#  4.  HYPERVOLUME CONVERGENCE
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating hypervolume plot ---")
if hv_df is not None and len(hv_df) > 0:
    hv_vals = hv_df.iloc[:, 0].to_numpy()
    gens = np.arange(1, len(hv_vals) + 1)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(gens, hv_vals, "s-", color="darkgreen", linewidth=2, markersize=6)
    ax.set_xlabel("Generation", fontsize=12)
    ax.set_ylabel("Hypervolume (normalised)", fontsize=12)
    ax.set_title("Hypervolume Indicator Convergence", fontsize=13)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, alpha=0.3)
    save_fig(fig, "Hypervolume_Convergence")
else:
    print("  HV data not found — skipping")


# ═══════════════════════════════════════════════════════════════════════════════
#  5.  AIRFOIL USAGE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating airfoil analysis ---")

# Final population airfoil distribution
if not final_df.empty:
    airfoil_cols = [c for c in final_df.columns if "Airfoil" in str(c)]
    if airfoil_cols:
        for col in airfoil_cols:
            counts = final_df[col].value_counts()
            if len(counts) > 0:
                fig, ax = plt.subplots(figsize=(10, 5))
                counts.sort_index().plot(kind="barh", ax=ax, color="teal", edgecolor="black")
                ax.set_xlabel("Count (in final Pareto set)", fontsize=11)
                ax.set_ylabel("Airfoil", fontsize=11)
                ax.set_title(f"Airfoil Selection Frequency — {col}", fontsize=13)
                ax.grid(True, alpha=0.3, axis="x")
                save_fig(fig, f"Airfoil_Frequency_{col}")

# Airfoil trends across generations (if all-gens data available)
if all_gens_df is not None and "Generation" in all_gens_df.columns:
    af_cols = [c for c in all_gens_df.columns if "Airfoil" in str(c)]
    for col in af_cols:
        if col in all_gens_df.columns:
            pivot = all_gens_df.groupby(["Generation", col]).size().unstack(fill_value=0)
            if pivot.shape[1] > 0:
                fig, ax = plt.subplots(figsize=(12, 6))
                pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
                ax.set_xlabel("Generation", fontsize=11)
                ax.set_ylabel("Count", fontsize=11)
                ax.set_title(f"Airfoil Distribution Over Generations — {col}", fontsize=13)
                ax.legend(title="Airfoil", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
                fig.tight_layout()
                save_fig(fig, f"Airfoil_Trend_{col}")


# ═══════════════════════════════════════════════════════════════════════════════
#  6.  DESIGN PARAMETER EVOLUTION ACROSS GENERATIONS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating design parameter evolution plots ---")

if all_gens_df is not None and "Generation" in all_gens_df.columns:
    # Identify numeric design parameters (exclude objectives & generation column)
    obj_and_meta = {"Area", "L2D", "Config", "Generation", "Design_ID"}
    numeric_params = [c for c in all_gens_df.select_dtypes(include=[np.number]).columns
                      if c not in obj_and_meta]

    if numeric_params:
        # --- 6a. Key parameter evolution (mean ± std per generation) ---
        # Select the most design-relevant parameters for a focused plot
        key_params = ["Wing_Span", "Power", "Taper", "Sweep", "Vol_Hor", "Vol_Vert",
                      "r_aft", "f_taper"]
        key_params = [p for p in key_params if p in numeric_params]

        if key_params:
            n_key = len(key_params)
            cols_p = min(3, n_key)
            rows_p = (n_key + cols_p - 1) // cols_p
            fig, axes = plt.subplots(rows_p, cols_p, figsize=(6 * cols_p, 4 * rows_p))
            axes_arr = np.atleast_1d(axes).flat

            for idx, param in enumerate(key_params):
                ax = axes_arr[idx]
                grouped = all_gens_df.groupby("Generation")[param]
                means = grouped.mean()
                stds = grouped.std().fillna(0)
                gens = means.index.to_numpy()

                ax.fill_between(gens, (means - stds).to_numpy(), (means + stds).to_numpy(),
                                alpha=0.2, color="steelblue")
                ax.plot(gens, means.to_numpy(), "o-", color="steelblue", linewidth=2,
                        markersize=4, label="Mean")
                ax.plot(gens, grouped.min().to_numpy(), "v:", color="green", linewidth=1,
                        markersize=3, label="Min")
                ax.plot(gens, grouped.max().to_numpy(), "^:", color="red", linewidth=1,
                        markersize=3, label="Max")
                ax.set_xlabel("Generation")
                ax.set_ylabel(param)
                ax.set_title(f"{param}", fontsize=11)
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)

            # Hide unused subplots
            for idx in range(n_key, rows_p * cols_p):
                axes_arr[idx].set_visible(False)

            fig.suptitle("Key Design Parameter Evolution Over Generations",
                         fontsize=14, fontweight="bold")
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            save_fig(fig, "Parameter_Evolution_Key")

        # --- 6b. All numeric parameter evolution (mean ± std) ---
        # Paginate into groups of 9 for readability
        page_size = 9
        for page_idx in range(0, len(numeric_params), page_size):
            page_params = numeric_params[page_idx:page_idx + page_size]
            n_p = len(page_params)
            cols_p = min(3, n_p)
            rows_p = (n_p + cols_p - 1) // cols_p
            fig, axes = plt.subplots(rows_p, cols_p, figsize=(6 * cols_p, 4 * rows_p))
            axes_arr = np.atleast_1d(axes).flat

            for idx, param in enumerate(page_params):
                ax = axes_arr[idx]
                grouped = all_gens_df.groupby("Generation")[param]
                means = grouped.mean()
                stds = grouped.std().fillna(0)
                gens = means.index.to_numpy()

                ax.fill_between(gens, (means - stds).to_numpy(), (means + stds).to_numpy(),
                                alpha=0.2, color="darkorange")
                ax.plot(gens, means.to_numpy(), "o-", color="darkorange", linewidth=2,
                        markersize=4)
                ax.set_xlabel("Generation")
                ax.set_ylabel(param)
                ax.set_title(param, fontsize=10)
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
                ax.grid(True, alpha=0.3)

            for idx in range(n_p, rows_p * cols_p):
                axes_arr[idx].set_visible(False)

            page_num = page_idx // page_size + 1
            fig.suptitle(f"Design Parameter Evolution (Page {page_num})",
                         fontsize=13, fontweight="bold")
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            save_fig(fig, f"Parameter_Evolution_All_Page{page_num}")

        # --- 6c. Per-generation summary statistics CSV ---
        gen_summary = all_gens_df.groupby("Generation")[numeric_params].agg(["mean", "std", "min", "max"])
        gen_summary.columns = [f"{p}_{stat}" for p, stat in gen_summary.columns]
        gen_summary_path = os.path.join(OUTPUT_DIR, "Parameter_Evolution_Stats.csv")
        gen_summary.to_csv(gen_summary_path)
        print(f"  Saved: {gen_summary_path}")

    # --- 6d. Parameter–Objective correlation heatmap ---
    print("  Generating parameter-objective correlation heatmap...")
    obj_cols_present = [c for c in ["Area", "L2D", "Config"]
                        if c in all_gens_df.columns]
    param_cols_for_corr = [c for c in numeric_params if c in all_gens_df.columns]
    if obj_cols_present and param_cols_for_corr:
        corr_matrix = all_gens_df[param_cols_for_corr + obj_cols_present].corr()
        # Extract just the parameter-vs-objective block
        corr_block = corr_matrix.loc[param_cols_for_corr, obj_cols_present]

        fig, ax = plt.subplots(figsize=(8, max(6, len(param_cols_for_corr) * 0.4)))
        im = ax.imshow(corr_block.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(len(obj_cols_present)))
        ax.set_xticklabels(obj_cols_present, fontsize=10)
        ax.set_yticks(range(len(param_cols_for_corr)))
        ax.set_yticklabels(param_cols_for_corr, fontsize=9)
        fig.colorbar(im, ax=ax, label="Pearson Correlation")
        ax.set_title("Design Parameter vs Objective Correlation", fontsize=13)
        fig.tight_layout()
        save_fig(fig, "Parameter_Objective_Correlation")

        # Save correlation data as CSV too
        corr_block.to_csv(os.path.join(OUTPUT_DIR, "Parameter_Objective_Correlation.csv"))

else:
    print("  No all-generations data available — skipping parameter evolution plots")


# ═══════════════════════════════════════════════════════════════════════════════
#  7.  PAIRWISE OBJECTIVE SCATTER (PARETO FRONT)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating Pareto front scatter plots ---")
obj_cols_in_df: dict[str, str | None] = {"Area": None, "L2D": None, "Config": None}
if not final_df.empty:
    for key in obj_cols_in_df:
        if key in final_df.columns:
            obj_cols_in_df[key] = key
    available_objs = {k: v for k, v in obj_cols_in_df.items() if v is not None}
    obj_keys = list(available_objs.keys())

    if len(obj_keys) >= 2:
        import itertools
        pairs = list(itertools.combinations(obj_keys, 2))
        n_pairs = len(pairs)
        cols_plot = min(3, n_pairs)
        rows_plot = (n_pairs + cols_plot - 1) // cols_plot
        fig, axes = plt.subplots(rows_plot, cols_plot, figsize=(6 * cols_plot, 5 * rows_plot))
        if n_pairs == 1:
            axes = np.array([axes])
        axes = axes.flat

        for idx, (o1, o2) in enumerate(pairs):
            ax = axes[idx]
            ax.scatter(final_df[o1], final_df[o2], c="steelblue", edgecolors="black", s=50, alpha=0.7)
            ax.set_xlabel(o1, fontsize=11)
            ax.set_ylabel(o2, fontsize=11)
            ax.set_title(f"{o1} vs {o2}", fontsize=12)
            ax.grid(True, alpha=0.3)

        # Hide unused subplots
        for idx in range(n_pairs, rows_plot * cols_plot):
            axes[idx].set_visible(False)

        fig.suptitle("Pairwise Objective Trade-offs (Final Pareto Front)", fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        save_fig(fig, "Pareto_Pairwise_Scatter")
    else:
        print("  Not enough objective columns for scatter plots")
else:
    print("  Skipped (no final population data)")


# ═══════════════════════════════════════════════════════════════════════════════
#  8.  CATEGORICAL DESIGN VARIABLE DISTRIBUTION (FINAL POPULATION)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating categorical variable distributions ---")
categorical_vars = ["Wing_Type", "Wing_Position", "Tail_Type", "Fuselage_NoseCap", "Fuselage_TailCap",
                    "Wing_Airfoil", "HTail_Airfoil", "VTail_Airfoil"]

if not final_df.empty:
    present_cats = [c for c in categorical_vars if c in final_df.columns]
    if present_cats:
        n_cats = len(present_cats)
        cols_plot = min(3, n_cats)
        rows_plot = (n_cats + cols_plot - 1) // cols_plot
        fig, axes = plt.subplots(rows_plot, cols_plot, figsize=(6 * cols_plot, 4 * rows_plot))
        if n_cats == 1:
            axes = np.array([axes])
        axes_arr = np.atleast_1d(axes)
        axes_flat = axes_arr.flat

        for idx, cat in enumerate(present_cats):
            ax = axes_flat[idx]
            counts = final_df[cat].value_counts()
            counts.plot(kind="bar", ax=ax, color="coral", edgecolor="black")
            ax.set_title(cat, fontsize=11)
            ax.set_ylabel("Count")
            ax.tick_params(axis="x", rotation=45)
            ax.grid(True, alpha=0.3, axis="y")

        for idx in range(n_cats, rows_plot * cols_plot):
            axes_flat[idx].set_visible(False)

        fig.suptitle("Design Variable Distributions (Final Pareto Front)", fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        save_fig(fig, "Categorical_Variable_Distribution")


# ═══════════════════════════════════════════════════════════════════════════════
#  9.  SUMMARY STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Generating summary statistics ---")
if not final_df.empty:
    summary_path = os.path.join(OUTPUT_DIR, "Design_Summary_Statistics.csv")
    numeric_cols = final_df.select_dtypes(include=[np.number]).columns
    summary = final_df[numeric_cols].describe().T
    summary.to_csv(summary_path)
    print(f"  Saved: {summary_path}")

    # Top designs by L/D
    if "L2D" in final_df.columns:
        top_ld_cols = ["Design_ID", "Wing_Span", "Taper", "Sweep",
                       "Wing_Airfoil", "HTail_Airfoil", "VTail_Airfoil",
                       "Wing_Type", "Tail_Type", "Area", "L2D", "Config"]
        # Only include columns that actually exist
        available_top_cols = [c for c in top_ld_cols if c in final_df.columns]
        top_ld = final_df.nlargest(5, "L2D")[available_top_cols]
        top_path = os.path.join(OUTPUT_DIR, "Top5_Designs_by_L2D.csv")
        top_ld.to_csv(top_path, index=False)
        print(f"  Saved: {top_path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  DONE
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"All post-generation outputs saved to: {OUTPUT_DIR}")
print(f"{'=' * 60}")
