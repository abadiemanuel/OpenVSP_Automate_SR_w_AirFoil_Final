from operator import index
import joblib
from pyparsing import empty
import math
import numpy as np

from vtkmodules.web.render_window_serializer import linspace
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d
import pandas as pd


#Error checker
def get_input(prompt, default):
    while True:
        try:
            value = input(f"{prompt} ")
            value = float(value) if value.strip() else float(default)
            if value <= 0:
                print("Please enter a value greater than 0.")
                continue
            return value
        except ValueError:
            print("Invalid. Please enter a valid number.")


# Use default values (no interactive input for automated runs)
# To enable interactive mode, call get_interactive_inputs() function
inputs = {
    'payload': 250, #kg
    'payload_vol': 2.5, #m3
    'cruise_speed': 82.0, #m/s 
    'Range': 2500,   #km
    'absolute_ceiling': 9144, #m
    'service_ceiling': 7620.0, #m
    'cl_max': 1.6, #max lift coefficient
    'cruise_ceiling' :5000.0, #m
    'Stall_Speed': 28.3,  # m/s According to EASA (55kts)
}

def get_interactive_inputs():
    """Call this function to enable interactive input mode"""
    global inputs
    inputs = {
        'payload': get_input(("Enter payload (kg): "), 386),
        'payload_vol': get_input(("Enter payload volume (m^3): "), 4),
        'cruise_speed': get_input(("Enter cruise speed (m/s): "),82),
        'Range': get_input(("Enter range (km): "), 740.8),
        'absolute_ceiling': get_input(("Enter Absolute ceiling (m): ") , 15240),
        'service_ceiling': float(7620),
        'cl_max': float(1.6),
        'cruise_ceiling': get_input(("Enter Cruise_ceiling (m): "), 7620),
        'Stall_Speed': get_input(("Enter Stall speed (m/s): ") , 40),# According to EASA
    }
    return inputs



#All these assume propeller drive
g = 9.81 #m/s2

Mto = inputs['payload']*g*5 # Maximum takeoff weight


rho_sl = 1.2225 #kg/m3

Vs = inputs['Stall_Speed'] #Stall speed-according to certification requirements
Vmax = 1.3 * inputs['cruise_speed'] # Calculated
Vto = 1.3 * Vs #Calculated takeoff speed
osward = 0.8 #Oswald efficiency factor

mupto = 0.55 #propeller efficiency at takeoff
muppac = 0.8 #propeller efficiency at cruise alt
muroc = 0.6

#Payload Radius
payload_radius = 2*np.cbrt((3*inputs['payload_vol'])/(4*np.pi)) #This is diameter rather

#long Range >15, medium 8-15 in km
if  inputs['Range']<=100 :#short range
    AR = 6
    Endurance=5


elif 100 < inputs['Range'] <= 400 :#medium range
    AR = 12
    Endurance=20
elif 400 < inputs['Range']  :#Long range
    AR = 20
    Endurance=25

#Modelling of relaive density as a fuction of altitude, I need to check for that
#and change all the rho_c/rho_sl
#below 11000m

if inputs['absolute_ceiling']<=11000: #m
    T = 15.04 - 0.00649*inputs['absolute_ceiling']
    P = 101.29 * ((T + 273.1)/288.08)**5.256
elif 11000<inputs['absolute_ceiling']<=25000:
    T = -56.46
    P = 22.65 * np.exp(1.73 - 0.000157*inputs['absolute_ceiling'])
elif inputs['absolute_ceiling']>25000:
    T = -131.21 + 0.00299*inputs['absolute_ceiling']
    P = 2.488 * ((T + 273.1)/216.6)**-11.388
rho_ac = P/(0.2869 * (T + 273.1))

#Cruise ceiling
if inputs['cruise_ceiling']<=11000: #m
    T = 15.04 - 0.00649*inputs['cruise_ceiling']
    P = 101.29 * ((T + 273.1)/288.08)**5.256
elif 11000<inputs['cruise_ceiling']<=25000:
    T = -56.46
    P = 22.65 * np.exp(1.73 - 0.000157*inputs['cruise_ceiling'])
elif inputs['cruise_ceiling']>25000:
    T = -131.21 + 0.00299*inputs['cruise_ceiling']
    P = 2.488 * ((T + 273.1)/216.6)**-11.388
rho_c = P/(0.2869 * (T + 273.1))

#cruise speed to Mach number conversion
gamma = 1.4 #ratio of specific heat, dry air
R = 287.05 #gas constant for air, J/(kg*k)
c = np.sqrt(gamma*R*(T + 273.1)) #speed of sound at cruise, T converted to kelvin
cruise_mach = inputs['cruise_speed']/c #Mach number at cruise

print(f"rho_c = {rho_c}")
print(f"rho_ac = {rho_ac}")

#Rate of climb at certain ceilings
ROCAC = 0 #Rate of climb at absolute ceiling
ROCSC = 0.5 #Rate of climb at Service ceiling
ROCCrc = 1.5 #Rate of climb at cruise ceiling

