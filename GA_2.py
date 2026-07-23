import random
import math

from numpy.random import randint
import time

from DT import decoded_pred
from Master_Controller_2 import *
from Sizing import *
import pandas as pd
import numpy as np

from Analysis import *
from matplotlib import pyplot as plt

# Discrete Variables
"""
This code uses the Weighted Sum Method to run the framework. It is not working efficiently at the moment.

"""
Wing_Position = ["Low", "Mid", "High"]
Wing_Type = ["SLTT", "TLTT", "TLST", "SLST", "Delta"]
Tail_Type = ["Conventional", "T-Tail", "Cruciform", "Dual-Tail", "V-Tail", "Inverted_V-Tai", "Y-Tail",
             "Inverted_Y-Tail"]
Engine_Type = ["Turboprop", "Turbofan", "PistonProp"]
Engine_Position = ["Under_Wing", "Inside", "Fuselage_Nose", "Rear_of_Fuselage"]

# Encoding in the Genetic space


# For Continuous variables we use 6 bits
# These are the bounds
Taper = [0.3,1]
Sweep = [0, 20]
Vol_Hor = [0.7,1.1]
Vol_Vert = [0.02, 0.1]

Span=Wing_span#Design Variable
power = Eng_pow
Fuse_length = -0.0092 * Wing_span**2 + 0.7391*Wing_span - 0.281
cg = 0.33*np.average(Fuse_length) #Center of mass of the aircraft

print(f"cg:{cg}")

Fuselage_Width_0 = (0.1*payload_radius, 0.5*payload_radius)
Fuselage_Height_0 = (0.1*payload_radius, 0.5*payload_radius)
Fuselage_Width_1 =(1.2*payload_radius, 1.5*payload_radius)#
Fuselage_Height_1 = (1.2*payload_radius, 1.5*payload_radius)
Fuselage_Width_2 = (0.6667*payload_radius, 1.2*payload_radius)#1
Fuselage_Height_2 = (0.6667*payload_radius, 1.2*payload_radius)#1
Fuselage_Width_3 = (0.6667*payload_radius, 1.2*payload_radius)#1
Fuselage_Height_3 = (0.6667*payload_radius, 1.2*payload_radius)#1
Fuselage_Width_4 = (0.333*payload_radius, 0.8*payload_radius)
Fuselage_Height_4 = (0.333*payload_radius, 0.8*payload_radius)

toptan_0 = (60,120)
toptan_1 = (60,120)
toptan_2 = (60,120)
toptan_3 = (60,120)
toptan_4 = (60,120)
bottan_0 = (60,12)
bottan_1 = (60,120)
bottan_2 = (60,120)
bottan_3 = (60,120)
bottan_4 = (60,120)
topstr_0 = (0.5, 1.83)
topstr_1 = (0.5, 1.83)
topstr_2 = (0.5, 1.83)
topstr_3 = (0.5, 1.83)
topstr_4 = (0.5, 1.83)
botstr_0 = (0.5, 1.83)
botstr_1 = (0.5, 1.83)
botstr_2 = (0.5, 1.83)
botstr_3 = (0.5, 1.83)
botstr_4 = (0.5, 1.83)


def objective(decoded_cont, decoded_discrete, dataframe,population_df, weights):
    # Continuous variables contribution
    Designer = Master_Designer(population_df)
    vsp_file = Designer.create_aircraft(index=0, final=False)

    aero = Aero(path=vsp_file, Engine_Power=decoded_cont[1], xcg = cg) #second value of decoded cont which is power
    #Analysis values

    obj = aero.compute_objective()
    wcont = weights['wcont']
    cont_sum,L2D,Cmy,CL,Cdtotal,cost,Area = obj


    # Discrete variables contribution
    wcost = weights['wcost']
    wweight = weights['wweight']

    cost_sum = sum(dataframe.loc[var, 'Cost'] for var in decoded_discrete)
    weight_sum = sum(dataframe.loc[var, 'Weight'] for var in decoded_discrete)

    grade = wcont * cont_sum - wcost * cost_sum/30 - wweight * weight_sum #minimizing (negative goes up positive down)
    # Final objective value
    return grade, CL, Cmy, cost_sum,L2D,cost,Area #minimize all except -l2d in conta

