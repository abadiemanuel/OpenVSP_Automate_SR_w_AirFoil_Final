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

        vsp.SetDoubleAnalysisInput(analysis_name, "MachStart", [cruise_mach])
        vsp.SetIntAnalysisInput(analysis_name, "MachNpts", [1])
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaStart", [-6.0])
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaEnd", [10.0])
        vsp.SetIntAnalysisInput(analysis_name, "AlphaNpts", [7])  # Number of alpha points
        vsp.SetDoubleAnalysisInput(analysis_name, "ReCref", [5.8e6])  # Reynolds number
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
        CMx = vsp.GetDoubleResults(polar, "CMxtot") or [0.0]
        CMy = vsp.GetDoubleResults(polar, "CMytot") or [0.0]
        CMz = vsp.GetDoubleResults(polar, "CMztot") or [0.0]

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
        vsp.SetIntAnalysisInput(analysis_name, "RefFlag", [0])
        vsp.SetDoubleAnalysisInput(analysis_name, "Sref", [100.0])

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
        #we normalize by 208270 which is the assumed max cost of the power we can have 2000 hp
        #L2D might be divided by 100
        print("\n=== Starting objective computation ===")
        area = self.ComputeArea()
        self.ComputeGeom()
        # VSPAero now returns sweep arrays and alphas for interpolation
        L2D_arr, CDtot_arr, CMy, CLtot_arr, E_arr, CDo_arr, CDi_arr, CDi_visc_arr, alphas = self.VSPAero()
        cd0_total = self.ParasiticDrag()
        # Legacy final L2D value (use last point or best non-zero)
        try:
            final_L2D = L2D_arr[-1]
            if final_L2D == 0.0 and len(L2D_arr) > 1:
                nonzero = [v for v in L2D_arr if v != 0.0]
                if nonzero:
                    final_L2D = max(nonzero)
        except Exception:
            final_L2D = 0.0
        if final_L2D > 50:
            final_L2D = 50
        cost = self.cost()
        #ost_ratio = cost/208270
        #We normalize the area with wetted area of global hawk
        #rea_ratio = sum(area)/218.546
       #L2D_ratio = L2D/50
       #E_ratio = E/100
       #if cost_ratio > 1:
       #    cost_ratio = 1
       #elif area_ratio > 1:
       #  area_ratio = 1
        #total = -0.4*L2D_ratio -0*E_ratio + 0.2*cost_ratio + 0.3*area_ratio
        #return total, L2D,CMy, Cl, Cdtotal, cost,area
        print(f"Objectives: cost={cost:.2f}, area={sum(area):.2f}, L/D={final_L2D:.2f}, CMy={CMy:.4f}")
        print("=== Objective computation complete ===\n")
        # --- New: compute mission-representative L/D_3 at required CL (CL_req)
        try:
            from Sizing import compute_cl_cruise
            # Prefer candidate's wing planform area if available on the Aero instance
            if self.wing_area_planform is not None:
                CL_req = compute_cl_cruise(self.wing_area_planform)
            else:
                CL_req = compute_cl_cruise()
        except Exception:
            CL_req = None

        L_D_3 = 0.0
        try:
            import numpy as _np
            CL_arr = _np.array(CLtot_arr)
            alpha_arr = _np.array(alphas)
            # Sort by CL to ensure monotonic interpolation
            sort_idx = _np.argsort(CL_arr)
            CL_sorted = CL_arr[sort_idx]
            alpha_sorted = alpha_arr[sort_idx]
            CDi_sorted = _np.array(CDi_arr)[sort_idx]
            CDi_visc_sorted = _np.array(CDi_visc_arr)[sort_idx]
            CDo_sorted = _np.array(CDo_arr)[sort_idx]


            AoA_at_CL = CL_at_AoA = L_D_3 = float("nan")
            cl_violation = 0.0
            if CL_req is None:
                L_D_3 = 0.0
                status = "no_CL_req"; cl_violation = 1e3  #Added error handling messages
            else:
                CL_max = CL_sorted.max()
                CL_min = CL_sorted.min()
                if CL_req > CL_max:
                    # Candidate never reaches required CL -> infeasible
                    L_D_3 = 0.0
                    status = "CL_unreachable"; cl_violation = CL_req - CL_max
                elif CL_req < CL_min:
                     status = "CL_below_sweep"; cl_violation = CL_min - CL_req
                else:
                    status = "ok"
                    # Interpolate AoA where CL == CL_req
                    AoA_at_CL = float(_np.interp(CL_req, CL_sorted, alpha_sorted))
                    # Interpolate CL at AoA where CL == CL_req
                    CL_at_AoA = float(_np.interp(AoA_at_CL, alpha_sorted, CL_sorted))
                    # Interpolate induced/viscous/parasite contributions at that AoA
                    CDi_at = float(_np.interp(AoA_at_CL, alpha_sorted, CDi_sorted))
                    CDi_visc_at = float(_np.interp(AoA_at_CL, alpha_sorted, CDi_visc_sorted))
                    # Parasite Cdo at that AoA (from VSPAero CDo sweep)
                    CDo_at = float(_np.interp(AoA_at_CL, alpha_sorted, CDo_sorted))
                    # Hybrid drag uses CDi + parasitic (cd0_total) + viscous-induced
                    CD_hyb_at = CDi_at + float(cd0_total) + CDi_visc_at
                    if CD_hyb_at > 0:
                        L_D_3 = float(CL_at_AoA / CD_hyb_at)
                    else:
                        status = "CD_hyb_zero"; cl_violation = 1e3
                        L_D_3 = 0.0
        except Exception as e:
            print(f"Warning: failed to compute L/D_3: {e}")
            L_D_3 = 0.0

        # For backwards compatibility, return scalar CLtot as last-point value
        try:
            CLtot_scalar = float(CLtot_arr[-1])
        except Exception:
            CLtot_scalar = float(CL_req) if CL_req is not None else 0.0

        return cost, area, -final_L2D, CMy, CL_at_AoA, CDi_arr[-1], CDo_arr[-1], cd0_total, CDi_visc_arr[-1], L_D_3, CL_req, AoA_at_CL,

