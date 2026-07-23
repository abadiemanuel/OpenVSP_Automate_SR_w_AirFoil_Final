import openvsp as vsp
import os
from Sizing import *
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
        
        # Verify path exists
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"VSP file not found: {self.path}")

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
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaStart", [-1.0])
        vsp.SetDoubleAnalysisInput(analysis_name, "AlphaEnd", [10.0])
        vsp.SetIntAnalysisInput(analysis_name, "AlphaNpts", [5])  # Number of alpha points
        vsp.SetDoubleAnalysisInput(analysis_name, "ReCref", [5.8e6])  # Reynolds number
        vsp.SetIntAnalysisInput(analysis_name, "NumWakeNodes", [32])
        vsp.SetIntAnalysisInput(analysis_name, "WakeNumIter", [5])
        vsp.SetDoubleAnalysisInput(analysis_name, "Xcg", [self.xcg])
        vsp.SetIntAnalysisInput(analysis_name, "UnsteadyType", [vsp.STABILITY_DEFAULT])

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

        #Process report
        print("Looking for VSPAERO_History results...")
        history_res = vsp.FindLatestResultsID("VSPAERO_History")
        print(f"History result ID: {history_res}")
        
        # Check if history results exist
        if not history_res or history_res == "":
            print("Warning: Could not find VSPAERO_History results")
            # Try to list all available results
            print("Attempting to find available result types...")
            vsp.ClearVSPModel()
            raise RuntimeError("VSPAERO_History results not found")
            
        print("Extracting aerodynamic data...")
        CLtot = vsp.GetDoubleResults(history_res, "CLtot")
        CDtot = vsp.GetDoubleResults(history_res, "CDtot")
        L2D = vsp.GetDoubleResults(history_res, "L/D")
        E = vsp.GetDoubleResults(history_res, "E")
        # CMx/CMy/CMz may not be available in VLM mode without stability analysis
        CMx = vsp.GetDoubleResults(history_res, "CMx") or [0.0]
        CMy = vsp.GetDoubleResults(history_res, "CMy") or [0.0]
        CMz = vsp.GetDoubleResults(history_res, "CMz") or [0.0]
        
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
        
        # Calculate CMy change (for stability derivative)
        CMy_delta = 0.0
        if len(CMy) >= 2:
            CMy_delta = CMy[-1] - CMy[-2]
        
        final_L2D = L2D[-1]
        if final_L2D == 0.0 and len(L2D) > 1:
            # Last alpha point gave L/D=0 (possible zero-lift angle), use best non-zero
            nonzero = [v for v in L2D if v != 0.0]
            if nonzero:
                final_L2D = max(nonzero)
                print(f"Note: Last L/D was 0, using best non-zero L/D = {final_L2D:.2f}")
        
        print(f"VSPAero analysis successful: L/D = {final_L2D:.2f}")
        vsp.ClearVSPModel()
        return final_L2D, CDtot[-1], CMy_delta, CLtot[-1], E[-1]


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
        L2D,Cdtotal,CMy,Cl,E = self.VSPAero()
        if L2D >50: # Based on highest achieved by ETA gliders
          L2D = 50
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
        print(f"Objectives: cost={cost:.2f}, area={sum(area):.2f}, L/D={L2D:.2f}, CMy={CMy:.4f}")
        print("=== Objective computation complete ===\n")
        return cost, area, -L2D, CMy

