import pandas as pd
import numpy as np
import random

print("Generating focused synthetic data for scoring service...")

# --- 1. 定义常量和样本数量 ---
N_SAMPLES = 10000

# 用于生成 'is_self_employed' 的职业标题列表
EMP_TITLES = [
    'Software Engineer', 'Project Manager', 'Data Scientist', 'Teacher', 
    'Nurse', 'Marketing Manager', 'self-employed', 'small business owner', 
    'freelance writer', 'consultant'
]
# 用于生成 'is_long_term' 的贷款期限
TERMS = ['36 months', '60 months']
STATES = ['CA', 'NY', 'TX', 'FL', 'IL', 'NJ', 'PA']
EMP_LENGTHS = ['< 1 year', '1 year', '2 years', '3 years', '4 years', '5 years', '6 years', '7 years', '8 years', '9 years', '10+ years']


# --- 2. 生成模型需要的原始特征 ---
# 这是您的模型实际接收的输入的前身
raw_data = {
    'loan_amnt': np.random.randint(1000, 40001, size=N_SAMPLES),
    'term': np.random.choice(TERMS, N_SAMPLES, p=[0.7, 0.3]),
    'int_rate': np.random.uniform(5.0, 25.0, size=N_SAMPLES).round(2),
    'emp_length': np.random.choice(EMP_LENGTHS, N_SAMPLES),
    'annual_inc': np.random.randint(30000, 150001, size=N_SAMPLES),
    'dti': np.random.uniform(5.0, 45.0, size=N_SAMPLES).round(2),
    'addr_state': np.random.choice(STATES, N_SAMPLES),
    # 以下两个特征用于计算派生特征
    'emp_title': np.random.choice(EMP_TITLES, N_SAMPLES, p=[0.15, 0.15, 0.1, 0.1, 0.1, 0.1, 0.05, 0.1, 0.05, 0.1]),
    'issue_d': pd.to_datetime(np.random.choice(pd.date_range(start='2020-01-01', end='2024-12-31'), N_SAMPLES)).strftime('%b-%Y')
}
# 'installment' 可以基于其他值估算，以增加真实感
raw_data['installment'] = (raw_data['loan_amnt'] * (raw_data['int_rate'] / 1200 * (1 + raw_data['int_rate'] / 1200)**36) / ((1 + raw_data['int_rate'] / 1200)**36 - 1)).round(2)

df = pd.DataFrame(raw_data)
print("Generated raw features.")

# --- 3. 根据您的逻辑计算派生特征 ---
print("Computing derived features...")

# credit_to_income_ratio: loan_amnt / annual_inc
df['credit_to_income_ratio'] = (df['loan_amnt'] / df['annual_inc']).round(4)

# is_self_employed: boolean derived from keywords
self_employed_keywords = 'freelance|owner|self-employed|consultant'
df['is_self_employed'] = df['emp_title'].str.contains(self_employed_keywords, case=False, na=False)

# loan_month: month extracted from issue_d
df['loan_month'] = pd.to_datetime(df['issue_d']).dt.month

# is_long_term: true if term is ≥ 36 months
# 注意：您的逻辑是 '≥ 36 months'，而常见选项是'36 months'和'60 months'，所以这里所有贷款都是 long_term。
# 如果想让其有变化，可以将逻辑改为 term == '60 months'
# 我们暂时遵循您给出的 '>=36' 逻辑
df['is_long_term'] = df['term'].str.extract(r'(\d+)').astype(int) >= 36


# --- 4. 准备最终的输出文件 ---
# 选取您指定的最终特征列
final_columns = [
    'loan_amnt', 'term', 'int_rate', 'installment', 'emp_length',
    'annual_inc', 'dti', 'addr_state', 'credit_to_income_ratio',
    'is_self_employed', 'loan_month', 'is_long_term'
]
final_df = df[final_columns]

# 保存为CSV文件
output_path = 'scoring_features_synthetic.csv'
final_df.to_csv(output_path, index=False)

print(f"\nFinal dataset with {len(final_columns)} features for scoring saved to {output_path}")
print("First 5 rows of the generated data:")
print(final_df.head())