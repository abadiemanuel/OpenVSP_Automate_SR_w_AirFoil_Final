from abc import abstractmethod
from distutils.command.config import config
import os, sys, glob
import concurrent.futures
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
#from jupyterlab.commands import enable_extension #commented due to import error, but jupiterlabs is not being used
from pymoo.core.crossover import Crossover
from pymoo.core.sampling import Sampling
from pymoo.core.variable import Choice, Real, Integer
from pymoo.core.problem import Problem, ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.mixed import MixedVariableMating, MixedVariableSampling, MixedVariableDuplicateElimination
from pymoo.optimize import minimize
from pymoo.termination.robust import RobustTermination
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
from pymoo.visualization.scatter import Scatter
from pymoo.termination.ftol import MultiObjectiveSpaceTermination
from pymoo.indicators.hv import Hypervolume, HV


from DT import decoded_pred
#from GA_2 import Designer
from Master_Controller_2 import *
from Sizing import *
from Analysis import *
import time
import subprocess
import json
import re
import signal

"""
This code uses the NSGA2 to run the framework
"""

# Parallelism settings
N_PARALLEL_WORKERS = min(os.cpu_count() or 3, 3)  # Balanced for 24-core system
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"Parallel workers: {N_PARALLEL_WORKERS} (CPUs detected: {os.cpu_count()})")

# Scan airfoils folder for available airfoil .dat files
AIRFOIL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "airfoils")
AIRFOIL_OPTIONS = sorted([os.path.basename(f) for f in glob.glob(os.path.join(AIRFOIL_DIR, "*.dat"))])
print(f"Available airfoils ({len(AIRFOIL_OPTIONS)}): {AIRFOIL_OPTIONS}")

Span=tuple(Wing_span)#Design Variable
power = tuple(Eng_pow)
print(Span)
print(power)
Fuse_length = 0.47*Wing_span #Fuselage length model
cg = 0.33*np.average(Fuse_length) #from mohammed 32% to 49%
Fuse_b_avg = float(np.average(Wing_span))
# Compute required diameter from payload + representative wingspan (use average wingspan)
fus_req = compute_fuselage_from_payload(l_p=float(inputs.get('payload_l', 1.0)),
                                       w_p=float(inputs.get('payload_w', 1.0)),
                                       h_p=float(inputs.get('payload_h', 1.0)),
                                       b=Fuse_b_avg)
D_req = fus_req['D_req']
D_max = fus_req['D_ceiling']

