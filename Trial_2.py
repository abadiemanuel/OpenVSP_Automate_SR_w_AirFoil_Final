import openvsp as vsp
from openvsp import XS_FOUR_SERIES

# Every object starts at 0,0,0
# Add the basic geometries
"""
This is the section that directly interacts with OpenVSP. 
"""


# Ids for cross_section
GENERAL_FUSE = 5


# You apply changes

class Fuselage:
    fid = None  # Class attribute

    def __init__(self, length=20, Xloc=0.0, Yloc=0.0, Zloc=0.0, XRot=0.0, YRot=0.0, ZRot=0.0, Xsec=None,
                 fuselage_Width_0=2.5, fuselage_Height_0=3.0
                 , fuselage_Width_1=2.5, fuselage_Height_1=3.0, fuselage_Width_2=2.5, fuselage_Height_2=3.0,
                 fuselage_Width_3=2.5, fuselage_Height_3=3.0,
                 fuselage_Width_4=2.5, fuselage_Height_4=3.0, Nose_cap=1, Tail_cap=2, topangle_0=90, topangle_1=90,
                 topangle_2=90, topangle_3=90, topangle_4=90,
                 botangle_0=90, botangle_1=90, botangle_2=90, botangle_3=90, botangle_4=90, topstr_0=0.5, topstr_1=0.5,
                 topstr_2=0.5, topstr_3=0.5, topstr_4=0.5,
                 botstr_0=0.5, botstr_1=0.5, botstr_2=0.5, botstr_3=0.5, botstr_4=0.5,
                 xloc_percent=None,
                 ):  # Setting default values

        self.length = length
        self.xloc_percent = xloc_percent  # station positions as fractions of length (None = OpenVSP defaults)
        self.Xloc = Xloc
        self.Yloc = Yloc
        self.Zloc = Zloc
        self.XRot = XRot
        self.YRot = YRot
        self.ZRot = ZRot
        self.Xsec = Xsec
        self.fuselage_Width_0 = fuselage_Width_0
        self.fuselage_Height_0 = fuselage_Height_0
        self.fuselage_Width_1 = fuselage_Width_1
        self.fuselage_Height_1 = fuselage_Height_1
        self.fuselage_Width_2 = fuselage_Width_2
        self.fuselage_Height_2 = fuselage_Height_2
        self.fuselage_Width_3 = fuselage_Width_3
        self.fuselage_Height_3 = fuselage_Height_3
        self.fuselage_Width_4 = fuselage_Width_4
        self.fuselage_Height_4 = fuselage_Height_4
        self.Nose_cap = Nose_cap
        self.Tail_cap = Tail_cap
        self.topangle_0 = topangle_0
        self.topangle_1 = topangle_1
        self.topangle_2 = topangle_2
        self.topangle_3 = topangle_3
        self.topangle_4 = topangle_4
        self.botangle_0 = botangle_0
        self.botangle_1 = botangle_1
        self.botangle_2 = botangle_2
        self.botangle_3 = botangle_3
        self.botangle_4 = botangle_4
        self.topstr_0 = topstr_0
        self.topstr_1 = topstr_1
        self.topstr_2 = topstr_2
        self.topstr_3 = topstr_3
        self.topstr_4 = topstr_4
        self.botstr_0 = botstr_0
        self.botstr_1 = botstr_1
        self.botstr_2 = botstr_2
        self.botstr_3 = botstr_3
        self.botstr_4 = botstr_4

        # Initialize `fid` in the constructor so it's available in all methods
        # Only create fuselage geometry if it doesn't already exist
        if Fuselage.fid is None:
            Fuselage.fid = vsp.AddGeom("FUSELAGE")
        else:
            Fuselage.fid = vsp.AddGeom("FUSELAGE")
            print("Fuselage already exists. Modifying parameters.")

    def Design(self):
        """
        for the nose and tail cap:
        0-->None
        1-->Flat
        2-->Round
        3-->Edge
        4-->Sharp

        :return:
        """
        if self.Nose_cap == "N_None":
            self.Nose_cap = 0
        elif self.Nose_cap == "N_Flat":
            self.Nose_cap = 1
        elif self.Nose_cap == "N_Round":
            self.Nose_cap = 2
        elif self.Nose_cap == "N_Edge":
            self.Nose_cap = 3
        elif self.Nose_cap == "N_Sharp":
            self.Nose_cap = 4
        if self.Tail_cap == "T_Flat":
            self.Tail_cap = 1
        elif self.Tail_cap == "T_Round":
            self.Tail_cap = 2
        elif self.Tail_cap == "T_Edge":
            self.Tail_cap = 3
        elif self.Tail_cap == "T_Sharp":
            self.Tail_cap = 4
        vsp.SetParmVal(Fuselage.fid, "Length", "Design", self.length)  # We set the lenth of the Fuselage
        vsp.SetParmVal(Fuselage.fid, "CapUMinOption", "EndCap", self.Nose_cap)
        vsp.SetParmVal(Fuselage.fid, "CapUMaxOption", "EndCap", self.Tail_cap)
        vsp.Update()

    # Here we set the location of the fuselage which is usually 0
    def Xform(self):
        vsp.SetParmVal(Fuselage.fid, "X_Rel_Location", "XForm", self.Xloc)
        vsp.SetParmVal(Fuselage.fid, "Y_Rel_Location", "XForm", self.Yloc)
        vsp.SetParmVal(Fuselage.fid, "Z_Rel_Location", "XForm", self.Zloc)
        vsp.SetParmVal(Fuselage.fid, "X_Rel_Rotation", "XForm", self.XRot)
        vsp.SetParmVal(Fuselage.fid, "Y_Rel_Rotation", "XForm", self.YRot)
        vsp.SetParmVal(Fuselage.fid, "Z_Rel_Rotation", "XForm", self.ZRot)
        vsp.Update()

    def Modify_Xsec(self):
        xsec_surf = vsp.GetXSecSurf(Fuselage.fid, 0)  # Get Surface object
        print(xsec_surf)
        num_xsec_order = vsp.GetNumXSec(xsec_surf)  # number of cross sections
        print(f"num_xsec_order:{num_xsec_order}")
        for i in range(num_xsec_order):
            vsp.ChangeXSecShape(xsec_surf, i, GENERAL_FUSE)  # Change the xsection to general fuse
            x_sec = vsp.GetXSec(xsec_surf, i)  # Get the crossection
            width_attr = f"fuselage_Width_{i}"  # Attribute name for width
            height_attr = f"fuselage_Height_{i}"  # Attribute name for height
            topangle_attr = f"topangle_{i}"
            botangle_attr = f"botangle_{i}"
            topstr_attr = f"topstr_{i}"
            botstr_attr = f"botstr_{i}"

            fuselage_Width = getattr(self, width_attr, None)
            fuselage_Height = getattr(self, height_attr, None)
            topangle = getattr(self, topangle_attr, None)
            botangle = getattr(self, botangle_attr, None)
            topstr = getattr(self, topstr_attr, None)
            botstr = getattr(self, botstr_attr, None)

            # Collection of variables for modification/Xsec
            parmid1 = vsp.GetXSecParm(x_sec, "Width")  # Collect the xsection/Width
            parmid2 = vsp.GetXSecParm(x_sec, "Height")  # Collect the xsection/Height
            parmid3 = vsp.GetXSecParm(x_sec, "TopTanAngle") #Collect the TopTanAngle of the section
            parmid4 = vsp.GetXSecParm(x_sec, "BotTanAngle")
            parmid5 = vsp.GetXSecParm(x_sec, "TopStr")
            parmid6 = vsp.GetXSecParm(x_sec, "BotStr")
            parmid7 = vsp.GetXSecParm(x_sec, "UpStr")
            parmid8 = vsp.GetXSecParm(x_sec, "LowStr")


            vsp.SetParmVal(parmid1, fuselage_Width)  # We set the dimensions of the fuselage
            vsp.SetParmVal(parmid2, fuselage_Height)
            vsp.SetParmVal(parmid3, topangle)
            vsp.SetParmVal(parmid4, botangle)
            vsp.SetParmVal(parmid5, topstr)
            vsp.SetParmVal(parmid6, botstr)


            # Collection of variables for modification/Skinning

        # Station positions along the body. OpenVSP keeps each interior station between its
        # neighbours, so sweep forwards and backwards until every station reaches its target.
        if self.xloc_percent is not None:
            interior = range(1, min(num_xsec_order, len(self.xloc_percent)) - 1)
            for _ in range(3):
                for i in list(interior) + list(reversed(interior)):
                    vsp.SetParmVal(vsp.GetXSecParm(vsp.GetXSec(xsec_surf, i), "XLocPercent"),
                                   float(self.xloc_percent[i]))
                vsp.Update()

        vsp.Update()


