from typing import final

import openvsp as vsp
import pandas as pd
import numpy as np
import math
import random
import os


#from GA_2 import top_n_df
from Trial_2 import Fuselage, Wing, Propulsion
from SubParts_config import Wing_Type_Config, Wing_Position_Config, Tail_Config
from Sizing import *

# Airfoil folder path
AIRFOIL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "airfoils")

def airfoil_path(name):
    """Convert airfoil filename (e.g. '1.sg6043rev.dat') to full file path."""
    if not name:
        return ""
    return os.path.join(AIRFOIL_DIR, name)


class Master_Designer:
    def __init__(self, population_df):
        self.population_df = population_df

    def process_population(self):
        row_count = self.population_df.shape[0]
        for i in range(row_count):
            self.create_aircraft(i,final = True)

    def create_aircraft(self, index, final = False):
        data = self.population_df.iloc[index]

        #Fuselage Geometry design
        fuse =  Fuselage(length=data['Fuselage_Length'], Nose_cap=data['Fuselage_NoseCap'], Tail_cap=data['Fuselage_TailCap'],
                    fuselage_Width_0=data['Fuselage_Width_0'],fuselage_Height_0=data['Fuselage_Height_0'],
                    fuselage_Width_1=data['Fuselage_Width_1'],fuselage_Height_1=data['Fuselage_Height_1'],
                    fuselage_Width_2=data['Fuselage_Width_2'],fuselage_Height_2=data['Fuselage_Height_2'],
                    fuselage_Width_3=data['Fuselage_Width_3'],fuselage_Height_3=data['Fuselage_Height_3'],
                    fuselage_Width_4=data['Fuselage_Width_4'],fuselage_Height_4=data['Fuselage_Height_4'],
                    topangle_0=data['toptan_0'], topangle_1=data['toptan_1'], topangle_2 = data['toptan_2'],
                    topangle_3=data['toptan_3'],topangle_4 = data['toptan_4'], botangle_0 = data['bottan_0'],
                    botangle_1=data['bottan_1'], botangle_2 = data['bottan_2'], botangle_3 = data['bottan_3'],
                    botangle_4=data['bottan_4'], topstr_0=  data['topstr_0'], topstr_1=  data['topstr_1'], topstr_2= data['topstr_2'],
                    topstr_3=data['topstr_3'], topstr_4=  data['topstr_4'], botstr_0= data['botstr_0'],
                    botstr_1= data['botstr_1'], botstr_2= data['botstr_2'], botstr_3= data['botstr_3'], botstr_4= data['botstr_4'],

                    )
        fuse.Design()
        fuse.Modify_Xsec()
        vsp.Update()  # Update after fuselage creation

        #Wing Design
        MAC = data['Wing_Span']/AR
        #TR =round(random.uniform(0.5,1), 2)

        TR = data["Taper"]

        Root_Chord = (1.5 * MAC) / ((1 + TR + TR ** 2) / (1 + TR))
        Tip_Chord = TR * Root_Chord
        wing_postion_config = Wing_Position_Config(fuselage_length=data['Fuselage_Length'],
                                                   fuselage_height=data['Fuselage_Height_2'])
        wing_loc_data = {}  # stores the wing location for reference
        if data['Wing_Position'] == "Low":
            x_loc, z_loc = wing_postion_config.Low()
            wing_loc_data[index] = {'x_loc': x_loc,
                                'z_loc': z_loc}  # Store these values later for Engine Under Wing Position

        elif data['Wing_Position'] == "Mid":
            x_loc, z_loc = wing_postion_config.Mid()
            wing_loc_data[index] = {'x_loc': x_loc,
                                'z_loc': z_loc}  # Store these values later for Engine Under Wing Position

        elif data['Wing_Position'] == "High":
            x_loc, z_loc = wing_postion_config.High()
            wing_loc_data[index] = {'x_loc': x_loc,
                                'z_loc': z_loc}  # Store these values later for Engine Under Wing Position

        wing_instance = Wing(Xloc=x_loc, Zloc=z_loc, Span=data['Wing_Span'], Sweep=data["Sweep"],
                                 Tip=Tip_Chord, Root=Root_Chord, YRot=-3, Chord=MAC)
        wing_instance.Plan()
        wing_af = airfoil_path(data.get('Wing_Airfoil', ''))
        wing_instance.Sect(root_af=wing_af, tip_af=wing_af)
        wing_instance.XForm()
        vsp.Update()  # Update after wing creation

        # Tail Design
        tail_span = 0.25 * data['Wing_Span']  # Tail is related to wingspan
        tail_xloc = 0.85 * data['Fuselage_Length']

        #vertical
        lv = 0.5*data['Fuselage_Length'] # diference between tail xloc and cg
        Svt = (data['Vol_Vert']*data['Wing_Span']**3)/(AR*lv) #Vertical Tail Area
        #Svt = 0.2*
        bv = np.sqrt(2*Svt) #Vertical Tail SPan
        Crv = 0.95*Svt/bv #Vertical Root Chord
        Ctv = 0.6*Crv #vertical tip Chord

        #horizontal
        lh = 0.4*data['Fuselage_Length']
        Sht = (data['Vol_Hor'] * (data['Wing_Span']**2)*MAC)/(AR*lh) #Horizontal Tail Area
        bh = np.sqrt(6*Sht) #Horizontal Tail Span
        Crh = 1.2*Sht/bh #Horizontal Root Chord
        Cth = 0.5 * Crh ##Horizontal tip Chord
        htail_af = airfoil_path(data.get('HTail_Airfoil', ''))
        vtail_af = airfoil_path(data.get('VTail_Airfoil', ''))
        if data['Tail_Type'] == "Conventional":
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=0.47 * data['Fuselage_Height_3'],
                                        H_Span=bh, H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=0,
                                        H_sweep=11.8,
                                        V_Xloc=tail_xloc, V_Zloc=0.47 * data['Fuselage_Height_3'],
                                        V_Span=bv, V_Root=Crv,
                                        V_Tip=Ctv, V_diehedral=90, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()



        elif data['Tail_Type'] == "T-Tail":
            h_z_loc = 0.496 * bv + 0.47 * data['Fuselage_Height_3']
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=h_z_loc, H_Span=bh,
                                        H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=0,
                                        H_sweep=11.8,
                                        V_Xloc=tail_xloc, V_Span=bv,
                                        V_Root=Crv,V_Zloc=0.47 * data['Fuselage_Height_3'],
                                        V_Tip=Ctv, V_diehedral=90, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()


        elif data['Tail_Type'] == "Cruciform":
            h_z_loc = 0.3 * bv + 0.47 * data['Fuselage_Height_3']

            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=h_z_loc, H_Span=bh,
                                        H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=0,
                                        H_sweep=11.8,
                                        V_Xloc=tail_xloc, V_Span=bv,
                                        V_Root=Crv,V_Zloc=0.47 * data['Fuselage_Height_3'],
                                        V_Tip=Ctv, V_diehedral=90, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()

        elif data['Tail_Type'] == "Y-Tail":
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=0.47 * data['Fuselage_Height_3'],
                                        H_Span=bh, H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=30,
                                        H_sweep=21.8,
                                        V_Xloc=tail_xloc, V_Zloc=-0.4 * data['Fuselage_Height_3'],
                                        V_Span=bv, V_Root=Crv,
                                        V_Tip=Ctv, V_diehedral=-90,
                                        V_sweep=21.8, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()

        elif data['Tail_Type'] == "Inverted_Y-Tail":
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=-0.4 * data['Fuselage_Height_3'],
                                        H_Span=bh, H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=-30,
                                        H_sweep=21.8,
                                        V_Xloc=tail_xloc, V_Zloc=0.47 * data['Fuselage_Height_3'],
                                        V_Span=bv, V_Root=Crv,
                                        V_Tip=Ctv, V_diehedral=90,
                                        V_sweep=21.8, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()

        elif data['Tail_Type'] == "Dual-Tail":
            Dual_H_Sweep = math.degrees(math.atan((3) / (0.5 * tail_span)))
            tail_instance = Tail_Config(H_Span=bh, H_Xloc=0.85 * data['Fuselage_Length'],
                                        H_Zloc=0.47 * data['Fuselage_Height_3'],
                                        H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=0,
                                        H_sweep=15,
                                        V_Xloc=0.89 * data['Fuselage_Length'], V_Yloc=0.53 * bh,
                                        V_Zloc=0.4 * data['Fuselage_Height_3'], V_Span=bv,
                                        V_Root=Crv,
                                        V_Tip=Ctv, V_diehedral=90,
                                        V_sweep=21.8, Y_Rot=-4,
                                        H_Airfoil=htail_af, V_Airfoil=vtail_af)
            tail_instance.Conventional()


        elif data['Tail_Type'] == "V-Tail":
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=0.47 * data['Fuselage_Height_3'],
                                        H_Span=bh, H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=30,
                                        H_sweep=21.8, Y_Rot=-4,
                                        H_Airfoil=htail_af)
            tail_instance.V_Tail()

        elif data['Tail_Type'] == "Inverted_V-Tail":
            tail_instance = Tail_Config(H_Xloc=tail_xloc, H_Zloc=-0.4 * data['Fuselage_Height_3'],
                                        H_Span=bh, H_Root=Crh,
                                        H_Tip=Cth, H_diehedral=-30,
                                        H_sweep=21.8, Y_Rot=-4,
                                        H_Airfoil=htail_af)
            tail_instance.V_Tail()

        output_folder = "output_vsp_files"
        os.makedirs(output_folder, exist_ok=True)

        if final:
            filename =os.path.join(output_folder, f"UAVee_{index}.vsp3") #for the final population
        else:
            filename = os.path.join(output_folder, f"temp_design_{index}.vsp3")

        print(f"Saving file: {filename}")
        vsp.Update()  # Update geometry before saving
        vsp.WriteVSPFile(filename, vsp.SET_ALL)

        vsp.ClearVSPModel()
        print(Root_Chord)
        return filename #path for Aero Analysis


top_n_df = pd.read_csv('design_compare.csv') #uncommented by Manuel 5/7 since running mastercontoller2 did not continue the workflow
Designer = Master_Designer(top_n_df)
Designer.process_population()
