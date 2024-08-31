import os
import sys
import time
import subprocess
import pandas as pd
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt

from IPython.display import display, clear_output
from datetime import datetime, timedelta
from enum import Enum

class TimeFrame(Enum):
    M1  = mt5.TIMEFRAME_M1
    M2  = mt5.TIMEFRAME_M2
    M3  = mt5.TIMEFRAME_M3
    M4  = mt5.TIMEFRAME_M4
    M5  = mt5.TIMEFRAME_M5
    M6  = mt5.TIMEFRAME_M6
    M10 = mt5.TIMEFRAME_M10
    M12 = mt5.TIMEFRAME_M12
    M15 = mt5.TIMEFRAME_M15
    M20 = mt5.TIMEFRAME_M20
    M30 = mt5.TIMEFRAME_M30
    H1  = mt5.TIMEFRAME_H1
    H2  = mt5.TIMEFRAME_H2
    H3  = mt5.TIMEFRAME_H3
    H4  = mt5.TIMEFRAME_H4
    H6  = mt5.TIMEFRAME_H6
    H8  = mt5.TIMEFRAME_H8
    H12 = mt5.TIMEFRAME_H12
    D1  = mt5.TIMEFRAME_D1
    W1  = mt5.TIMEFRAME_W1 
    MN1 = mt5.TIMEFRAME_MN1 

class tools:
  def __init__(self):
    pass 
  
  def get_historical_data(self, symbol, timeframe):
    darray =  self.get_server_data(symbol, timeframe)
    new_df = pd.DataFrame(darray)

    file_name =  f"historical-candles/{symbol}-{TimeFrame(timeframe).name}.csv".lower()

    if os.path.isfile(file_name):
      old_df = pd.read_csv(file_name)
      last_time = old_df.iloc[-1, 0]
      diff_df = new_df[new_df.time > last_time]
      new_df = pd.concat([old_df, diff_df])
        
      new_df.to_csv(file_name, index = False)

      return new_df
  

























