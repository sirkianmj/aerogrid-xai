"""Build Notebook 03 - Receiver efficiency surface.

Run once from the repo root:
    python scripts/build_notebook_03.py

Generates: notebooks/03_receiver_efficiency_surface.ipynb
"""

from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
CELLS = []

CELLS.append(nbf.v4.new_markdown_cell(
    "# Notebook 03 - Receiver Efficiency Surface\n\n"
    "**Sprint:** S2c (Stage A - Coupled Electro-Thermal Physics)\n"
    "**Roadmap task:** s2-6\n"
    "**Specification reference:** Section 33.3 (two-node lumped thermal "
    "model) and Section 33.4 (thermal runaway boundary).\n\n"
    "## Scientific gate\n\n"
    "> 3D plot; labeled first-order lumped approximation.\n\n"
    "## What this notebook does\n\n"
    "1. Sweeps eta_total(P_incident, v_airflow) at reference ambient "
    "(25 C) using the actual ThermalModel.steady_state solver.\n"
    "2. Produces a 3D surface plot labeled as a first-order lumped "
    "approximation.\n"
    "3. Overlays the thermal-runaway boundary P_max(v).\n"
    "4. Shows 1D slices at a fixed airflow for a range of ambient "
    "temperatures.\n"
    "5. Marks the Han et al. degradation regime (80-90 C T_plc) as a "
    "labelled band.\n\n"
    "**Citation note.** The Han et al. regime boundary is taken from the "
    "docstring of PLCParams.t_max_kelvin in app.physics.receiver. The "
    "primary citation (spec Rev. 6 Section 6, Han et al., Matter & Light, "
    "2026) has not been cross-verified against the published paper in "
    "this environment. Until that verification is done, the band is "
    "labelled CITATION PENDING."
))

CELLS.append(nbf.v4.new_markdown_cell("## Setup"))

CELLS.append(nbf.v4.new_code_cell(
    "%matplotlib inline\n\n"
    "import sys\n"
    "from pathlib import Path\n\n"
    "repo_root = Path.cwd().parent if Path.cwd().name == \"notebooks\" "
    "else Path.cwd()\n"
    "sys.path.insert(0, str(repo_root / \"backend\"))\n\n"
    "import matplotlib.pyplot as plt\n"
    "import numpy as np\n\n"
    "from app.physics.receiver import eta_total\n"
    "from app.physics.thermal import (\n"
    "    REFERENCE_T_AMBIENT_K,\n"
    "    default_model,\n"
    ")\n\n"
    "model = default_model()\n"
    "print(f\"Ambient reference: {REFERENCE_T_AMBIENT_K:.2f} K \"\n"
    "      f\"({REFERENCE_T_AMBIENT_K - 273.15:.2f} C)\")\n"
    "print(f\"PLC t_max:         {model.receiver.plc.t_max_kelvin:.2f} K \"\n"
    "      f\"({model.receiver.plc.t_max_kelvin - 273.15:.2f} C)\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 1 - Grid sweep\n\n"
    "Sweep incident power and airflow at reference ambient. For each "
    "grid point we solve for the steady state, then evaluate the total "
    "efficiency.\n\n"
    "Efficiency is computed as eta_total(T_plc, T_plc, T_te) because "
    "the current lumped model uses a single TE node temperature. This "
    "matches the convention inside ThermalModel.dt_te_dt."
))

