import os
import pytz
import numpy as np
import pandas as pd
import MetaTrader5 as mt5
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

    def calculate_next_time(self, rates):
        current_time = rates[0][0]
        previous_time = rates[1][0]
        time_difference = previous_time - current_time
        return int(current_time - time_difference)
    
    def get_server_data(self, symbol, timeframe):    

        next_time = datetime.now(pytz.utc) + timedelta(days = 2)       
        darray = None 

        while True:            
            rates = mt5.copy_rates_from(symbol, timeframe, next_time, 999)
            error_code = mt5.last_error()[0]

            if error_code < 0:                    
                print(mt5.last_error())
                break                
            
            if darray is None:
                darray = rates
            else:
                darray = np.concatenate((rates, darray), axis=0)
            
            next_time = self.calculate_next_time(rates)

            if rates.shape[0] < 999:
                break

        return darray    
  
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
  

#-----------------------------indicators--------------------------

    def create_indicators(self, df):
        df["wma_5"] = self.wma(df.close, 5)
        df["wma_10"] = self.wma(df.close, 10)
        df["wma_20"] = self.wma(df.close, 20)
        df["macd_line"], df["macd_signal"], df["macd_histogram"] = self.macd(df.close)
        df["rsi"] = self.rsi(df.close)
        df["k"], df["d"] = self.kd(df)
        df["bias_6"] = self.bias(df.close, 6)
        df["bias_12"] = self.bias(df.close, 12)
        df["bias_24"] = self.bias(df.close, 24)
        df["upper_band"], df["lower_band"]= self.bollinger_bands(df.close)
        df["atr"] = self.atr(df)
   
        print(f"Feature Engineering: {df.shape}")
        
        return df

    def sma(self, data, window):
        return data.rolling(window).mean()
  
    def ema(self, data, span):
        return data.ewm(span=span, adjust=False).mean()  

    def wma(self, data, window):
        weights = np.arange(1, window + 1)
        wma = data.rolling(window).apply(lambda prices: np.dot(prices, weights) / weights.sum(), raw=True)
        return wma
    
    def macd(self, data, short_window=12, long_window=26, signal_window=9):
        short_ema = self.ema(data, short_window)
        long_ema = self.ema(data, long_window)
        macd_line = short_ema - long_ema
        signal_line = self.ema(macd_line, signal_window)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def rsi(self, data, window = 14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def kd(self, data, period=14):
        low = data.low.rolling(window=period).min()
        high = data.high.rolling(window=period).max()
        k = 100 * ((data.close - low) / (high - low))
        d = k.rolling(window=3).mean()
        return k, d
        
    def bias(self, data, window):
        ma = self.sma(data, window)
        return ((data - ma) / ma) * 100

    def bollinger_bands(self, data, window = 20, num_std = 2):
        mean = data.rolling(window = window).mean()
        std = data.rolling(window = window).std()
        upper_band = mean + (std * num_std)
        lower_band = mean - (std * num_std)
        return upper_band, lower_band
    
    def atr(self, data, window = 14):

       # (True Range, TR)
        tr = np.maximum(data.high - data.low, np.maximum(abs(data.high - data.close.shift(1)), abs(data.low - data.close.shift(1))))
        atr = tr.rolling(window=window, min_periods=1).mean()
        return atr
        
# ----------------------------------Feature Scaling--------------------------------------------

    def feature_scaling(self, data):
        max_val = data[['open', 'high', 'low', 'close']].max().max()
        min_val = data[['open', 'high', 'low', 'close']].min().min()

        for col in ['open', 'high', 'low', 'close', 'wma_5', 'wma_10','wma_20', 'upper_band', 'lower_band']:            
            data[f"scaled_{col}"] = np.round((data[[col]] - min_val) / (max_val - min_val), 6)

        for col in ["tick_volume", "spread", "atr"]:
            data[f"scaled_{col}"] =  np.round((data[[col]] - data[[col]].min()) / (data[[col]].max() - data[[col]].min()), 6)

        for col in ["rsi", "k", "d", "bias_6", "bias_12", "bias_24"]:
            data[f"scaled_{col}"] = np.round((data[[col]] / 100), 6)

        for col in ["macd_line", "macd_signal", "macd_histogram"]:
            data[f"scaled_{col}"] = np.round(data[[col]], 6)
  
        return data
    
# -------------------------------save scaling data--------------------------------------------
    def save_file(self, data, symbol, timeframe):
        file_name = f"scaled_data/{symbol}-{TimeFrame(timeframe).name}-scaled.csv".lower()
        data.to_csv(file_name, index = False)
        
