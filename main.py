import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from tools import tools 
tool = tools()

if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

timeframe = mt5.TIMEFRAME_M1
symbol = "USDJPY"

df = tool.get_historical_data(symbol, timeframe)

df['datetime'] = pd.to_datetime(df['time'], unit='s')
df.insert(0, 'datetime', df.pop('datetime'))

df = tool.create_indicators(df)
df = tool.feature_scaling(df)

tool.save_file(df, symbol, timeframe)

print(df.tail())
print(df.shape)