CELLS.append(nbf.v4.new_code_cell(
    "P_range = np.linspace(1.0, 40.0, 41)\n"
    "v_range = np.linspace(0.5, 20.0, 21)\n"
    "P_grid, v_grid = np.meshgrid(P_range, v_range)\n\n"
    "eta_grid = np.full_like(P_grid, np.nan, dtype=float)\n"
    "T_plc_grid = np.full_like(P_grid, np.nan, dtype=float)\n"
    "converged = np.zeros_like(P_grid, dtype=bool)\n\n"
    "for i, v in enumerate(v_range):\n"
    "    for j, P in enumerate(P_range):\n"
    "        ss = model.steady_state(float(P), float(v), "
    "REFERENCE_T_AMBIENT_K)\n"
    "        if ss is None:\n"
    "            continue\n"
    "        t_plc, t_te = ss\n"
    "        eta_grid[i, j] = eta_total(t_plc, t_plc, t_te, "
    "model.receiver)\n"
    "        T_plc_grid[i, j] = t_plc\n"
    "        converged[i, j] = True\n\n"
    "n_total = converged.size\n"
    "n_conv = int(converged.sum())\n"
    "print(f\"Grid points: {n_total}, converged: {n_conv} \"\n"
    "      f\"({100.0 * n_conv / n_total:.1f}%)\")\n"
    "print(f\"eta_total range: [{np.nanmin(eta_grid):.4f}, "
    "{np.nanmax(eta_grid):.4f}]\")\n"
    "print(f\"T_plc range:     [{np.nanmin(T_plc_grid):.1f} K, \"\n"
    "      f\"{np.nanmax(T_plc_grid):.1f} K]\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 2 - Efficiency surface\n\n"
    "3D surface of eta_total(P, v) at 25 C ambient. **This surface is "
    "a first-order lumped approximation.** The multiplicative form "
    "eta_PLC * eta_TE assumes the PLC and TE layers can be electrically "
    "combined as a simple product; real PV-TE tandem extraction depends "
    "on circuit topology (series vs. independently extracted junctions) "
    "and is not rigorously derivable as a product without justification "
    "(spec Section 33.2).\n\n"
    "Non-converged grid points are masked (visible as NaN holes)."
))

CELLS.append(nbf.v4.new_code_cell(
    "fig = plt.figure(figsize=(11, 7))\n"
    "ax = fig.add_subplot(111, projection=\"3d\")\n\n"
    "eta_masked = np.ma.masked_invalid(eta_grid)\n"
    "surf = ax.plot_surface(\n"
    "    P_grid, v_grid, eta_masked,\n"
    "    cmap=\"viridis\", edgecolor=\"none\", alpha=0.9,\n"
    ")\n\n"
    "ax.set_xlabel(\"Incident power P [W]\")\n"
    "ax.set_ylabel(\"Airflow v [m/s]\")\n"
    "ax.set_zlabel(\"eta_total [-]\")\n"
    "ax.set_title(\n"
    "    \"Receiver efficiency surface eta_total(P, v), T_amb = 25 C | \"\n"
    "    \"FIRST-ORDER LUMPED APPROXIMATION (spec Section 33.2)\",\n"
    "    fontsize=10,\n"
    ")\n"
    "fig.colorbar(surf, ax=ax, shrink=0.6, label=\"eta_total [-]\")\n"
    "plt.tight_layout()\n"
    "plt.show()\n\n"
    "print(\"Surface axes: P (W), v (m/s), eta_total (dimensionless).\")\n"
    "print(\"Labeled: FIRST-ORDER LUMPED APPROXIMATION.\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 3 - Thermal-runaway boundary overlay\n\n"
    "The boundary P_max(v) is computed with thermal_runaway_boundary, "
    "which bisects on the predicate \"a safe steady state exists\" "
    "(T_plc < t_max_kelvin). This is the edge of the efficiency surface "
    "in the power direction."
))

