import pandas as pd
import numpy as np
import time

print("Generating 1M rows...")
df = pd.DataFrame({'price': np.random.randn(1000000)})
start = time.time()
print("Calculating rolling median...")
med = df['price'].rolling(11, center=True).median()
print(f"Done in {time.time() - start:.2f} seconds.")
