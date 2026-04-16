import os
import json
import pandas as pd

def new_q():
    folder = 'questions'
    answer_folder = 'answers'
    data_folder = 'data_ans'
    result = []

    files = sorted([
        f for f in os.listdir(folder)
        if f.startswith('plot') and f.endswith('.png') and f[4:-4].isdigit() and int(f[4:-4]) >= 100
    ])

    for filename in files:
        p = filename[4:-4]
        csv_path = os.path.join(data_folder, f'data{p}.csv')
        direction = None

        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if not df.empty and 'open' in df.columns and 'close' in df.columns:
                open_price = df['open'].iloc[0]
                close_price = df['close'].iloc[-1]
                direction = bool(close_price > open_price)

        result.append({
            "file": filename,
            "up": direction,
            'fact_1' : 'none',
            'fact_2': 'none',
            'fact_3': 'none',
            'ans': 'none'
        })

    with open(os.path.join(folder, 'list.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    new_q()