# Set fuselage station bounds relative to required diameter
Fuselage_Width_0 = (0.333 * D_req, 0.5 * D_req)
Fuselage_Height_0 = (0.333 * D_req, 0.5 * D_req)
Fuselage_Width_1 = (D_req, D_req)
Fuselage_Height_1 = (D_req, D_req)
Fuselage_Width_2 = (D_req, D_req)
Fuselage_Height_2 = (D_req, D_req)
Fuselage_Width_3 = (D_req, D_req)
Fuselage_Height_3 = (D_req, D_req)
Fuselage_Width_4 = (0.333 * D_req, 0.8 * D_req)
Fuselage_Height_4 = (0.333 * D_req, 0.8 * D_req)
mixed_vars = {
    "Wing_Span": Real(bounds = (Span)), "Power": Real(bounds = (power)),"Taper": Real(bounds = (0.3,1)),"Sweep": Real(bounds = (0, 20)),"Vol_Hor": Real(bounds = (0.7,1.1)),"Vol_Vert": Real(bounds = (0.02, 0.1)),
    "Fuselage_Length": Real(bounds=(Fuse_length)),"Fuselage_Width_0": Real(bounds=(Fuselage_Width_0)),"Fuselage_Height_0": Real(bounds=(Fuselage_Height_0)),"Fuselage_Width_1": Real(bounds=(Fuselage_Width_1)),"Fuselage_Height_1": Real(bounds=(Fuselage_Height_1)),
    "Fuselage_Width_2": Real(bounds=(Fuselage_Width_2)),"Fuselage_Height_2": Real(bounds=(Fuselage_Height_2)),"Fuselage_Height_3": Real(bounds=(Fuselage_Height_3)),"Fuselage_Width_3": Real(bounds=(Fuselage_Width_3)),"Fuselage_Height_4": Real(bounds=(Fuselage_Height_4)),
    "Fuselage_Width_4": Real(bounds=(Fuselage_Width_4)),"toptan_0": Real(bounds=(40,120)),"toptan_1": Real(bounds=(40,120)),"toptan_2": Real(bounds=(40,120)),"toptan_3": Real(bounds=(40,120)),"toptan_4": Real(bounds=(40,120)),
    "bottan_0": Real(bounds=(40,120)),"bottan_1": Real(bounds=(40,120)),"bottan_2": Real(bounds=(40,120)),"bottan_3": Real(bounds=(40,120)),"bottan_4": Real(bounds=(40,120)),"topstr_0": Real(bounds=(0.5, 1.83)),"topstr_1": Real(bounds=(0.5, 1.83)),
    "topstr_2": Real(bounds=(0.5, 1.83)),"topstr_3": Real(bounds=(0.5, 1.83)),"topstr_4": Real(bounds=(0.5, 1.83)),"botstr_0": Real(bounds=(0.5, 1.83)),
    "botstr_1": Real(bounds=(0.5, 1.83)),"botstr_2": Real(bounds=(0.5, 1.83)),"botstr_3": Real(bounds=(0.5, 1.83)),"botstr_4": Real(bounds=(0.5, 1.83)),

    "Fuselage_NoseCap":Choice(options=["N_Round", "N_Sharp", "N_Edge"]), "Fuselage_TailCap":Choice(options=["T_Round", "T_Sharp", "T_Edge"]),
    "Wing_Type":Choice(options=["SLTT", "TLTT", "TLST", "SLST"]),
    "Wing_Position":Choice(options=["Low", "Mid", "High"]),
    "Tail_Type":Choice(options=["Conventional", "T-Tail", "Cruciform", "Dual-Tail", "V-Tail", "Inverted_V-Tail", "Y-Tail",
             "Inverted_Y-Tail"]),
    "Wing_Airfoil":Choice(options=AIRFOIL_OPTIONS),
    "HTail_Airfoil":Choice(options=AIRFOIL_OPTIONS),
    "VTail_Airfoil":Choice(options=AIRFOIL_OPTIONS),
}
#print(pd.DataFrame(list(mixed_vars)))

data = {
    "Cost":{ "Conventional":5, "T-Tail":5, "Cruciform":5, "Dual-Tail":5, "V-Tail":5,
            "Inverted_V-Tail":5, "Y-Tail":5, "Inverted_Y-Tail":5, "SLTT":5,
             "TLTT":5, "TLST":5, "SLST":5, "Low":5, "Mid":5, "High":5,}
}

#Where the ML makes the predictions
y_pred = decoded_pred
keys_to_access = y_pred #substitute this with Y pred
for key in keys_to_access:
  if key in data["Cost"]:
    data['Cost'][key] = 10

class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout



