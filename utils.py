import numpy as np

#def get_data(file:str, skiprows=18, oscilloscope_model=None):
    #oscilloscope saves data as csv file
    #data = np.loadtxt(file, delimiter=',', skiprows=skiprows, usecols= [3,4])
    #return data[:, 0], data[:,1]


def get_data(file:str, skiprows=1):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows)
    return data[:, 0], data[:,1]