from numpy.ma.core import arctan
import random

#from Master_Controller import sweep
from Trial_2 import Wing
import math

"""
This section is responsible for the configurations
"""
class Tail_Config:
    def __init__(self, H_Xloc=0,H_Zloc=0,H_Span=15, H_Root=4, H_Tip=1, H_diehedral=45,H_sweep = 0,
                 V_Xloc=5,V_Zloc=0,V_Yloc=0.001,V_Span=15, V_Root=4, V_Tip=1, V_diehedral=90, V_sweep =0,Y_Rot=0,
                 H_Airfoil="", V_Airfoil=""):
        self.H_Xloc = H_Xloc
        self.H_Zloc = H_Zloc
        self.H_Span = H_Span
        self.H_Root = H_Root
        self.H_Tip = H_Tip
        self.H_diehedral = H_diehedral
        self.H_sweep = H_sweep
        self.V_Xloc = V_Xloc
        self.V_Yloc = V_Yloc
        self.V_Zloc = V_Zloc
        self.V_Span = V_Span
        self.V_Root = V_Root
        self.V_Tip = V_Tip
        self.V_diehedral = V_diehedral
        self.V_sweep = V_sweep
        self.Y_Rot = Y_Rot
        self.H_Airfoil = H_Airfoil
        self.V_Airfoil = V_Airfoil



    def Conventional(self):
        """
        This function will be used for Conventional, T, Cruciform, Dual, Y and Inverted-Ytail
        :return:
        """
        H_Tail = Wing(Xloc=self.H_Xloc,Zloc=self.H_Zloc, Span=self.H_Span,Root=self.H_Root,Tip=self.H_Tip,diehedral=self.H_diehedral, Sweep=self.H_sweep, YRot=self.Y_Rot)
        H_Tail.Plan()
        H_Tail.Sect(root_af=self.H_Airfoil, tip_af=self.H_Airfoil)
        H_Tail.XForm()

        V_Tail = Wing(Xloc=self.V_Xloc,Yloc=self.V_Yloc,Zloc=self.V_Zloc ,Span=self.V_Span,Root=self.V_Root,Tip=self.V_Tip,diehedral=self.V_diehedral, Sweep=self.V_sweep)
        V_Tail.Plan()
        V_Tail.Sect(root_af=self.V_Airfoil, tip_af=self.V_Airfoil)
        V_Tail.XForm()


    def V_Tail(self):
        """
        This function will be used for V and Inverted V-tail
        :return:
        """
        H_Tail = Wing(Xloc=self.H_Xloc,Zloc=self.H_Zloc, Span=self.H_Span,Root=self.H_Root,Tip=self.H_Tip,diehedral=self.H_diehedral, Sweep=self.H_sweep)
        H_Tail.Plan()
        H_Tail.Sect(root_af=self.H_Airfoil, tip_af=self.H_Airfoil)
        H_Tail.XForm()

#For the wing type configuration
class Wing_Type_Config:
    def __init__(self, wing_root_chord=1, wing_span=1, Taper =0.5 ):
        self.wing_root_chord = wing_root_chord
        self.wing_span = wing_span
        self.Taper = Taper

    def SLTT(self):

        T_C = self.Taper* self.wing_root_chord
        #SweepX = round(random.uniform(0,1.0), 2)
        SweepX = 0.5
        return T_C, SweepX

    def TLTT(self):
        T_C = self.Taper * self.wing_root_chord
        Sweep = math.degrees(math.atan((self.wing_root_chord - T_C)/(0.5 * self.wing_span)))
        #SweepX = round(random.uniform(1, Sweep), 2)
        SweepX = (1+ Sweep)/2
        return T_C, SweepX

    def TLST(self):
        T_C = self.Taper * self.wing_root_chord
        SweepX = math.degrees(math.atan((self.wing_root_chord - T_C)/(0.5 * self.wing_span)))
        return T_C, SweepX

    def SLST(self):
        T_C = self.Taper*self.wing_root_chord
        SweepX = 0
        return T_C, SweepX

    def Delta(self):
        T_C = self.Taper*self.wing_root_chord
        SweepX = math.degrees(math.atan((self.wing_root_chord - T_C)/(0.5 * self.wing_span)))
        return T_C, SweepX

class Wing_Position_Config:
    def __init__(self, fuselage_length=1, fuselage_height=1):
        self.fuselage_length = fuselage_length
        self.fuselage_height = fuselage_height
    #later we will reference the middle cross-section of the fuselage
    def Low(self):
        Wing_X_loc = 0.4 * self.fuselage_length
        Wing_Z_Loc = -0.4 * self.fuselage_height
        return Wing_X_loc, Wing_Z_Loc

    def Mid(self):
        Wing_X_loc = 0.4 * self.fuselage_length
        Wing_Z_Loc = 0
        return Wing_X_loc, Wing_Z_Loc

    def High(self):
        Wing_X_loc = 0.4 * self.fuselage_length
        Wing_Z_Loc = 0.47*self.fuselage_height
        return Wing_X_loc, Wing_Z_Loc