# Decode continuous values
def decode_cont(bounds_cont, n_bits_cont, bitstring):
    decoded_cont = []
    largest = 2 ** n_bits_cont
    for i in range(len(bounds_cont)):
        start, end = i * n_bits_cont, (i + 1) * n_bits_cont
        substring = bitstring[start:end]
        chars = ''.join([str(s) for s in substring])
        integer = int(chars, 2)
        value = bounds_cont[i][0] + (integer / largest) * (bounds_cont[i][1] - bounds_cont[i][0])
        decoded_cont.append(value)
    return decoded_cont


def decode_discrete(bounds_discrete, n_bits_discrete, bitstring, lookup_table):
    decoded_discrete = []
    start = 0  # Initialize the starting index

    for i in range(len(bounds_discrete)):
        n_bits = n_bits_discrete[i]  # Number of bits for the current variable
        end = start + n_bits

        # Extract the substring and decode using the lookup table
        substring = bitstring[start:end]
        chars = ''.join([str(s) for s in substring])
        decoded_value = lookup_table[bounds_discrete[i]].get(chars, "Unknown")

        decoded_discrete.append(decoded_value)
        start = end  # Update the starting index

    return decoded_discrete



# Tournament Selection
"""
Randomly select a percentage of the population for a tournament, where the one with the lowest score is chosen
"""
def selection(pop, scores, k=3):
    selection_ix = randint(len(pop))
    for ix in randint(0, len(pop), k - 1):
        if scores[ix] < scores[selection_ix]:
            selection_ix = ix
    return pop[selection_ix]

# Crossover
def crossover(p1, p2, r_cross):
    c1, c2 = p1.copy(), p2.copy()
    if random.random() < r_cross:
        pt = randint(1, len(p1) - 2)
        c1 = p1[:pt] + p2[pt:]
        c2 = p2[:pt] + p1[pt:]
    return [c1, c2]

# Mutation
def mutation(bitstring, r_mut):
    for i in range(len(bitstring)):
        if random.random() < r_mut:
            bitstring[i] = 1 - bitstring[i]
    return bitstring

