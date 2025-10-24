import os
import glob
import json
import pandas as pd
import folium
from folium import plugins


def extract_values_from_payload(payload):
    """Извлекает координаты и SNR из payload"""
    try:
        if isinstance(payload, str):
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
        else:
            return None, None, None

        lat = data.get("rx lat") or data.get("lat") or data.get("latitude")
        lon = data.get("rx long") or data.get("lon") or data.get("longitude")
        snr = data.get("rx snr") or data.get("snr") or data.get("SNR")

        return float(lat), float(lon), float(snr)
    except Exception:
        return None, None, None


def create_heatmap_layer(csv_file):
    df = pd.read_csv(csv_file)

    # Поддержка CSV с колонками или payload
    if "rx lat" not in df.columns or "rx long" not in df.columns or "rx snr" not in df.columns:
        if "payload" in df.columns:
            df[["rx lat", "rx long", "rx snr"]] = df["payload"].apply(
                lambda x: pd.Series(extract_values_from_payload(x))
            )
        else:
            print(f"⚠️ В файле {csv_file} нет нужных колонок, пропускаю.")
            return None

    df = df.dropna(subset=["rx lat", "rx long", "rx snr"])
    if df.empty:
        print(f"⚠️ В файле {csv_file} нет валидных данных после фильтрации, пропускаю.")
        return None

    # Нормализуем SNR [-21, 12] → [0, 1]
    df["rx snr"] = df["rx snr"].clip(-21, 12)
    df["weight"] = (df["rx snr"] - (-21)) / (12 - (-21))

    heat_points = df[["rx lat", "rx long", "weight"]].values.tolist()

    # 🎨 Градиент Meshtastic: красный → оранжевый → жёлтый → зелёный
    gradient = {
        0.0: "#d7191c",  # плохой (красный)
        0.25: "#fdae61",  # средний (оранжевый)
        0.5: "#ffffbf",  # переход (жёлтый)
        0.75: "#a6d96a",  # хороший
        1.0: "#1a9641",  # отличный (зелёный)
    }

    # 🔥 Более плотная тепловая карта
    layer = plugins.HeatMap(
        heat_points,
        name=os.path.basename(csv_file),
        radius=30,         # было 20 → стало 30 (густее)
        blur=15,           # было 25 → стало 15 (чётче пятна)
        min_opacity=0.6,   # было 0.4 → стало 0.6 (ярче)
        max_zoom=12,
        gradient=gradient,
    )

    layer.data = heat_points
    return layer


def create_map_with_layers(csv_files, output_file):
    valid_layers = []

    for csv_file in csv_files:
        layer = create_heatmap_layer(csv_file)
        if layer:
            valid_layers.append(layer)

    if not valid_layers:
        print("❌ Нет корректных CSV с нужными данными.")
        return

    m = folium.Map(location=[0, 0], zoom_start=2, tiles="OpenStreetMap", control_scale=True)

    all_points = []
    for layer in valid_layers:
        layer.add_to(m)
        all_points.extend(layer.data)

    # Автофокус на данные
    if all_points:
        lats = [p[0] for p in all_points]
        lons = [p[1] for p in all_points]
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

    # === Легенда SNR (старая версия, как раньше) ===
    legend_snr = """
    <div style="
        position: fixed;
        bottom: 25px;
        right: 25px;
        width: 220px;
        background-color: rgba(255,255,255,0.95);
        border-radius: 8px;
        padding: 10px;
        font-size: 13px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        line-height: 1.2;
        z-index:9999;
    ">
        <b>SNR (dB)</b><br>
        <div style="height: 15px; 
                    background: linear-gradient(to right, #d7191c, #fdae61, #ffffbf, #a6d96a, #1a9641);
                    margin: 6px 0;
                    border-radius: 4px;"></div>
        <div style="display: flex; justify-content: space-between;">
            <span>-21 dB</span>
            <span>12 dB</span>
        </div>
    </div>
    """

    # === Легенда Signal Strength (dBm) ===
    legend_dbm = """
    <div style="
        position: fixed;
        bottom: 85px;
        right: 25px;
        width: 220px;
        background-color: rgba(255,255,255,0.95);
        border-radius: 8px;
        padding: 10px;
        font-size: 13px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        line-height: 1.2;
        z-index:9999;
    ">
        <b>Signal Strength (dBm)</b><br>
        <div style="height: 15px; 
                    background: linear-gradient(to right, #d7191c, #fdae61, #ffffbf, #a6d96a, #1a9641);
                    margin: 6px 0;
                    border-radius: 4px;"></div>
        <div style="display: flex; justify-content: space-between;">
            <span>-130 dBm</span>
            <span>-80 dBm</span>
        </div>
    </div>
    """

    m.get_root().html.add_child(folium.Element(legend_dbm))
    m.get_root().html.add_child(folium.Element(legend_snr))

    folium.LayerControl(collapsed=False).add_to(m)
    m.save(output_file)
    print(f"✅ Тепловая карта создана: {output_file}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = glob.glob(os.path.join(script_dir, "*.csv"))

    if not csv_files:
        print("CSV-файлы не найдены. Завершение.")
        exit(1)

    output_file = "rangetest-heatmap.html"
    create_map_with_layers(csv_files, output_file)
    print(f"✅ Тепловая карта сохранена в: {output_file}")