CELLS.append(nbf.v4.new_code_cell(
    "v_for_boundary = np.linspace(1.0, 20.0, 20)\n"
    "p_max_curve = np.array([\n"
    "    model.thermal_runaway_boundary(float(v), "
    "REFERENCE_T_AMBIENT_K)\n"
    "    for v in v_for_boundary\n"
    "])\n\n"
    "fig = plt.figure(figsize=(11, 7))\n"
    "ax = fig.add_subplot(111, projection=\"3d\")\n\n"
    "surf = ax.plot_surface(\n"
    "    P_grid, v_grid, eta_masked,\n"
    "    cmap=\"viridis\", edgecolor=\"none\", alpha=0.55,\n"
    ")\n\n"
    "eta_at_pmax = []\n"
    "for v, p_max in zip(v_for_boundary, p_max_curve):\n"
    "    ss = model.steady_state(float(p_max), float(v), "
    "REFERENCE_T_AMBIENT_K)\n"
    "    eta_at_pmax.append(\n"
    "        eta_total(ss[0], ss[0], ss[1], model.receiver) if ss "
    "else np.nan\n"
    "    )\n"
    "ax.plot(\n"
    "    p_max_curve, v_for_boundary, eta_at_pmax,\n"
    "    color=\"red\", linewidth=2.5, "
    "label=\"P_max(v) thermal-runaway boundary\",\n"
    ")\n\n"
    "ax.set_xlabel(\"Incident power P [W]\")\n"
    "ax.set_ylabel(\"Airflow v [m/s]\")\n"
    "ax.set_zlabel(\"eta_total [-]\")\n"
    "ax.set_title(\n"
    "    \"Efficiency surface with thermal-runaway boundary | \"\n"
    "    \"FIRST-ORDER LUMPED APPROXIMATION\",\n"
    "    fontsize=10,\n"
    ")\n"
    "ax.legend(loc=\"upper right\")\n"
    "fig.colorbar(surf, ax=ax, shrink=0.6, label=\"eta_total [-]\")\n"
    "plt.tight_layout()\n"
    "plt.show()\n\n"
    "print(f\"P_max at v = 1 m/s:  {p_max_curve[0]:.2f} W\")\n"
    "print(f\"P_max at v = 5 m/s:  \"\n"
    "      f\"{model.thermal_runaway_boundary(5.0, "
    "REFERENCE_T_AMBIENT_K):.2f} W\")\n"
    "print(f\"P_max at v = 20 m/s: {p_max_curve[-1]:.2f} W\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 4 - Ambient temperature slices\n\n"
    "1D slices at v = 5 m/s for four ambient temperatures. The surface "
    "shifts left (lower usable power) as ambient rises, because the "
    "convective and radiative sinks have less margin."
))

CELLS.append(nbf.v4.new_code_cell(
    "ambients_c = [0.0, 15.0, 25.0, 40.0]\n"
    "ambients_k = [c + 273.15 for c in ambients_c]\n"
    "v_slice = 5.0\n"
    "P_slice = np.linspace(0.5, 60.0, 120)\n\n"
    "fig, ax = plt.subplots(figsize=(10, 6))\n\n"
    "for c, t_amb in zip(ambients_c, ambients_k):\n"
    "    eta_line = []\n"
    "    for P in P_slice:\n"
    "        ss = model.steady_state(float(P), v_slice, float(t_amb))\n"
    "        if ss is None:\n"
    "            eta_line.append(np.nan)\n"
    "        else:\n"
    "            t_plc, t_te = ss\n"
    "            eta_line.append(eta_total(t_plc, t_plc, t_te, "
    "model.receiver))\n"
    "    ax.plot(P_slice, np.array(eta_line) * 100.0,\n"
    "            linewidth=2.0, label=f\"T_amb = {c:.0f} C\")\n\n"
    "ax.axvspan(15.0, 25.0, color=\"orange\", alpha=0.10)\n"
    "ax.set_xlabel(\"Incident power P [W]\")\n"
    "ax.set_ylabel(\"eta_total [%]\")\n"
    "ax.set_title(\n"
    "    \"eta_total(P) slices at v = 5 m/s | \"\n"
    "    \"FIRST-ORDER LUMPED APPROXIMATION\",\n"
    "    fontsize=10,\n"
    ")\n"
    "ax.grid(alpha=0.3)\n"
    "ax.legend(loc=\"lower right\")\n"
    "plt.tight_layout()\n"
    "plt.show()\n\n"
    "print(\"Slices computed at v = 5 m/s for T_amb in {0, 15, 25, 40} C.\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 5 - Han et al. degradation regime\n\n"
    "At reference conditions the model places T_plc inside the 80-90 C "
    "window observed by Han et al. This is the s2-4 gate. Here we show "
    "the same band in the (P, v) plane as a shaded region.\n\n"
    "**CITATION PENDING.** The numerical value of the band is taken "
    "from the docstring of PLCParams.t_max_kelvin in "
    "app.physics.receiver. The primary citation (spec Rev. 6 Section 6) "
    "has not been cross-verified against the published paper in this "
    "environment. Until that verification is done, the band is a "
    "labelled tolerance, not a verified published measurement."
))

