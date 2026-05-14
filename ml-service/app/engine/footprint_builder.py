import pandas as pd
import numpy as np

def build_footprint(df: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """
    Groups tick trades into footprint candles with volume clusters per price.
    df must have index as DatetimeIndex, and columns: [price, size, side]
    where side is 'A' (Ask/Buy) or 'B' (Bid/Sell).
    """
    if df.empty:
        return pd.DataFrame()
        
    # Group by time and price
    # Databento 'action' or 'side' usually contains 'A' or 'B'. 
    # 'size' is the volume traded.
    
    # Let's ensure columns exist
    required = ["price", "size", "side"]
    for col in required:
        if col not in df.columns:
            # Fallback if names are slightly different
            pass

    # For Databento trades schema:
    # side: 'A' -> trade aggressor was Ask (buyer), 'B' -> trade aggressor was Bid (seller)
    # Actually, in Databento: side='A' means ask/sell aggressor, side='B' means bid/buy aggressor in some contexts?
    # Actually standard order flow: 
    # Aggressive Buy hits Ask -> volume added to Ask Volume
    # Aggressive Sell hits Bid -> volume added to Bid Volume
    # We will map 'B' -> bid_volume, 'A' -> ask_volume.
    
    # We'll create a new dataframe with bid_volume and ask_volume columns
    df['bid_volume'] = np.where(df['side'] == 'B', df['size'], 0)
    df['ask_volume'] = np.where(df['side'] == 'A', df['size'], 0)
    
    # Group by candle frequency
    grouper = df.groupby([pd.Grouper(freq=freq), 'price'])
    
    clusters = grouper.agg({
        'bid_volume': 'sum',
        'ask_volume': 'sum',
        'size': 'sum'
    }).rename(columns={'size': 'total_volume'})
    
    clusters['delta'] = clusters['ask_volume'] - clusters['bid_volume']
    
    # Reformat so each row is a time candle, and has a list of clusters
    # We'll reset index
    clusters = clusters.reset_index()
    
    def agg_clusters(x):
        cluster_list = []
        for _, row in x.iterrows():
            cluster_list.append({
                "price": float(row['price']),
                "bid": float(row['bid_volume']),
                "ask": float(row['ask_volume']),
                "delta": float(row['delta']),
                "total": float(row['total_volume'])
            })
        # Calculate candle level OHLC
        # For OHLC, we need original prices
        return cluster_list

    # Calculate OHLC and clusters
    ohlc = df['price'].resample(freq).ohlc()
    ohlc['clusters'] = clusters.groupby('ts_event').apply(agg_clusters)
    ohlc['total_volume'] = df['size'].resample(freq).sum()
    ohlc['candle_delta'] = df['ask_volume'].resample(freq).sum() - df['bid_volume'].resample(freq).sum()
    
    return ohlc.dropna()