# Genetic Algorithm
def genetic_algorithm(objective, bounds_cont, n_bits_cont, bounds_discret, n_bits_discrete,lookup_table, dataframe,weights, n_iter, n_pop, r_cross, r_mut,):
    # Initialize population
    pop = [
        randint(0, 2, n_bits_cont * len(bounds_cont)).tolist() +
        randint(0, 2, sum(n_bits_discrete)).tolist()  # Sum of n_bits_discrete for the new decode_discrete
        for _ in range(n_pop)
    ]

    #Initialization of dataframe for top_n individuals
    columns = [ "Wing_Span","Power","Taper","Sweep","Vol_Hor","Vol_Vert", "Fuselage_Length","Fuselage_Width_0","Fuselage_Height_0","Fuselage_Width_1",
         "Fuselage_Height_1","Fuselage_Width_2","Fuselage_Height_2","Fuselage_Width_3","Fuselage_Height_3",
                   "Fuselage_Width_4","Fuselage_Height_4", "toptan_0", "toptan_1", "toptan_2", "toptan_3", "toptan_4","bottan_0", "bottan_1",
         "bottan_2", "bottan_3","bottan_4", "topstr_0", "topstr_1", "topstr_2", "topstr_3", "topstr_4","botstr_0", "botstr_1","botstr_2", "botstr_3", "botstr_4",
         "Wing_Type","Wing_Position","Tail_Type","Fuselage_NoseCap", "Fuselage_TailCap",
         "Engine_Type", "Engine_Position", "Engine_Number", "Scores","Cmy","Cl","Cdtot", "Design_Bits"]
    columns_pop =["Wing_Span","Power","Taper","Sweep","Vol_Hor","Vol_Vert", "Fuselage_Length","Fuselage_Width_0","Fuselage_Height_0","Fuselage_Width_1",
         "Fuselage_Height_1","Fuselage_Width_2","Fuselage_Height_2","Fuselage_Width_3","Fuselage_Height_3",
                   "Fuselage_Width_4","Fuselage_Height_4", "toptan_0", "toptan_1", "toptan_2", "toptan_3", "toptan_4","bottan_0", "bottan_1",
         "bottan_2", "bottan_3","bottan_4", "topstr_0", "topstr_1", "topstr_2", "topstr_3", "topstr_4","botstr_0", "botstr_1","botstr_2", "botstr_3", "botstr_4",
         "Wing_Type","Wing_Position","Tail_Type","Fuselage_NoseCap", "Fuselage_TailCap",
         "Engine_Type", "Engine_Position", "Engine_Number",]
    top_n_df = pd.DataFrame(columns=columns)

    # Decode first population and evaluate
    best, best_eval = 0, float('inf')
    iterate = 0
    iterate_vals,scores_avg, cl_avg,Config_avg, cost_avg,L2D_avg, area_avg =[],[],[],[],[],[],[]




    for gen in range(n_iter):

        decoded = [
            decode_cont(bounds_cont, n_bits_cont, p[:n_bits_cont * len(bounds_cont)]) +
            decode_discrete(bounds_discret, n_bits_discrete, p[n_bits_cont * len(bounds_cont):],lookup_table)
            for p in pop
        ]
        #scores = [objective(d[:len(bounds_cont)], d[len(bounds_cont):], dataframe, weights) for d in decoded]
        #Penalty scores for certain combinations
        penalty_conditions = [
            ("Fuselage_Nose", "Engine_Number_Two"),
            ("Fuselage_Nose", "Engine_Number_Four"),
            ("Fuselage_Nose", "Engine_Number_Six"),
            ("Fuselage_Nose", "Engine_Number_Eight"),
            ("Rear_of_Fuselage", "Engine_Number_Two"),
            ("Under_Wing", "Engine_Number_One"),
        ]
        scores = []
        #Additional values to add
        Cl_vals = []
        Cmy_vals = []
        config_vals = []
        cost_vals = []
        L2D_vals = []
        area_vals = []



        for d in decoded:
            population_df = pd.DataFrame([d],columns=columns_pop)

            #Pull taper and sweep out for configs
            if population_df["Taper"].iloc[0] > 0.9:
                population_df["Wing_Type"] = "SLST"
            else:
                if 0<population_df["Sweep"].iloc[0] <=0.5:
                    population_df["Wing_Type"] = "SLTT"
                elif population_df["Sweep"].iloc[0] > 0.5:
                    population_df["Wing_Type"] = "TLTT"

            score,cl,cmy,config,l2d,cost,area = objective(d[:len(bounds_cont)], d[len(bounds_cont):], dataframe,population_df, weights,)
            if cmy>0:#Where score[2] is the Cmy value, if greater than 0, we have an unstable UAV
                score *=0.8
            scores.append(score)
            Cl_vals.append(cl)
            Cmy_vals.append(cmy)
            config_vals.append(config)
            cost_vals.append(cost)
            L2D_vals.append(l2d)
            area_vals.append(area)
        scores_avg.append(np.mean(scores))
        cl_avg.append(np.mean(Cl_vals))
        Config_avg.append(np.mean(config_vals))
        cost_avg.append(np.mean(cost_vals))
        L2D_avg.append(np.mean(L2D_vals))
        area_avg.append(np.mean(area_vals))


        for i in range(n_pop):
            if scores[i] < best_eval:
                best, best_eval = pop[i], scores[i]
                print(f">Gen {gen}, new best f({decoded[i]}) = {scores[i]}")

        #Sorting the scores and indeces for the top_n individuals
        sorted_indeces = sorted(range(len(scores)), key=lambda k: scores[k])[:50]

        #Appending of top 10 individuals to the dataframe
        for idx in sorted_indeces:
            row = decoded[idx] + [scores[idx] ,Cmy_vals[idx], Cl_vals[idx] ,config_vals[idx], ''.join(map(str, pop[idx]))]
            top_n_df= pd.concat([top_n_df, pd.DataFrame([row], columns = top_n_df.columns)] , ignore_index = True) # append row to the dataframedd
            top_n_df = top_n_df.sort_values(by="Scores").head(50) #based on the column heading Scores
        # Select parents
        selected = [selection(pop, scores) for _ in range(n_pop)]

        # Generate the next generation
        """
        We look through the population an select individuals at random and perform 
        crossover and mutation on them
        
        """
        children = []
        for i in range(0, n_pop, 2):
            p1, p2 = selected[i], selected[i + 1]
            for c in crossover(p1, p2, r_cross):# produces two childeren by crossing two parents
                mutation(c, r_mut)# we mutate each chile individually
                children.append(c)


        pop = children  # Replace the population
        iterate += 1
        iterate_vals.append(iterate)

        ##Plotting scores against the iteration
        fig, ax = plt.subplots(3, 2, figsize=(10, 12))
        if isinstance(ax, plt.Axes):
            ax = np.array([[ax]])

        ax[0,0].plot(iterate_vals, scores_avg, label='scores_avg',linestyle='--', marker='o')
        ax[0,0].set_title('scores_avg')

        ax[0,1].plot(iterate_vals, cl_avg, label='cl_avg', color='blue', linestyle='--',marker='^')
        ax[0,1].set_title('cl_avg')

        ax[1,0].plot(iterate_vals, Config_avg, label='Config_avg', color='red', linestyle='--',marker='x')
        ax[1,0].set_title('Config_avg')

        ax[1,1].plot(iterate_vals, cost_avg, label='cost_avg', color='orange',linestyle='--', marker='*')
        ax[1,1].set_title('Cost_avg')

        ax[2,0].plot(iterate_vals, L2D_avg, label='L2D_avg', color='g',linestyle='--', marker='d')
        ax[2,0].set_title('L2D_avg')

        ax[2,1].plot(iterate_vals, area_avg, label='area_avg', color='Brown',linestyle='--', marker='<')
        ax[2,1].set_title('area_avg')

        plt.tight_layout()
        plt.show()


    return best, best_eval, top_n_df



