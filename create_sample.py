import pandas as pd

# --- 配置 ---
# 指向您巨大的原始数据文件
SOURCE_FILE = r'C:\Users\Lenovo\natwest\Loan-Risk-Evaluator\loan.csv'

# 我们要创建的样本文件名
SAMPLE_FILE = 'loan_sample_10k.csv'

# 定义样本大小
SAMPLE_SIZE = 10000 

print(f"Loading full dataset from {SOURCE_FILE}...")
print("This may take a moment for a large file...")

try:
    # 尝试一次性加载。如果您的内存足够大，这是最简单的方法。
    df_full = pd.read_csv(SOURCE_FILE)
    print(f"Full dataset loaded with {len(df_full)} rows.")

    # --- 进行随机采样 ---
    # random_state=42 保证了您每次运行脚本得到的样本都是完全一样的，便于复现
    print(f"Creating a random sample of {SAMPLE_SIZE} rows...")
    df_sample = df_full.sample(n=SAMPLE_SIZE, random_state=42)

    # --- 保存样本文件 ---
    df_sample.to_csv(SAMPLE_FILE, index=False)
    print(f"Sample file '{SAMPLE_FILE}' with {len(df_sample)} rows has been created successfully.")

except MemoryError:
    print("\nMemoryError encountered. The file is too large to load into memory at once.")
    print("Consider using more advanced techniques like chunking if needed for other tasks.")
    print("For a one-off sample, you can also use command-line tools if available.")
    print("Example (Linux/macOS): shuf -n 10000 path/to/your/loan.csv > loan_sample_10k.csv")
except Exception as e:
    print(f"An error occurred: {e}")