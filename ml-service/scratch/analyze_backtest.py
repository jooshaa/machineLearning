import pandas as pd
import numpy as np
from datetime import datetime

# Load the CSV
csv_path = "/Users/asal/Desktop/volume_delta_dataset.csv"
df = pd.read_csv(csv_path)

print(f"Total signals: {len(df)}")

# Calculate R:R
# For Buy: Risk = entry - stop, Reward = target - entry
# For Sell: Risk = stop - entry, Reward = entry - target
# Since we only have 'buy' in the sample data shown (let's check if there are sells)
print(f"Directions found: {df['direction'].unique()}")

df['risk'] = np.abs(df['entry'] - df['stop'])
df['reward'] = np.abs(df['target'] - df['entry'])
df['rr'] = df['reward'] / df['risk']

print(f"Average R:R: {df['rr'].mean():.2f}")

# Group by direction
direction_counts = df['direction'].value_counts()
print("\nSignals by direction:")
print(direction_counts)

# Group by session
# Convert ts to datetime
df['ts'] = pd.to_datetime(df['ts'])

def get_session(dt):
    hour = dt.hour
    if 0 <= hour < 8:
        return 'Asia'
    elif 8 <= hour < 16:
        return 'London'
    else:
        return 'New York'

df['session'] = df['ts'].apply(get_session)
session_counts = df['session'].value_counts()
print("\nSignals by session:")
print(session_counts)

# Check for result column
if 'result' in df.columns:
    print("\nResult column exists!")
    # Calculate win rate
    win_rate = (df['result'] == 'win').mean()
    print(f"Win rate: {win_rate:.2f}")
else:
    print("\nNo 'result' column exists in the dataset.")
    print("Cannot calculate win rate, correlate features with wins, or plot equity curve without trade outcomes.")

# Print available features
features = ['score', 'layering']
print("\nAvailable features in dataset:")
print(df[features].describe())
