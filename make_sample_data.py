from sklearn.datasets import fetch_openml

data = fetch_openml("adult", version=2, as_frame=True)
df = data.frame.sample(5000, random_state=0)
df.to_csv("sample_data/adult_sample.csv", index=False)
print(df.shape)
print(df.columns.tolist())