class Genetic(Problem):
    def __init__(self, **kwargs):
        super().__init__(vars = mixed_vars, n_obj=3, n_ieq_constr=3
                         ,**kwargs)
        self.last_temp_df = None
        self.last_objectives = None
        self.current_generation = 0
        self.candidate_counter = 0
        self.total_candidates_per_gen = []
        self.evaluation_records = []

    @staticmethod
    def _run_worker(i, vsp_file_abs, engine_power, cg_val, wing_area_pf):
        """Launch a VSPAero worker subprocess, retrying one native crash."""
        first_result = Genetic._run_worker_once(i, vsp_file_abs, engine_power, cg_val, wing_area_pf)
        if first_result.get("success"):
            return first_result

        error = first_result.get("error", "")
        retryable = (
            "Worker crashed" in error or
            "Worker produced no output" in error or
            "No worker result marker" in error
        )
        if not retryable:
            return first_result

        print(f"    Design {i}: worker failed once; retrying in a fresh process...")
        second_result = Genetic._run_worker_once(i, vsp_file_abs, engine_power, cg_val, wing_area_pf)
        if second_result.get("success"):
            return second_result

        second_error = second_result.get("error", "unknown")
        return {
            "success": False,
            "error": f"{error}; retry also failed: {second_error}",
        }

    @staticmethod
    def _run_worker_once(i, vsp_file_abs, engine_power, cg_val, wing_area_pf):
        """Launch a single VSPAero worker subprocess. Called from thread pool."""
        worker_cmd = [
            sys.executable, "vsp_worker.py",
            vsp_file_abs, str(engine_power), str(cg_val), str(wing_area_pf)
        ]
        proc = subprocess.Popen(
            worker_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_DIR,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=600)  # 10 min
        except subprocess.TimeoutExpired:
            # Kill entire process tree on Windows
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=30
            )
            proc.kill()
            proc.wait(timeout=10)
            return {"success": False, "error": "TimeoutExpired: Worker timed out (>600s)"}

        if proc.returncode != 0:
            stderr_msg = stderr_data[:300] if stderr_data else "no stderr"
            return {"success": False, "error": f"Worker crashed (exit code {proc.returncode}): {stderr_msg}"}

        stdout = stdout_data.strip() if stdout_data else ""
        if not stdout:
            return {"success": False, "error": "Worker produced no output (likely native crash)"}

        marker_match = re.search(r'>>>VSP_WORKER_RESULT>>>(.*?)<<<VSP_WORKER_RESULT<<<', stdout, re.DOTALL)
        if marker_match is None:
            return {"success": False, "error": f"No worker result marker in output. Last 300 chars: {stdout[-300:]}"}

        json_line = marker_match.group(1).strip()
        return json.loads(json_line)

    @abstractmethod
    def _evaluate(self, x, out, *args, **kwargs ):
        temp_df = pd.DataFrame(list(x), columns= list(mixed_vars.keys()))
        self.last_temp_df = temp_df
        
        # Track candidates per generation (reset counter on new batch)
        if self.candidate_counter == 0:
            self.current_generation += 1
            print(f"\n{'='*60}")
            print(f"Generation {self.current_generation}")
            print(f"{'='*60}")
        # Pull taper and sweep out for configs
        mask_taper = temp_df["Taper"]>0.9
        temp_df.loc[mask_taper, "Wing_Type"] = "SLST"

        mask_sltt = (~mask_taper) & (temp_df["Sweep"]<=0.5)
        temp_df.loc[mask_sltt, "Wing_Type"] = "SLTT"

        mask_tltt = (~mask_taper) & (temp_df["Sweep"]>0.5)
        temp_df.loc[mask_tltt, "Wing_Type"] = "TLTT"

        n_candidates = temp_df.shape[0]

        # Fast fuselage feasibility pre-check (hard-reject infeasible candidates)
        # Uses compute_fuselage_from_payload from Sizing.py. If payload dims are not
        # provided as columns, fall back to a cubic bounding box derived from global inputs.
        reject_indices = set()
        for i in range(n_candidates):
            row = temp_df.iloc[i]
            b_val = float(row.get('Wing_Span', 0.0))
            # Try to read explicit payload dims if provided
            l_p = row.get('Payload_L', None)
            w_p = row.get('Payload_W', None)
            h_p = row.get('Payload_H', None)
            if l_p is None or w_p is None or h_p is None:
                # fallback: use explicit payload dims from Sizing.inputs if available
                l_p = l_p or float(inputs.get('payload_l', 1.0))
                w_p = w_p or float(inputs.get('payload_w', 1.0))
                h_p = h_p or float(inputs.get('payload_h', 1.0))

            fus = compute_fuselage_from_payload(l_p=float(l_p), w_p=float(w_p), h_p=float(h_p), b=float(b_val))
            if not fus['fit_xsec'] or not fus['fit_len']:
                reject_indices.add(i)

        # ── Phase 1: Sequential geometry creation ──────────────────────
        # OpenVSP API uses global state so geometry must be built one at a time.
        # Each candidate gets a unique temp file (temp_design_{i}.vsp3).
        vsp_jobs = {}       # i -> (vsp_file_abs, engine_power, design_row)
        geometry_errors = set()  # indices that failed geometry creation

        phase1_start = time.time()
        print(f"  Phase 1 (Gen {self.current_generation}): Building {n_candidates} geometries sequentially...")
        for i in range(n_candidates):
            self.candidate_counter += 1
            # Skip geometry creation for candidates pre-rejected by fuselage feasibility
            if i in reject_indices:
                print(f"    Design {i+1}/{n_candidates} SKIPPED: fuselage packaging infeasible (hard reject)")
                geometry_errors.add(i)
                continue
            try:
                # Pass full DataFrame so iloc[i] resolves correctly inside create_aircraft
                Designer = Master_Designer(temp_df)
                vsp_file = Designer.create_aircraft(index=i, final=False)

                if not os.path.exists(vsp_file):
                    raise FileNotFoundError(f"VSP file was not created: {vsp_file}")

                vsp_file_abs = os.path.abspath(vsp_file)
                design_row = temp_df.iloc[i:i+1]
                engine_power = design_row["Power"].iloc[0]
                # Compute wing planform area for this candidate (S = b^2 / AR)
                wing_span_val = float(design_row["Wing_Span"].iloc[0])
                try:
                    wing_area_pf = (wing_span_val ** 2) / AR
                except Exception:
                    wing_area_pf = float(design_row["Wing_Span"].iloc[0])
                vsp_jobs[i] = (vsp_file_abs, engine_power, design_row, wing_area_pf)
            except Exception as e:
                print(f"    Geometry {i+1}/{n_candidates} FAILED: {type(e).__name__}: {str(e)[:150]}")
                geometry_errors.add(i)
        phase1_time = time.time() - phase1_start
        print(f"  Phase 1 done: {len(vsp_jobs)} geometries in {phase1_time:.1f}s "
              f"({len(geometry_errors)} failed)")

        # ── Phase 2: Parallel VSPAero evaluation ──────────────────────
        phase2_start = time.time()
        print(f"  Phase 2 (Gen {self.current_generation}): Evaluating {len(vsp_jobs)} candidates with "
              f"{N_PARALLEL_WORKERS} parallel workers...")
        worker_results = {}  # i -> result dict

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=N_PARALLEL_WORKERS) as executor:
            futures = {}
            for i, (vsp_file_abs, engine_power, _, wing_area_pf) in vsp_jobs.items():
                future = executor.submit(
                    self._run_worker, i, vsp_file_abs, engine_power, cg, wing_area_pf)
                futures[future] = i

            for future in concurrent.futures.as_completed(futures):
                i = futures[future]
                try:
                    worker_results[i] = future.result()
                except Exception as e:
                    worker_results[i] = {
                        "success": False,
                        "error": f"{type(e).__name__}: {str(e)}"
                    }

        phase2_time = time.time() - phase2_start
        succeeded = sum(1 for r in worker_results.values() if r.get("success"))
        print(f"  Phase 2 done: {succeeded}/{len(vsp_jobs)} succeeded in {phase2_time:.1f}s")

        # ── Phase 3: Collect results ──────────────────────────────────
        F, G = [], []
        for i in range(n_candidates):
            design_row = temp_df.iloc[i]
            base_row = design_row.to_dict()
            base_row["Generation"] = self.current_generation

            # Geometry creation failed
            if i in geometry_errors:
                F.append([1e6, -1.0, -100.0])
                G.append([1e6, 1e6, 1e6])
                base_row.update({
                    "Area": 1e6,
                    "L2D": -1.0,
                    "L/D_3": -1.0,
                    "Config": -100.0,
                    "CMy": np.nan,
                    "cd0_total": np.nan,
                    "CD_vsp": np.nan,
                    "CD_hyb": np.nan,
                    "CLtot": np.nan,
                    "L/D_2": np.nan,
                    "CDi": np.nan,
                    "CDi_visc": np.nan,
                    "CL_req": np.nan,
                    "AoA_at_CL": np.nan,
                })
                self.evaluation_records.append(base_row)
                continue

            result = worker_results.get(i)
            if result is None or not result.get("success", False):
                error_msg = result.get("error", "unknown") if result else "no result"
                print(f"    Design {i} failed: {error_msg[:150]}")
                F.append([1e6, -1.0, -100.0])
                G.append([1e6, 1e6, 1e6]) 
                base_row.update({
                    "Area": 1e6,
                    "L2D": -1.0,
                    "L/D_3": -1.0,
                    "Config": -100.0,
                    "CMy": np.nan,
                    "cd0_total": np.nan,
                    "CD_vsp": np.nan,
                    "CD_hyb": np.nan,
                    "CLtot": np.nan,
                    "L/D_2": np.nan,
                    "CDi": np.nan,
                    "CDi_visc": np.nan,
                    "CL_req": np.nan,
                    "AoA_at_CL": np.nan,
                })
                self.evaluation_records.append(base_row)
                continue

            try:
                design_row = vsp_jobs[i][2]
                f_1 = float(result["cost"])
                f_2 = float(sum(result["area"]))
                f_3 = float(-result["L/D_3"])  # Negate for minimization, using parasitic-drag corrected L/D_3 at CL_req
                constraint_1 = float(result["CMy"])

                f_4 = -1*(
                    data["Cost"].get(design_row["Wing_Type"].iloc[0],0) +
                    data["Cost"].get(design_row["Wing_Position"].iloc[0],0) +
                    data["Cost"].get(design_row["Tail_Type"].iloc[0],0)
                )
                constraint_2 = 1+f_3
                constraint_3 = -f_3-49
                f_4 = float(f_4)
                F.append([f_2,f_3,f_4])
                G.append([constraint_1, constraint_2, constraint_3])
                print(f"    Design {i}: cost={f_1:.2f}, area={f_2:.2f}, L/D_3={-f_3:.2f}, config_score={f_4:.2f}")

                base_row.update({
                    "Area": f_2,
                    "L2D": float(-result["L2D"]),
                    "L/D_3": -f_3,
                    "Config": f_4,
                    "CMy": constraint_1,
                    "cd0_total": float(result["cd0_total"]),
                    "CD_vsp": float(result["CD_vsp"]),
                    "CD_hyb": float(result["CD_hyb"]),
                    "CLtot": float(result["CLtot"]),
                    "L/D_2": float(result["L/D_2"]),
                    "CDi": float(result["CDi"]),
                    "CDi_visc": float(result["CDi_visc"]),
                    "CL_req": float(result["CL_req"]),
                    "AoA_at_CL": float(result["AoA_at_CL"]),
                })
                self.evaluation_records.append(base_row)
            except Exception as e:
                print(f"    Design {i} result parsing failed: {type(e).__name__}: {str(e)[:150]}")
                F.append([1e6, -1.0, -100.0])
                G.append([1e6, 1e6, 1e6])
                base_row.update({
                    "Area": 1e6,
                    "L2D": -1.0,
                    "L/D_3": -1.0,
                    "Config": -100.0,
                    "CMy": np.nan,
                    "cd0_total": np.nan,
                    "CD_vsp": np.nan,
                    "CD_hyb": np.nan,
                    "CLtot": np.nan,
                    "L/D_2": np.nan,
                    "CDi": np.nan,
                    "CDi_visc": np.nan,
                    "CL_req": np.nan,
                    "AoA_at_CL": np.nan,
                })
                self.evaluation_records.append(base_row)

        out["F"] = np.array(F)
        out["G"] = np.array(G)
        self.last_objectives = out["F"]
        
        # Store number of candidates evaluated in this generation
        self.total_candidates_per_gen.append(self.candidate_counter)
        # Reset counter for next generation
        self.candidate_counter = 0





