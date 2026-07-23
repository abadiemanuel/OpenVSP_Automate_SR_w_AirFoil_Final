"""
Experimental values to assume from
"""
friction_coeff = {
    "Brakes_off":{
        "Asphalt_dry_concrete":0.04, "Asphalt_wet_concrete":0.05,"Asphalt_icy_concrete":0.02,
        "Hard_turf":0.05, "Firm_dirt":0.04, "Soft_turf": 0.07, "Wet_Grass":0.08,
    },
    "Brakes_on": {
        "Asphalt_dry_concrete": 0.4, "Asphalt_wet_concrete": 0.2, "Asphalt_icy_concrete": 0.08,
        "Hard_turf": 0.4, "Firm_dirt": 0.3, "Soft_turf": 0.2, "Wet_Grass": 0.2,
    }
}

Cl_max = {
    "Cl_max_avg":{
        "Single_engine_propeller_driven":1.6, "Twin_engine_propeller_driven":1.5, "Fighter":1.5,
        "Supersonic_cruise":2, "Jet_transport":1.5, "Business_jet":1.6
    },
    "Cl_max_to": {
        "Single_engine_propeller_driven": 1.2, "Twin_engine_propeller_driven": 1.7, "Fighter": 1.7,
        "Supersonic_cruise": 1.8, "Jet_transport": 1.9, "Business_jet": 1.9
    },
    "Cl_max_landing": {
        "Single_engine_propeller_driven": 1.45, "Twin_engine_propeller_driven": 2.05, "Fighter": 2.1,
        "Supersonic_cruise": 2, "Jet_transport": 2.3, "Business_jet": 2.1
    }
}

Vol_coeff = {
    "Vol_hor_coeff":{
        "Cessna 172":0.76, "Alenia_G222":0.85, "FOkker_100":1.07, "Lake_LA_250":0.8, "Airbus_340_200":1.11, "Eurofighter_2000":0.063
    }
}