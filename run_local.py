from analysis_engine import run_analysis

DATA_DIR = "/Users/asif/Documents/Data_and_Analytics/sample_data"
OUT_DIR = "/Users/asif/Documents/Data_and_Analytics/outputs"

result = run_analysis(
    DATA_DIR,
    OUT_DIR,
    start_date="2024-01-01",
    end_date="2024-05-28"
)

print(result)
