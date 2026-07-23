"""
Utility functions for running VSP analysis with timeout protection
"""
import multiprocessing
import openvsp as vsp

def _run_vspaero_compute_geom(path, result_queue):
    """
    Worker function to run VSPAEROComputeGeometry in separate process
    """
    try:
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(path)
        vsp.Update()
        
        compGeom = "VSPAEROComputeGeometry"
        vsp.SetAnalysisInputDefaults(compGeom)
        vsp.SetIntAnalysisInput(compGeom, "GeomSet", [1])
        result = vsp.ExecAnalysis(compGeom)
        
        result_queue.put(("success", result))
    except Exception as e:
        result_queue.put(("error", str(e)))

def run_vspaero_compute_geom_with_timeout(path, timeout=30):
    """
    Run VSPAEROComputeGeometry with timeout protection
    Returns: (success: bool, result_or_error: str)
    """
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=_run_vspaero_compute_geom,
        args=(path, result_queue)
    )
    
    process.start()
    process.join(timeout=timeout)
    
    if process.is_alive():
        # Timeout occurred
        process.terminate()
        process.join()
        return False, f"VSPAEROComputeGeometry timeout after {timeout}s"
    
    if not result_queue.empty():
        status, data = result_queue.get()
        if status == "success":
            return True, data
        else:
            return False, data
    else:
        return False, "VSPAEROComputeGeometry returned no result"
