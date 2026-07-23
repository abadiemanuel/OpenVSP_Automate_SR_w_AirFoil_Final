
import joblib
from Sizing import *
from joblib import Parallel, delayed
"""
Where the ML model is used to predict the configurationss
"""

clf = joblib.load('RandomForestClassifier.pkl')
le = joblib.load('labelencoder.pkl')
DT_input = [(inputs['payload']*g)/Mto, (Vmax*g)/Mto, (inputs['cruise_speed']*g)/Mto, (inputs['Range']*g)/Mto, (Endurance*g)/Mto, (inputs['cruise_ceiling']*g)/Mto]
pred = clf.predict([DT_input])
#



decoded_pred = [le[col].inverse_transform([pred[0][i]])[0] for i, col in enumerate(le.keys())]
print(decoded_pred)

