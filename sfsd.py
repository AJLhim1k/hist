import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import random
from datetime import datetime, timedelta
import zipfile

# --- Настройки ---
NUM_CHARTS = 30
START_NUMBER = 411
OUTPUT_DIR = "spoofing_charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Генерация данных спуфинга ---
def generate_layering_dataframe(base_price, direction, start_time):
    steps = [0, 2, 4]
    time_labels = [(start_time + timedelta(minutes=m)).strftime("%H:%M") for m in steps]
    frames = []

    for i, time_label in enumerate(time_labels):
        price_shift = direction * i * random.uniform(1.0, 1.5) if i > 0 else 0
        center = base_price + price_shift
        prices_sell = [round(center + j * 0.5, 2) for j in range(10, 0, -1)]
        prices_buy = [round(center - j * 0.5, 2) for j in range(10)]

        rows = []
        for price in prices_sell:
            qty = np.random.randint(10, 1000)
            rows.append([time_label, "Продажа", price, qty])
        for price in prices_buy:
            qty = np.random.randint(10, 1000)
            rows.append([time_label, "Покупка", price, qty])

        df = pd.DataFrame(rows, columns=["Время", "Тип", "Цена", "Количество"])

        # Лэйеринг на втором стакане
        if i == 1:
            layer_side = random.choice(["Покупка", "Продажа"])
            layer_prices = df[(df["Время"] == time_label) & (df["Тип"] == layer_side)]["Цена"].unique()
            layer_levels = sorted(random.sample(list(layer_prices), k=3))  # 3 уровня

            for price in layer_levels:
                idxs = df[(df["Время"] == time_label) & (df["Тип"] == layer_side) & (df["Цена"] == price)].index
                if not idxs.empty:
                    df.loc[idxs, "Количество"] *= 1

        frames.append(df)

    return pd.concat(frames, ignore_index=True)

# --- Построение графика ---
def plot_spoofing_chart(df, filename):
    time_points = sorted(df["Время"].unique())
    fig, axes = plt.subplots(1, 3, figsize=(18, 9), sharey=True)

    for i, time in enumerate(time_points):
        ax = axes[i]
        snap = df[df["Время"] == time]
        bid = snap[snap["Тип"] == "Покупка"].sort_values("Цена")
        ask = snap[snap["Тип"] == "Продажа"].sort_values("Цена")

        ax.barh(bid["Цена"], bid["Количество"], color="#2dd242")
        ax.barh(ask["Цена"], -ask["Количество"], color="red")

        ax.set_title(time, fontsize=16)
        ax.set_xlabel("Объём заявок", fontsize=14)
        ax.axvline(0, color='gray', linewidth=0.5)
        ax.grid(True, axis='x', linestyle='--', alpha=0.3)
        ax.tick_params(labelsize=12)
        xt = ax.get_xticks()
        ax.set_xticks(xt)  # Явно зафиксируем текущие тики
        ax.set_xticklabels([str(abs(int(t))) for t in xt])

    axes[0].set_ylabel("Цена", fontsize=14)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

# --- Генерация графиков и архива ---
base_time = datetime.strptime("10:00", "%H:%M")
for i in range(NUM_CHARTS):
    price = round(random.uniform(100, 10000), 2)
    direction = random.choice([-1, 1])
    t0 = base_time + timedelta(minutes=random.randint(0, 600))
    df = generate_layering_dataframe(price, direction, t0)
    number = START_NUMBER + i
    filepath = os.path.join(OUTPUT_DIR, f"plot{number}.png")
    plot_spoofing_chart(df, filepath)

# --- Упаковка в zip ---
with zipfile.ZipFile("spoofing_charts.zip", "w") as zipf:
    for fname in os.listdir(OUTPUT_DIR):
        zipf.write(os.path.join(OUTPUT_DIR, fname), fname)

print("✅ Архив spoofing_charts.zip успешно создан с именами data351–data381.")
