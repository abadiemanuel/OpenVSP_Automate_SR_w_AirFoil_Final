"""
VSP Worker - subprocess entry point for VSPAero analysis.

Called by Pymoo.py to isolate native OpenVSP/VSPAero crashes from the
main optimization process.

Usage:
    python vsp_worker.py <vsp_file> <engine_power> <cg>

Outputs JSON wrapped in markers so the parent can extract it even if
VSPAero prints stray text to stdout.
"""
import sys
import os
import json
import traceback
import shutil
import tempfile

# Ensure the project root is on sys.path so we can import Analysis
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <vsp_file> <engine_power> <cg>",
              file=sys.stderr)
        sys.exit(1)

    vsp_file = sys.argv[1]
    engine_power = float(sys.argv[2])
    cg = float(sys.argv[3])

    try:
        # Import here so any openvsp init happens inside the subprocess
        from Analysis import Aero

        worker_root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "output_vsp_files",
            "worker_tmp",
        )
        os.makedirs(worker_root, exist_ok=True)

        stem, ext = os.path.splitext(os.path.basename(vsp_file))
        work_dir = tempfile.mkdtemp(
            prefix=f"{stem}_{os.getpid()}_",
            dir=worker_root,
        )
        local_vsp_file = os.path.join(work_dir, f"{stem}{ext}")
        shutil.copy2(vsp_file, local_vsp_file)

        # VSPAero writes sidecar files next to the input model. Use a private
        # copy so parallel workers do not contend for the same files.
        os.chdir(work_dir)

        aero = Aero(path=local_vsp_file, Engine_Power=engine_power, xcg=cg)
        cost, area, neg_L2D, CMy, CLtot, CDi, CDo, cd0_total, CDi_visc= aero.compute_objective()
        CD_vsp = CDi + CDo
        CD_hyb = CDi + cd0_total + CDi_visc
        l_d_2 = CLtot / CD_hyb if CD_hyb else 0.0
        result = {
            "success": True,
            "cost": cost,
            "area": list(area),       # area is a list of component areas
            "L2D": -neg_L2D,           # compute_objective returns -L2D; undo negation
            "CMy": CMy,
            "cd0_total": cd0_total,    # total parasitic drag coefficient
            "CD_vsp": CD_vsp,           # VSPAero total drag coefficient
            "CD_hyb": CD_hyb,           # hybrid drag coefficient
            "CLtot": CLtot,               # total lift coefficient
            "L/D_2": l_d_2,                # L/D based on hybrid drag (CDi + cd0_total)
            "CDi": CDi,                     # induced drag coefficient
            "CDi_visc": CDi_visc,           # viscous induced drag coefficient
        }

    except Exception as e:
        result = {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }

    # Emit result between unique markers so the parent can find it
    # even if OpenVSP prints unexpected text to stdout.
    payload = json.dumps(result)
    print(f">>>VSP_WORKER_RESULT>>>{payload}<<<VSP_WORKER_RESULT<<<")


if __name__ == "__main__":
    main()
