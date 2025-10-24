import os
import glob
import json
import pandas as pd
import folium
from folium import plugins
from branca.colormap import LinearColormap


def extract_values_from_payload(payload):
    """Пытается вытащить координаты и SNR из поля payload"""
    try:
        if isinstance(payload, str):
            # Иногда payload это строка JSON
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

    # Попробуем извлечь поля из payload, если нужно
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

    # Ограничиваем значения SNR
    df["rx snr"] = df["rx snr"].clip(-21, 12)
    df["weight"] = (df["rx snr"] - (-21)) / (12 - (-21))

    # Формируем точки тепловой карты
    heat_points = df[["rx lat", "rx long", "weight"]].values.tolist()

    # Градиент как в Meshtastic Plasma
    gradient = {
        0.0: "#0d0887",
        0.25: "#6a00a8",
        0.5: "#b12a90",
        0.75: "#e16462",
        1.0: "#fca636",
    }

    layer = plugins.HeatMap(
        heat_points,
        name=os.path.basename(csv_file),
        radius=20,
        blur=25,
        min_opacity=0.4,
        max_zoom=12,
        gradient=gradient,
    )

    # Добавим данные слоя для автоцентровки
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
    else:
        print(f"✅ Найдено {len(valid_layers)} файлов с корректными данными.")

    # Создаем карту (OpenStreetMap по умолчанию)
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="OpenStreetMap", control_scale=True)

    # Добавляем все тепловые слои и собираем все точки
    all_points = []
    for layer in valid_layers:
        layer.add_to(m)
        all_points.extend(layer.data)

    # Автоматический фокус на область с точками
    if all_points:
        lats = [p[0] for p in all_points]
        lons = [p[1] for p in all_points]
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

    # Легенда (SNR)
    colormap = LinearColormap(
        ["#0d0887", "#6a00a8", "#b12a90", "#e16462", "#fca636"],
        vmin=-21,
        vmax=12,
        caption="SNR (dB)"
    )
    colormap.add_to(m)

    # Контрол переключения слоёв
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