CELLS.append(nbf.v4.new_code_cell(
    "fig, ax = plt.subplots(figsize=(10, 6))\n\n"
    "T_plc_c = T_plc_grid - 273.15\n"
    "masked_T = np.ma.masked_invalid(T_plc_c)\n"
    "cf = ax.contourf(P_grid, v_grid, masked_T, levels=15, "
    "cmap=\"inferno\")\n"
    "fig.colorbar(cf, ax=ax, label=\"T_plc [C]\")\n\n"
    "ax.contour(P_grid, v_grid, masked_T,\n"
    "           levels=[80.0, 90.0], colors=[\"cyan\", \"magenta\"],\n"
    "           linewidths=2.5, linestyles=[\"--\", \"--\"])\n"
    "ax.plot([], [], color=\"cyan\", linestyle=\"--\", linewidth=2.5,\n"
    "        label=\"T_plc = 80 C\")\n"
    "ax.plot([], [], color=\"magenta\", linestyle=\"--\", "
    "linewidth=2.5,\n"
    "        label=\"T_plc = 90 C\")\n\n"
    "ax.set_xlabel(\"Incident power P [W]\")\n"
    "ax.set_ylabel(\"Airflow v [m/s]\")\n"
    "ax.set_title(\n"
    "    \"T_plc(P, v) with Han et al. 80-90 C band (CITATION PENDING)\",\n"
    "    fontsize=10,\n"
    ")\n"
    "ax.legend(loc=\"lower right\")\n"
    "plt.tight_layout()\n"
    "plt.show()\n\n"
    "print(\"Han et al. regime: 80-90 C (353.15-363.15 K).\")\n"
    "print(\"Status: CITATION PENDING (spec Rev. 6 Section 6 not "
    "provided).\")"
))

CELLS.append(nbf.v4.new_markdown_cell(
    "## Section 6 - Gate summary\n\n"
    "The s2-6 gate is satisfied:\n\n"
    "> 3D plot; labeled first-order lumped approximation.\n\n"
    "Every surface and slice above carries the label. The Han et al. "
    "regime is displayed but explicitly marked as CITATION PENDING "
    "until the primary source is provided."
))

CELLS.append(nbf.v4.new_code_cell(
    "t_max_c = model.receiver.plc.t_max_kelvin - 273.15\n"
    "assert 80.0 <= t_max_c <= 90.0, f\"Han regime outside 80-90 C: "
    "{t_max_c}\"\n"
    "assert 5.0 < model.thermal_runaway_boundary(\n"
    "    5.0, REFERENCE_T_AMBIENT_K) < 500.0\n"
    "assert eta_grid[converged].min() >= 0.0\n"
    "assert eta_grid[converged].max() <= 1.0\n\n"
    "print(\"Notebook 03 - Receiver efficiency surface\")\n"
    "print(\"=\" * 60)\n"
    "print(f\"Grid points:              {n_total}\")\n"
    "print(f\"Converged:                {n_conv}\")\n"
    "print(f\"eta_total range:          \"\n"
    "      f\"[{np.nanmin(eta_grid):.4f}, {np.nanmax(eta_grid):.4f}]\")\n"
    "print(f\"P_max at v = 5 m/s:       \"\n"
    "      f\"{model.thermal_runaway_boundary(5.0, "
    "REFERENCE_T_AMBIENT_K):.2f} W\")\n"
    "print(f\"Han regime (from docstring): {t_max_c:.2f} C  "
    "(CITATION PENDING)\")\n"
    "print()\n"
    "print(\"ALL GATES PASS\")"
))

NB["cells"] = CELLS
NB["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (aerogrid)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/03_receiver_efficiency_surface.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(NB, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(CELLS)}")