#solving the problem
problem = Genetic()

algorithm = NSGA2(
    pop_size=10,
    sampling=MixedVariableSampling(),
    mating=MixedVariableMating(eliminate_duplicates= MixedVariableDuplicateElimination()),
    eliminate_duplicates=False
)

n_gen = 1

res = minimize(
    problem,
    algorithm,
    ('n_gen', n_gen),
    seed = 35,#42,
    save_history = True,
    verbose = False  # Changed to True to see progress
)
start = time.time()

print(f"Starting optimization: {algorithm.pop_size} individuals x {n_gen} generations = {algorithm.pop_size * n_gen} evaluations")
print(f"Estimated time: many hours (depending on VSPAero performance)")
print("="*60)

end = time.time()

# Print optimization summary
print(f"\n{'='*60}")
print(f"OPTIMIZATION SUMMARY")
print(f"{'='*60}")
print(f"Total generations run: {problem.current_generation}")
print(f"Candidates per generation: {problem.total_candidates_per_gen[0] if problem.total_candidates_per_gen else 'N/A'}")
print(f"Total candidates evaluated: {sum(problem.total_candidates_per_gen)}")
print(f"Total time elapsed: {end - start:.2f} seconds")
print(f"{'='*60}\n")

# Column names for design variables (from mixed_vars)
var_names = list(mixed_vars.keys())

