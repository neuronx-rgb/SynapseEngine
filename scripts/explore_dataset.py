import pandas as pd, sys, os
os.chdir(r'D:\Storm')
df = pd.read_excel('datasets/Cornelius_FR_NFR_Curated_Mendeley_Dataset_2025.xlsx', sheet_name='Complete_Dataset')
print('Shape:', df.shape)
print('Columns:', list(df.columns))
print('Projects:', sorted(df['Project_Name'].unique()))
print('Total projects:', df['Project_Name'].nunique())
print()
print('Req Types:', df['Requirement_Type'].value_counts().to_dict())
print('NFR cats (top10):', df['NFR_Category'].dropna().value_counts().head(10).to_dict())
print()
print('Sample descriptions:')
for i, r in df.head(5).iterrows():
    print(f"  [{r['Requirement_Type']}] {str(r['Description'])[:80]}")
print()
# check for duplicates and vague terms
vague = df['Description'].str.contains(r'user.?friendly|intuitive|easy', case=False, na=False)
print(f'Vague terms: {vague.sum()} rows')
dup = df.duplicated(subset=['Project_Name','Description'])
print(f'Exact duplicate descriptions: {dup.sum()} rows')
# check metric templates
import re
metric_pat = re.compile(r'(\d+(?:\.\d+)?)\s*(?:second|concurrent|uptime|backup)', re.I)
print('Metric mentions:', df['Description'].str.contains(metric_pat, regex=True).sum())
