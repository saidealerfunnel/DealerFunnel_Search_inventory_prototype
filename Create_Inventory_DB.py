import pandas as pd
import sqlite3
df = pd.read_csv('Sample_Inventory_file.csv')
conn = sqlite3.connect('Inventory.db')
df.to_sql('vehicles', conn, if_exists='replace', index=False)