#Plotting results
gen_area_min, gen_l2d_min, gen_config_min = [], [], []
gen_area_avg, gen_l2d_avg, gen_config_avg = [], [], []
gen_area_max, gen_l2d_max, gen_config_max = [], [], []

F_all = np.vstack([gen.pop.get("F") for gen in res.history])
F_min = F_all.min(axis=0)
F_max = F_all.max(axis=0)

def normalize(F):
    denom = F_max - F_min
    denom[denom == 0] = 1.0  # Avoid divide-by-zero for constant objectives
    return (F - F_min) / denom
hv = HV(ref_point=np.array([1,1,1]))
gen_hv = []
for gen in res.history:
    F = gen.pop.get("F")
    gen_area_min.append(np.min(F[:, 0]))
    gen_l2d_min.append(-np.min(F[:, 1]))
    gen_config_min.append(-np.min(F[:, 2]))
    gen_area_avg.append(np.mean(F[:, 0]))
    gen_l2d_avg.append(-np.mean(F[:, 1]))
    gen_config_avg.append(-np.mean(F[:, 2]))
    gen_area_max.append(np.max(F[:, 0]))
    gen_l2d_max.append(-np.max(F[:, 1]))
    gen_config_max.append(-np.max(F[:, 2]))
    F_norm = normalize(F)
    volume = hv.do(F_norm)
    gen_hv.append(volume)
