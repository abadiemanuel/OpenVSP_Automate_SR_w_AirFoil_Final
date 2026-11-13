import openvsp as vsp
import os
from Sizing import *
import pandas as pd
"""
This section interacts with VSPAero in OpenVSP
"""

# Set VSPAero path at module level
VSPAERO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenVSP-3.47.0-win64")
if os.path.exists(VSPAERO_PATH):
    vsp.SetVSPAEROPath(VSPAERO_PATH)
    print(f"VSPAero path set to: {VSPAERO_PATH}")
else:
    print(f"WARNING: VSPAero path not found: {VSPAERO_PATH}")

MU_AIR = 1.789e-5  # Pa*s, dynamic viscosity of air (sea-level standard; varies <1% up to 120 m)


def main_wing_id():
    """Largest wing geom in the loaded model (the main wing, not the tails)."""
    wings = [g for g in vsp.FindGeoms() if vsp.GetGeomTypeName(g) == "Wing"]
    if not wings:
        raise RuntimeError("No wing geometry found for the reference area")
    return max(wings, key=lambda g: vsp.GetParmVal(g, "TotalArea", "WingGeom"))


class Aero:
    def __init__(self,path = "", Engine_Power=20,xcg=1):
        self.path = path
        self.Engine_Power = Engine_Power
        self.xcg = xcg
        # wing planform area (m^2) used to compute CL_cruise — can be set by caller
        self.wing_area_planform = None

        # Verify path exists
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"VSP file not found: {self.path}")

    # CL_cruise calculation moved to Sizing.compute_cl_cruise

    def ComputeArea(self):
        print(f"Computing area for: {self.path}")
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(self.path)
        vsp.Update()
        compGeom = "CompGeom"
        vsp.SetAnalysisInputDefaults(compGeom)
        vsp.SetIntAnalysisInput(compGeom, "Set", [1])

        #print("Checking Geometry for analysis...")
        #vsp.PrintAnalysisInputs(compGeom)
        compGeom_results = vsp.ExecAnalysis(compGeom)
        
        if not compGeom_results or compGeom_results == "":
            raise RuntimeError("CompGeom analysis failed")
            
        Swet = list(vsp.GetDoubleResults(compGeom_results, "Total_Wet_Area"))  # FInd Total Area
        
        if not Swet:
            raise RuntimeError("CompGeom returned no wetted area results")
        
        print(f"Wetted area computed: {sum(Swet):.2f} m²")
        #print(f"Swet {Swet}")
        return Swet
        
    def ComputeGeom(self):
        print(f"Computing geometry for VSPAero: {self.path}")
        # IMPORTANT: Start with a completely clean model.
        # Do NOT run CompGeom before VSPAEROComputeGeometry — CompGeom
        # modifies internal surface intersection data that corrupts the
        # panel mesh, producing non-manifold edges and causing vspaero
        # to reject it with "Mesh is not logically valid".
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(self.path)
        vsp.Update()
        
        # Validate geometry exists
        geom_ids = vsp.FindGeoms()
        if len(geom_ids) == 0:
            raise RuntimeError("No geometry found in model")
        
        print(f"Found {len(geom_ids)} geometry components")
        
        # Run VSPAEROComputeGeometry on the clean model
        compGeom = "VSPAEROComputeGeometry"
        vsp.SetAnalysisInputDefaults(compGeom)
        # IMPORTANT: Do NOT set GeomSet to SET_SHOWN — that forces everything
        # (including wings) into the thick/body mesh, eliminating Kutta edges.
        # Defaults: GeomSet=SET_NONE (no thick bodies), ThinGeomSet=SET_SHOWN
        # (all visible components as thin/lifting surfaces with Kutta edges).
        # For VLM analysis this is correct.  The fuselage contribution is small
        # compared to the wing, and this avoids the non-manifold mesh issues
        # that arise when thick and thin surfaces intersect.
        
        print("Executing VSPAEROComputeGeometry...")
        result = vsp.ExecAnalysis(compGeom)
        
        if not result or result == "":
            raise RuntimeError("VSPAEROComputeGeometry analysis failed")
        
        print("VSPAEROComputeGeometry completed successfully")


    def VSPAero(self):
        """
        L2D
        min= 2
        max = 20
        :return:
        """
        print(f"Starting VSPAero analysis for: {self.path}")
        
        analysis_name = "VSPAEROSweep"
        vsp.SetAnalysisInputDefaults(analysis_name)
        # Reference geometry and freestream conditions
        # Do NOT override GeomSet — the default matches what ComputeGeometry used.

        # Reference area, chord and span from the main wing (the default is a manual Sref = 100, cref = bref = 1)
        wing = main_wing_id()
        vsp.SetIntAnalysisInput(analysis_name, "RefFlag", [vsp.COMPONENT_REF])
        vsp.SetStringAnalysisInput(analysis_name, "WingID", [wing])
        # Cruise Reynolds number on the wing's mean geometric chord (S/b)
        c_ref = vsp.GetParmVal(wing, "TotalArea", "WingGeom") / vsp.GetParmVal(wing, "TotalSpan", "WingGeom")
        Re_cruise = float(rho_c) * float(inputs['cruise_speed']) * c_ref / MU_AIR
        print(f"Reference wing {wing}: c_ref = {c_ref:.4f} m, Re = {Re_cruise:.3e}")

        vsp.SetDoubleAnalysisInput(analysis_name, "MachStart", [cruise_mach])
        vsp.SetIntAnalysisInput(analysis_name, "MachNpts", [1])
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaStart", [-6.0])
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaEnd", [10.0])
        vsp.SetIntAnalysisInput(analysis_name, "AlphaNpts", [7])  # Number of alpha points
        vsp.SetDoubleAnalysisInput(analysis_name, "ReCref", [Re_cruise])  # Reynolds number at cruise
        vsp.SetIntAnalysisInput(analysis_name, "NumWakeNodes", [32])
        vsp.SetIntAnalysisInput(analysis_name, "WakeNumIter", [5])
        vsp.SetDoubleAnalysisInput(analysis_name, "Xcg", [self.xcg])
        vsp.SetIntAnalysisInput(analysis_name, "UnsteadyType", [vsp.STABILITY_OFF]) #Removed [vsp.STABILITY_DEFAULT] due to data handling issues. Steady analysis was not doind anything accurately

        print("VSPAero inputs configured")
        vsp.Update()
        
        print("Executing VSPAero analysis...")
        try:
            allResults=vsp.ExecAnalysis(analysis_name)
            #print(f"VSPAero execution completed. Result ID: {allResults}")
        except Exception as e:
            print(f"VSPAero execution error: {e}")
            vsp.ClearVSPModel()
            raise RuntimeError(f"VSPAero execution failed: {e}")

        # Check if analysis completed successfully
        if not allResults or allResults == "":
            print("Warning: VSPAero analysis failed or returned no results")
            print(f"Analysis path: {self.path}")
            vsp.ClearVSPModel()
            raise RuntimeError("VSPAero analysis did not complete successfully")

        # #Process report
        # print("Looking for VSPAERO_History results...")
        # history_res = vsp.FindLatestResultsID("VSPAERO_History")
        # print(f"History result ID: {history_res}")
        # # Check if history results exist
        # if not history_res or history_res == "":
        #     print("Warning: Could not find VSPAERO_History results")
        #     # Try to list all available results
        #     print("Attempting to find available result types...")
        #     vsp.ClearVSPModel()
        #     raise RuntimeError("VSPAERO_History results not found")

        #Process report
        print("Looking for VSPAERO_Polar results...")
        polar = vsp.FindLatestResultsID("VSPAERO_Polar")
        print(f"Polar result ID: {polar}")
        # Check if history results exist
        if not polar or polar == "":
            print("Warning: Could not find VSPAERO_Polar results")
            # Try to list all available results
            print("Attempting to find available result types...")
            vsp.ClearVSPModel()
            raise RuntimeError("VSPAERO_Polar results not found")
            
        print("Extracting aerodynamic data...")
        alphas = vsp.GetDoubleResults(polar, "Alpha")
        CLtot = vsp.GetDoubleResults(polar, "CLtot")
        CDtot = vsp.GetDoubleResults(polar, "CDtot")
        CDi = vsp.GetDoubleResults(polar, "CDi")
        Cdo = vsp.GetDoubleResults(polar, "CDo")
        L2D = vsp.GetDoubleResults(polar, "L_D")
        E = vsp.GetDoubleResults(polar, "E")
        # CMx/CMy/CMz may not be available in VLM mode without stability analysis
        CMx = vsp.GetDoubleResults(polar, "CMx") or [0.0]
        CMy = vsp.GetDoubleResults(polar, "CMy") or [0.0]
        CMz = vsp.GetDoubleResults(polar, "CMz") or [0.0]

        # results_polar = []
        # polar = vsp.FindLatestResultsID("VSPAERO_Polar")
        # alphas = np.array(vsp.GetDoubleResults(polar, "Alpha"))   # read, don't reconstruct
        # CL     = np.array(vsp.GetDoubleResults(polar, "CLtot"))
        # CDi    = np.array(vsp.GetDoubleResults(polar, "CDi"))
        # CDo    = np.array(vsp.GetDoubleResults(polar, "CDo"))
        # # assert len(alphas) == len(CL) == alpha_npts
        # results_polar = np.empty((len(alphas), 4))
        # results_polar[:,0] = alphas
        # results_polar[:,1] = CL
        # results_polar[:,2] = CDi
        # results_polar[:,3] = CDo
        # print(f' Polar results: {results_polar}', flush=True)


        # Check if we got valid results
        if not CLtot or not CDtot or not L2D or not E:
            print("Warning: Empty results from VSPAero")
            print(f"CLtot: {CLtot}, CDtot: {CDtot}, L2D: {L2D}, E: {E}")
            vsp.ClearVSPModel()
            raise RuntimeError("VSPAero returned empty results")
        
        # Validate that results are physically meaningful
        # (vspaero can sometimes return zeros when the solver partially fails)
        if all(v == 0.0 for v in L2D):
            print(f"Warning: All L/D values are zero — solver likely failed silently")
            print(f"CLtot: {CLtot}, CDtot: {CDtot}, L2D: {L2D}")
            vsp.ClearVSPModel()
            raise RuntimeError("VSPAero returned all-zero L/D (solver failure)")

        # Calculate Cdi_Visc for Removing NACA0012-based parasite drag, see Brandon Litherlands drag buildup for info
        Cdo_min = min(Cdo)
        CDi_visc = [cdo - Cdo_min for cdo in Cdo]  #cdo is just the loop/iteration variable inside the list
        assert all(x >= -1e-9 for x in CDi_visc), "residual went negative: check sweep/monotonicity"

        # Calculate CMy change (for stability derivative)
        CMy_delta = 0.0
        if len(CMy) >= 2:
            CMy_delta = CMy[-1] - CMy[-2]

        # Construct alpha array based on inputs used for the sweep so callers can
        # interpolate at arbitrary CL or alpha values.
        # alpha_start = -6.0
        # alpha_end = 10.0
        # alpha_npts = 7
        # try:
        #     import numpy as _np
        #     alphas = list(_np.linspace(alpha_start, alpha_end, alpha_npts))
        # except Exception:
        #     # Fallback to indices if numpy not available
        #     alphas = list(range(len(CLtot)))

        print(f"VSPAero analysis successful: {len(CLtot)} alpha points")
        vsp.ClearVSPModel()

        # Return full sweep arrays plus alpha list and CMy_delta for downstream interpolation
        return L2D, CDtot, CMy_delta, CLtot, E, Cdo, CDi, CDi_visc, alphas

    def ParasiticDrag(self):
        """
        Run OpenVSP's ParasiteDrag analysis and return Total_CD_Total.
        """
        print(f"Starting ParasiticDrag analysis for: {self.path}")

        analysis_name = "ParasiteDrag"
        vsp.VSPRenew()
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(self.path)
        vsp.Update()

        vsp.SetAnalysisInputDefaults(analysis_name)
        vsp.SetIntAnalysisInput(analysis_name, "LengthUnit", [2])
        vsp.SetIntAnalysisInput(analysis_name, "VelocityUnit", [1])
        vsp.SetIntAnalysisInput(analysis_name, "AltLengthUnit", [1])
        vsp.SetIntAnalysisInput(analysis_name, "GeomSet", [0])
        # Same reference as VSPAero (main wing), so cd0_total and CDi add on one area
        vsp.SetIntAnalysisInput(analysis_name, "RefFlag", [vsp.COMPONENT_REF])
        vsp.SetStringAnalysisInput(analysis_name, "WingID", [main_wing_id()])

        cruise_ceiling = float(inputs.get("cruise_ceiling", 0.0))
        cruise_speed = float(inputs.get("cruise_speed", 0.0))

        vsp.SetDoubleAnalysisInput(analysis_name, "Altitude", [cruise_ceiling])
        vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [cruise_speed])
        vsp.SetIntAnalysisInput(analysis_name, "RecomputeGeom", [1])

        print("Executing ParasiteDrag analysis...")
        try:
            result_id = vsp.ExecAnalysis(analysis_name)
        except Exception as e:
            vsp.ClearVSPModel()
            raise RuntimeError(f"ParasiteDrag execution failed: {e}")

        if not result_id or result_id == "":
            vsp.ClearVSPModel()
            raise RuntimeError("ParasiteDrag analysis did not complete successfully")

        result_obj = vsp.parse_results_object(result_id)
        total_cd_total = getattr(result_obj, "Total_CD_Total", None)
        if not total_cd_total:
            vsp.ClearVSPModel()
            raise RuntimeError("ParasiteDrag returned no Total_CD_Total results")

        cd0_total = total_cd_total[0]
        print(f"ParasiteDrag analysis successful: Total_CD_Total = {cd0_total:.6f}")
        vsp.ClearVSPModel()
        return cd0_total   #cd0_total includes the parasite drag of all components


        #print(f"Coeffiecient of lift:{CL[-1]}\n Total Drag:{CDtot[-1]}\n Lift_to_Drag:{L2D[-1]}\n CMy:{CMy[-1]}\n E:{E[-1]}")
    def cost(self):
        """
        min = 46$
        max = 13,919$
        :return:
        """
        cost = 0.1326 *self.Engine_Power - 3.3346
        return cost

    def compute_objective(self):
        """
        Run the aero pipeline and return a dict that ALWAYS has the same keys.
        Feasibility is reported in "status", never by raising:
            ok              CL_req reached inside the sweep; objectives valid
            CL_unreachable  CL_req > CL_max of the valid sweep  (graded in Pymoo)
            CL_below_sweep  CL_req < CL_min of the valid sweep  (graded in Pymoo)
            no_CL_req       CL_req could not be computed
            aero_invalid    sweep unusable (non-finite, CD <= 0, non-monotonic CL, ...)
        Exceptions raised by VSPAero()/ParasiticDrag() still propagate -> worker crash.
        """
        import numpy as np
        nan = float("nan")
        print("\n=== Starting objective computation ===")

        area = self.ComputeArea()
        self.ComputeGeom()
        L2D_arr, CDtot_arr, CMy_delta, CLtot_arr, E_arr, CDo_arr, CDi_arr, CDi_visc_arr, alphas = self.VSPAero()
        cd0_total = float(self.ParasiticDrag())

        out = {
            "status": "ok",
            "cost": float(self.cost()),
            "area": [float(v) for v in area],
            "cd0_total": cd0_total,
            "CMy": float(CMy_delta),
            "SM": nan,
            "CL_req": nan, "CL_min": nan, "CL_max": nan, "AoA_at_CL": nan,
            "CLtot": nan, "CDi": nan, "CDi_visc": nan,
            "CD_vsp": nan, "CD_hyb": nan, "L/D_2": nan, "L/D_3": nan,
            "n_bad_alpha": 0,
        }

        # ── 1. Required cruise CL ────────────────────────────────────────────
        try:
            from Sizing import compute_cl_cruise
            if self.wing_area_planform is not None:
                CL_req = compute_cl_cruise(self.wing_area_planform)
            else:
                print("WARNING: wing_area_planform not set; CL_req uses Sizing default area")
                CL_req = compute_cl_cruise()
            CL_req = float(CL_req)
        except Exception as e:
            print(f"WARNING: compute_cl_cruise failed: {type(e).__name__}: {e}")
            CL_req = nan

        if not np.isfinite(CL_req) or CL_req <= 0:
            out["status"] = "no_CL_req"
            return out
        out["CL_req"] = CL_req

        # ── 2. Keep only physically valid sweep points ──────────────────────
        a   = np.asarray(alphas,    float)
        CL  = np.asarray(CLtot_arr, float)
        CD  = np.asarray(CDtot_arr, float)
        CDi = np.asarray(CDi_arr,   float)
        CDo = np.asarray(CDo_arr,   float)

        if not (len(a) == len(CL) == len(CD) == len(CDi) == len(CDo)) or len(a) < 2:
            print(f"aero_invalid: array lengths a={len(a)} CL={len(CL)} CD={len(CD)}")
            out["status"] = "aero_invalid"
            return out

        valid = (np.isfinite(a) & np.isfinite(CL) & np.isfinite(CD) & np.isfinite(CDi) & np.isfinite(CDo)
                 & (np.abs(CL) < 3.0) & (CD > 0.0) & (CD < 1.0))
        out["n_bad_alpha"] = int((~valid).sum())

        order = np.argsort(a)                       # sort by ALPHA, never by CL
        a, CL, CD, CDi, CDo, valid = a[order], CL[order], CD[order], CDi[order], CDo[order], valid[order]
        a_v, CL_v, CD_v, CDi_v, CDo_v = a[valid], CL[valid], CD[valid], CDi[valid], CDo[valid]

        if len(a_v) < 4 or np.any(np.diff(CL_v) <= 0):
            print(f"aero_invalid: {len(a_v)} valid points, CL monotonic={bool(np.all(np.diff(CL_v) > 0))}")
            out["status"] = "aero_invalid"
            return out

        CL_min, CL_max = float(CL_v[0]), float(CL_v[-1])
        out["CL_min"], out["CL_max"] = CL_min, CL_max

        # ── 3. CL_req feasibility (graded in Pymoo) ─────────────────────────
        if CL_req > CL_max:
            out["status"] = "CL_unreachable"
            print(f"CL_unreachable: CL_req={CL_req:.4f} > CL_max={CL_max:.4f} at alpha={a_v[-1]:.1f} deg")
            return out
        if CL_req < CL_min:
            out["status"] = "CL_below_sweep"
            print(f"CL_below_sweep: CL_req={CL_req:.4f} < CL_min={CL_min:.4f} at alpha={a_v[0]:.1f} deg")
            return out

        # ── 4. Cruise point and L/D_3 ───────────────────────────────────────
        AoA = float(np.interp(CL_req, CL_v, a_v))
        CDi_at = float(np.interp(AoA, a_v, CDi_v))
        CDo_visc = CDo_v - CDo_v.min()               # viscous drag rise over VALID points only
        CDi_visc_at = float(np.interp(AoA, a_v, CDo_visc))
        CD_vsp_at = float(np.interp(AoA, a_v, CD_v))
        CD_hyb = CDi_at + cd0_total + CDi_visc_at

        if not np.isfinite(CD_hyb) or CD_hyb <= 0:
            print(f"aero_invalid: CD_hyb={CD_hyb}")
            out["status"] = "aero_invalid"
            return out

        out.update({
            "AoA_at_CL": AoA,
            "CLtot": CL_req,
            "CDi": CDi_at,
            "CDi_visc": CDi_visc_at,
            "CD_vsp": CD_vsp_at,
            "CD_hyb": CD_hyb,
            "L/D_2": CL_req / CD_vsp_at if CD_vsp_at > 0 else nan,
            "L/D_3": CL_req / CD_hyb,
        })
        print(f"ok: CL_req={CL_req:.4f}, alpha={AoA:.2f} deg, L/D_3={out['L/D_3']:.2f}, "
              f"bad alpha pts={out['n_bad_alpha']}")
        print("=== Objective computation complete ===\n")
        return out