# Parameters, A sample use case
data = {
    "Cost":{"Turbofan":0, "Turboprop":0, "PistonProp":0,"Engine_Number_One":0,"Engine_Number_Two":0,"Engine_Number_Four":0,"Engine_Number_Six":0,"Engine_Number_Eight":0, "Under_Wing":0,"Rear_of_Fuselage":0, "Fuselage_Nose":0,"SLTT":5,"TLTT":5, "TLST":5, "SLST":5, "Delta":5, "Low":5, "Mid":5, "High":5,
         "T_Round":0, "T_Edge":0, "T_Sharp":0,  "N_Round":0, "N_Edge":0, "N_Sharp":0, "Conventional":5, "T-Tail":5, "Cruciform":5, "Dual-Tail":5, "V-Tail":5,
            "Inverted_V-Tail":5, "Y-Tail":5, "Inverted_Y-Tail":5},
    "Weight":{"Turbofan":0, "Turboprop":0, "PistonProp":0,"Engine_Number_One":0,"Engine_Number_Two":0,"Engine_Number_Four":0,"Engine_Number_Six":0,"Engine_Number_Eight":0, "Under_Wing":0,"Rear_of_Fuselage":0, "Fuselage_Nose":0, "SLTT":5, "TLTT":7, "TLST":5, "SLST":1, "Delta":10, "Low":10, "Mid":1, "High":5,
             "T_Round":0, "T_Edge":0, "T_Sharp":0, "N_Round":0, "N_Edge":0, "N_Sharp":0, "Conventional":7, "T-Tail":2, "Cruciform":2, "Dual-Tail":1, "V-Tail":10,
            "Inverted_V-Tail":10, "Y-Tail":5, "Inverted_Y-Tail":5},
}