gen_area_avg_df = pd.DataFrame(gen_area_avg, columns=["Avg_Area"])
gen_l2d_avg_df = pd.DataFrame(gen_l2d_avg,columns=["Avg_L2D"])
gen_config_avg_df = pd.DataFrame(gen_config_avg, columns=["Avg_Config"])
convergence_df_avg = pd.concat([gen_area_avg_df,gen_l2d_avg_df,gen_config_avg_df],axis=1)
convergence_df_avg.to_csv("Convergence_avg.csv",index=False)

gen_area_min_df = pd.DataFrame(gen_area_min, columns=["min_Area"])
gen_l2d_min_df = pd.DataFrame(gen_l2d_min,columns=["min_L2D"])
gen_config_min_df = pd.DataFrame(gen_config_min, columns=["min_Config"])
convergence_df_min = pd.concat([gen_area_min_df,gen_l2d_min_df,gen_config_min_df],axis=1)
convergence_df_min.to_csv("Convergence_min.csv",index=False)

gen_area_max_df = pd.DataFrame(gen_area_max, columns=["max_Area"])
gen_l2d_max_df = pd.DataFrame(gen_l2d_max,columns=["max_L2D"])
gen_config_max_df = pd.DataFrame(gen_config_max, columns=["max_Config"])
convergence_df_max = pd.concat([gen_area_max_df,gen_l2d_max_df,gen_config_max_df],axis=1)
convergence_df_max.to_csv("Convergence_max.csv",index=False)


HV_df = pd.DataFrame(gen_hv)
HV_df.to_csv("HV_normalised.csv",index=False)

# Saving ALL generation history with named columns
all_gens_df = pd.DataFrame(problem.evaluation_records)
all_gens_df.to_csv("all_generations.csv", index=False)
# Also keep last10_gens.csv for backward compatibility
last10_df = all_gens_df[all_gens_df["Generation"] <= 2]
last10_df.to_csv("last10_gens.csv", index=False)


# Saving results
# Check if optimization produced valid results
if res.X is not None and res.F is not None:
    results_df = pd.DataFrame(list(res.X), columns=var_names)
    results_df['Area'] = res.F[:,0]
    results_df['L/D_3'] = -res.F[:,1]
    results_df['L2D'] = 0  #-res.F[:,1]
    results_df['Config'] = -res.F[:,2]
    pd.set_option('display.max_rows', 20)

    #Generate final aircrafts
    Designer_auto = Master_Designer(results_df)
    Designer_auto.process_population()
    results_df.to_csv("final_population.csv", index = False)
else:
    print("WARNING: Optimization did not produce valid results (res.X or res.F is None)")
    print("This usually means no feasible solutions were found.")
    results_df = pd.DataFrame()  # Empty dataframe

objective_names = ["Area", "L/D_3", "Config"]
if problem.last_objectives is not None and problem.last_temp_df is not None:
    objective_df = pd.DataFrame(problem.last_objectives, columns = objective_names)
    temporary_df = pd.concat([problem.last_temp_df,objective_df], axis = 1)
    temporary_df.to_csv("temporary_population.csv", index = False)
else:
    print("WARNING: No temporary population data available")


print(f"time: {end - start}")

# ── Run post-generation analysis & visualization ──────────────────────────────
print("\n" + "="*60)
print("Running post-generation analysis (Aircraft_Design_w_Airfoils)...")
print("="*60)
try:
    post_gen_script = os.path.join(PROJECT_DIR, "Aircraft_Design_w_Airfoils.py")
    result = subprocess.run(
        [sys.executable, post_gen_script],
        cwd=PROJECT_DIR,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"Post-generation analysis exited with code {result.returncode}")
        print("You can run it manually:  python Aircraft_Design_w_Airfoils.py")
except Exception as e:
    print(f"Post-generation analysis encountered an error: {type(e).__name__}: {e}")
    print("You can run it manually:  python Aircraft_Design_w_Airfoils.py")