Sto = 500 #launch unit length in m
K = 0.398/AR #Induced factor
Cdo = 0.0245
Cdoto = 0.0835 #Takeoff zero lift Drag coefficient gotten from literature
Clto = 0.85 #Lift coefficient at Takeoff off
Cdto = 0.0835 + K * 0.7225 #drag coefficient in take off config
Clr = Clto
mu = 0.08 # runway friction coefficient
Cdg = Cdto - mu*Clto






#plotting
fig, ax = plt.subplots()


#Wing_loding at v stall
Wing_Loading_Stall = 0.5 * rho_sl * Vs**2*inputs['cl_max']
#plt.plot([Wing_Loading_Stall, Wing_Loading_Stall],[-0.5, 2] ,color='r', label='Stall speed')



epsilon = 1e-9
# Wing Power loading at Vmax calc
Wing_loading = np.linspace(1,1.2*Wing_Loading_Stall,500)
Power_loading_maxspeed = ((muppac)*(rho_c/rho_sl))/(((0.5 * rho_sl * Vmax**3*Cdo)/(Wing_loading)) + ((2*K*Wing_loading)/(rho_c*Vmax)))
plt.plot(Wing_loading, Power_loading_maxspeed, color='g',linestyle= '--', label='Vmax')
print( f"min:{min(Power_loading_maxspeed)}, max:{max(Power_loading_maxspeed)}")

#Takeoff
Power_loading_takeoff = ((1-np.exp((0.6*rho_sl*g*Cdg*Sto)/Wing_loading))/(mu - (mu + Cdg/Clr)*(np.exp((0.6*rho_sl*g*Cdg*Sto)/Wing_loading))))*(mupto/Vto)
plt.plot(Wing_loading, Power_loading_takeoff, color='b',linestyle = '--', label='WPto')


#Rate of climb
#from EASA CS VLA 65 we take ROC to be 2 m/s
LDmax = 1/(2*np.sqrt(Cdo*K))#Gotten from a text book
ROC = 2 #m/s
Power_loading_ROC = 1/((ROC/muroc) + np.sqrt((2/(rho_sl*np.sqrt(3*Cdo/K)))*Wing_loading)*(1.155/(LDmax*muroc)))
plt.plot(Wing_loading, Power_loading_ROC, color='gold',linestyle = '--', label='WPROC')

#Ceiling/ rho @ cruise ceiling alt
Power_loading_Ceil = (rho_c/rho_sl)/(ROCCrc/muppac + (np.sqrt((2/(rho_c*np.sqrt(3*Cdo/K)))*Wing_loading)*(1.155/(LDmax*muppac))))
plt.plot(Wing_loading, Power_loading_Ceil, color='cyan',linestyle = '--',  label='WPCeil')



# Compute upper boundary (minimum of all Power_loading curves)
min_power_loading = np.minimum.reduce([Power_loading_maxspeed, Power_loading_takeoff, Power_loading_ROC, Power_loading_Ceil]) #Get the minimum plot
# Mask for feasible x (x >= Wing_Loading_Stall)
mask_x = Wing_loading <= Wing_Loading_Stall #Getting wing loading values less than stall
feasible_x = Wing_loading[mask_x] #Generate x arrays from it
feasible_y_upper = min_power_loading[mask_x] #Generate corresponding y values using the lowest plot

# Generate grid of points and check feasibility
x_grid, y_grid = np.meshgrid(
    np.linspace(feasible_x.min(), feasible_x.max(), 100),
    np.linspace(0, feasible_y_upper.max(), 100) #create a grid out it
)
f_upper = interp1d(feasible_x, feasible_y_upper, bounds_error=False, fill_value=np.inf) #FInd new upper limits on the lowest plot
mask = (x_grid <= Wing_Loading_Stall) & (y_grid <= f_upper(x_grid))
# Extract feasible points
feasible_points = np.column_stack((x_grid[mask], y_grid[mask]))


df = pd.DataFrame(feasible_points, columns=['wing_loading', 'Power_loading'])
df.to_csv("feasible_points.csv", index=False)

A = feasible_points[-2000:]

B  = (Mto)/A
#print(B)

Wl_min = np.min(B[:,0])
Wl_max = np.max(B[:,0])
Wing_Area = [1.2*float(Wl_min),float(Wl_max)] #TO move it away from the stall speed
print(Wing_Area)
Wing_span =  np.sqrt(AR*np.array(Wing_Area))#Design Variable
print(Wing_span)

Pl_min = np.min(B[:,1])
Pl_max = np.max(B[:,1])
Eng_pow = [float(Pl_min),float(Pl_max)]
print(f"Eng_pow: {Eng_pow}")

ax.set_xlim(1,1.5*Wing_Loading_Stall)
ax.set_ylim(0, 20*np.max(feasible_points[:,1]))
plt.xlabel("W/S, N/m^2")
plt.ylabel("W/P, N/W")
plt.title("Constraint Plot")
plt.plot([Wing_Loading_Stall, Wing_Loading_Stall],[0, 20*np.max(feasible_points[:,1])] ,color='r', linestyle = '--', label='Stall speed')

plt.scatter(feasible_points[:,0], feasible_points[:,1], color='red', s=2, label='Feasible Region')
plt.legend()
#plt.show()