# We assume a uniform cross_section through out

class Wing:
    wid = None

    def __init__(self, Xloc=0.0, Yloc=0.0, Zloc=0.0, XRot=0.0, YRot=0.0, ZRot=0.0, Xsec=None, Chord=12.0, Span=10.0,
                 Sweep=30.0, diehedral=0.0, Root=4.0, Tip=4.0):
        self.Xloc = Xloc
        self.Yloc = Yloc
        self.Zloc = Zloc
        self.XRot = XRot
        self.YRot = YRot
        self.ZRot = ZRot
        self.Xsec = Xsec
        self.Chord = Chord
        self.Span = Span
        self.Sweep = Sweep
        self.diehedral = diehedral
        self.Root = Root
        self.Tip = Tip
        if Wing.wid is None:
            Wing.wid = vsp.AddGeom("WING")
            print("Wing added.")
        else:
            Wing.wid = vsp.AddGeom("WING")
            print("Wing already exists. Modifying parameters.")

    def XForm(self):
        vsp.SetParmVal(Wing.wid, "X_Rel_Location", "XForm", self.Xloc)
        vsp.SetParmVal(Wing.wid, "Y_Rel_Location", "XForm", self.Yloc)
        vsp.SetParmVal(Wing.wid, "Z_Rel_Location", "XForm", self.Zloc)
        vsp.SetParmVal(Wing.wid, "X_Rel_Rotation", "XForm", self.XRot)
        vsp.SetParmVal(Wing.wid, "Y_Rel_Rotation", "XForm", self.YRot)
        vsp.SetParmVal(Wing.wid, "Z_Rel_Rotation", "XForm", self.ZRot)
        vsp.Update()

    def Plan(self):
        vsp.SetParmVal(Wing.wid, "TotalSpan", "WingGeom", self.Span)
        vsp.SetParmVal(Wing.wid, "TotalChord", "WingGeom", self.Chord)
        vsp.Update()



    def Sect(self, root_af="", tip_af=""):
        # Set geometry values
        vsp.SetParmVal(Wing.wid, "Root_Chord", "XSec_1", self.Root)
        vsp.SetParmVal(Wing.wid, "Tip_Chord", "XSec_1", self.Tip)
        vsp.SetParmVal(Wing.wid, "Sweep", "XSec_1", self.Sweep)
        vsp.SetParmVal(Wing.wid, "Dihedral", "XSec_1", self.diehedral)

        # Only set airfoils if file paths are provided
        if root_af and tip_af:
            # Get XSecSurf ID for the wing
            xsec_surf = vsp.GetXSecSurf(Wing.wid, 0)

            # Set ROOT section (XSec 0)
            vsp.ChangeXSecShape(xsec_surf, 0, vsp.XS_FILE_AIRFOIL)
            xsec0 = vsp.GetXSec(xsec_surf, 0)
            vsp.ReadFileAirfoil(xsec0, root_af)

            # Set TIP section (XSec 1)
            vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_FILE_AIRFOIL)
            xsec1 = vsp.GetXSec(xsec_surf, 1)
            vsp.ReadFileAirfoil(xsec1, tip_af)

        vsp.Update()