y_pred = decoded_pred
keys_to_access = y_pred #substitute this with Y pred
for key in keys_to_access:
  if key in data["Cost"]:
    data['Cost'][key] = 10



lookup_discrete_df= pd.DataFrame(data)

#look up values for the bitstring
lookup_discrete_table = {
    "Wing_Type":{"000":"SLST", "001":"SLTT", "010":"TLST", "011":"TLTT", "100":"Delta", "101":"SLST", "110":"TLST","111":"TLTT"},
    "Wing_Position":{"00":"Low", "01":"Mid", "10":"High", "11":"Mid"},
    "Tail_Type":{"000":"Conventional", "001":"T-Tail", "010":"Cruciform", "011":"Y-Tail", "100":"Inverted_Y-Tail", "101":"Dual-Tail", "110":"V-Tail","111":"Inverted_V-Tail"},
    "Fuselage_NoseCap":{"00":"N_Round", "01":"N_Round", "10":"N_Edge", "11":"N_Sharp"},
    "Fuselage_TailCap":{"00":"T_Round", "01":"T_Round", "10":"T_Edge", "11":"T_Sharp"},
    "Engine_Type":{"00":"Turboprop", "01":"Turbofan", "10":"PistonProp", "11":"Turbofan"},
    "Engine_Position":{"00":"Under_Wing", "01":"Fuselage_Nose", "10":"Rear_of_Fuselage", "11":"Under_Wing"},
    "Engine_Number":{"000":"Engine_Number_One","001":"Engine_Number_Two", "010":"Engine_Number_Four", "011":"Engine_Number_Six", "100":"Engine_Number_Eight","101":"Engine_Number_One","110":"Engine_Number_Two", "111":"Engine_Number_Four"}
}


weights = {'wcont': 1, 'wcost': 0.1, 'wweight': 0}
n_bits_cont = 6  # Bits per continuous variable
n_bits_discrete = [3,2,3,2,2,2,2,3]  # Bits per discrete variable
bounds_cont = [Span,power,Taper,Sweep,Vol_Hor,Vol_Vert,Fuse_length,Fuselage_Width_0,Fuselage_Height_0,Fuselage_Width_1,Fuselage_Height_1,Fuselage_Width_2,Fuselage_Height_2,
               Fuselage_Width_3,Fuselage_Height_3,Fuselage_Width_4,Fuselage_Height_4, toptan_0,toptan_1,toptan_2,toptan_3,toptan_4,bottan_0,bottan_1,bottan_2,bottan_3,bottan_4,
               topstr_0 ,topstr_1,topstr_2,topstr_3,topstr_4, botstr_0,botstr_1,botstr_2,botstr_3,botstr_4,]   # Continuous variable bounds
bounds_discret = ["Wing_Type","Wing_Position","Tail_Type","Fuselage_NoseCap", "Fuselage_TailCap",
         "Engine_Type", "Engine_Position", "Engine_Number"]  # Number of discrete variables
n_iter = 100  # Number of generations
n_pop = 100  # Population size
r_cross = 0.75  # Crossover rate
r_mut = 0.05  # Mutation rate

# Run the Genetic Algorithm
start_time = time.time()
best, best_eval,  top_n_df = genetic_algorithm(
    objective, bounds_cont, n_bits_cont, bounds_discret, n_bits_discrete,lookup_discrete_table, lookup_discrete_df,weights,
    n_iter, n_pop, r_cross, r_mut
)

print(f"Best Solution: {best}, Best Objective: {best_eval}")
print(top_n_df)

"""Designer = Master_Designer(top_n_df)
Designer.process_population()
end_time = time.time()

print(f"Execution Time: {end_time - start_time} seconds")

top_n_df.to_csv("Randconfig.csv", index=False)


"""