"""
     def Sect(self):
        vsp.SetParmVal(Wing.wid, "Root_Chord", "XSec_1", self.Root)
        vsp.SetParmVal(Wing.wid, "Tip_Chord", "XSec_1", self.Tip)
        vsp.SetParmVal(Wing.wid, "Sweep", "XSec_1", self.Sweep)
        vsp.SetParmVal(Wing.wid, "Dihedral", "XSec_1", self.diehedral)
        vsp.Update()

"""

# pid = vsp.AddGeom("PROP")
class Propulsion:
    propid = None

    def __init__(self, length=3.0, Width=5.0, Thick_cord=0.136, Chord=2.25, Xloc=0.0, Yloc=0.0,
                 Pod_Xloc=0.0,Pod_Yloc=0.0,Pod_Zloc=0.0,
                 Zloc=0.0, XRot=0.0,YRot=0.0, ZRot=0.0, Xsec=None, Diameter=30, num_blades=3,
                 Duct_Diameter=2, Duct_Angle=8, Fine_Ratio=10, Prop_Scale = 1, Turbofan_Scale = 1, Turboprop_scale = 1):
        self.Xloc = Xloc
        self.Yloc = Yloc
        self.Zloc = Zloc
        self.Pod_Xloc = Pod_Xloc
        self.Pod_Yloc = Pod_Yloc
        self.Pod_Zloc = Pod_Zloc
        self.XRot = XRot
        self.YRot = YRot
        self.ZRot = ZRot
        self.Xsec = Xsec
        self.Diameter = Diameter
        self.num_blades = num_blades
        self.length = length
        self.Width = Width
        self.Thick_cord = Thick_cord
        self.Chord = Chord
        self.Duct_Diameter = Duct_Diameter
        self.Duct_Angle = Duct_Angle
        self.Fine_Ratio = Fine_Ratio
        self.Prop_Scale = Prop_Scale
        self.Turbofan_Scale = Turbofan_Scale
        self.Turboprop_scale = Turboprop_scale

        Propulsion.propid = vsp.AddGeom("PROP")
        print("Propeller added.")

    def Propeller(self):
        vsp.SetParmVal(Propulsion.propid, "X_Rel_Location", "XForm", self.Xloc)
        vsp.SetParmVal(Propulsion.propid, "Y_Rel_Location", "XForm", self.Yloc)
        vsp.SetParmVal(Propulsion.propid, "Z_Rel_Location", "XForm", self.Zloc)
        vsp.SetParmVal(Propulsion.propid, "X_Rel_Rotation", "XForm", self.XRot)
        vsp.SetParmVal(Propulsion.propid, "Y_Rel_Rotation", "XForm", self.YRot)
        vsp.SetParmVal(Propulsion.propid, "Z_Rel_Rotation", "XForm", self.ZRot)
        vsp.SetParmVal(Propulsion.propid, "Diameter", "Design", self.Diameter)
        vsp.SetParmVal(Propulsion.propid, "NumBlade", "Design", self.num_blades)
        vsp.SetParmVal(Propulsion.propid, "Scale", "XForm", self.Prop_Scale)
        vsp.Update()

    def Turbofan(self):
        # Modifying the duct
        # Four_series = 7
        ductid = vsp.AddGeom("BODYOFREVOLUTION", "")
        vsp.ChangeBORXSecShape(ductid, XS_FOUR_SERIES)  # Used to change the crosssection
        # vsp.SetGeomName(ductid,"Duct")

        vsp.SetParmVal(ductid, "X_Rel_Location", "XForm", self.Xloc)
        vsp.SetParmVal(ductid, "Y_Rel_Location", "XForm", self.Yloc)
        vsp.SetParmVal(ductid, "Z_Rel_Location", "XForm", self.Zloc)
        vsp.SetParmVal(ductid, "X_Rel_Rotation", "XForm", self.XRot)
        vsp.SetParmVal(ductid, "Y_Rel_Rotation", "XForm", self.YRot)
        vsp.SetParmVal(ductid, "Z_Rel_Rotation", "XForm", self.ZRot)
        vsp.SetParmVal(ductid, "Chord", "XSecCurve", self.Chord)
        vsp.SetParmVal(ductid, "ThickChord", "XSecCurve", self.Thick_cord)
        vsp.SetParmVal(ductid, "Diameter", "Design", self.Duct_Diameter)
        propeller_diameter_for_turbofan = 0.85 * self.Duct_Diameter * self.Turbofan_Scale
        vsp.SetParmVal(Propulsion.propid, "Diameter", "Design", propeller_diameter_for_turbofan)
        vsp.SetParmVal(ductid, "Angle", "Design", self.Duct_Angle)
        vsp.SetParmVal(ductid, "Scale", "XForm", self.Turbofan_Scale)
        vsp.Update()


        # Modifying the Pod

    def Turboprop(self):
        Podid = vsp.AddGeom("POD")

        vsp.SetParmVal(Podid, "X_Rel_Location", "XForm", self.Xloc)
        vsp.SetParmVal(Podid, "Y_Rel_Location", "XForm", self.Yloc)
        vsp.SetParmVal(Podid, "Z_Rel_Location", "XForm", self.Zloc)
        vsp.SetParmVal(Podid, "X_Rel_Location", "XForm", self.Pod_Xloc)
        vsp.SetParmVal(Podid, "X_Rel_Rotation", "XForm", self.XRot)
        vsp.SetParmVal(Podid, "Y_Rel_Rotation", "XForm", self.YRot)
        vsp.SetParmVal(Podid, "Z_Rel_Rotation", "XForm", self.ZRot)
        vsp.SetParmVal(Podid, "Length", "Design", self.length)
        propeller_diameter_for_turbofan = 0.85 * self.length * self.Turboprop_scale
        vsp.SetParmVal(Propulsion.propid, "Diameter", "Design", propeller_diameter_for_turbofan)
        vsp.SetParmVal(Podid, "FineRatio", "Design", self.Fine_Ratio)
        vsp.SetParmVal(Podid, "Scale", "XForm", self.Turboprop_scale)
        vsp.Update()

    # vsp.AddGeom("PROP")




# Create an instance of the Fuselage class
# fuselage_instance = Fuselage(length=10.0)
# Call the Design method on the instance
# fuselage_instance.Design()
# fuselage_instance.Modify_Xsec()

# filename = f"Aircraft.vsp4"

# print(f"Saving file: ")
# vsp.WriteVSPFile(filename, vsp.SET_ALL)