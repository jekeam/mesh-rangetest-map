import os
import glob
import pandas as pd
import folium
from folium.plugins import HeatMap
from branca.colormap import LinearColormap


def detect_column(df, keywords):
    """Ищет колонку по ключевым словам"""
    for col in df.columns:
        low = col.strip().lower().replace("_", "").replace(" ", "")
        for kw in keywords:
            if kw in low:
                return col
    return None


def create_heat_layer(df, lat_col, lon_col, value_col, name, gradient):
    df = df.dropna(subset=[lat_col, lon_col, value_col])

    # Нормализация значений в [0, 1]
    values = df[value_col].astype(float)
    norm = (values - values.min()) / (values.max() - values.min())
    heat_data = [
        [df.iloc[i][lat_col], df.iloc[i][lon_col], norm.iloc[i]]
        for i in range(len(df))
    ]

    return HeatMap(
        heat_data,
        name=name,
        min_opacity=0.4,
        radius=22,     # плотнее точки
        blur=28,
        max_zoom=12,
        gradient=gradient,
    )


def create_map_with_layers(csv_files, output_file):
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="OpenStreetMap")

    snr_gradient = {
        0.0: "#ff0000",  # красный
        0.5: "#ffff00",  # жёлтый
        1.0: "#00ff00",  # зелёный
    }

    dbm_gradient = {
        0.0: "#8000ff",
        0.25: "#ff00ff",
        0.5: "#ff8000",
        0.75: "#ffff00",
        1.0: "#ffffff",
    }

    valid_layers = []
    all_points = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            print(f"❌ Ошибка чтения {csv_file}: {e}")
            continue

        lat_col = detect_column(df, ["lat", "latitude", "rxlat"])
        lon_col = detect_column(df, ["lon", "long", "lng", "longitude", "rxlong"])
        snr_col = detect_column(df, ["snr"])
        rssi_col = detect_column(df, ["rssi", "signal", "dbm"])

        if not lat_col or not lon_col:
            print(f"⚠️ В файле {csv_file} не найдены координаты, пропускаю.")
            continue

        if snr_col:
            snr_layer = create_heat_layer(df, lat_col, lon_col, snr_col,
                                          f"SNR — {os.path.basename(csv_file)}", snr_gradient)
            snr_layer.add_to(m)
            valid_layers.append(snr_layer)

        if rssi_col:
            dbm_layer = create_heat_layer(df, lat_col, lon_col, rssi_col,
                                          f"RSSI — {os.path.basename(csv_file)}", dbm_gradient)
            dbm_layer.add_to(m)
            valid_layers.append(dbm_layer)

        all_points.extend(df[[lat_col, lon_col]].dropna().values.tolist())

    if not valid_layers:
        print("❌ Нет корректных CSV с нужными данными.")
    else:
        # Автоматический центр по точкам
        if all_points:
            lats = [p[0] for p in all_points]
            lons = [p[1] for p in all_points]
            m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

        # Легенды
        snr_colormap = LinearColormap(['red', 'yellow', 'green'], vmin=-21, vmax=12)
        snr_colormap.caption = 'SNR (дБ)'
        snr_colormap.add_to(m)

        dbm_colormap = LinearColormap(
            ['#8000ff', '#ff00ff', '#ff8000', '#ffff00', '#ffffff'],
            vmin=-130, vmax=-80
        )
        dbm_colormap.caption = 'RSSI (dBm)'
        dbm_colormap.add_to(m)

        # Позиции легенд
        m.get_root().html.add_child(folium.Element("""
        <style>
        .leaflet-control.branca.colormap:first-of-type {
            top: 10px !important;
            right: 10px !important;
            bottom: auto !important;
            width: 220px !important;
        }
        .leaflet-control.branca.colormap:last-of-type {
            bottom: 10px !important;
            right: 10px !important;
            width: 220px !important;
        }
        </style>
        """))

        folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_file)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = glob.glob(os.path.join(script_dir, "*.csv"))

    if not csv_files:
        print("❌ CSV-файлы не найдены.")
        exit(1)

    output_file = "rangetest-heatmap.html"
    create_map_with_layers(csv_files, output_file)
    print(f"✅ Тепловая карта создана: {output_file}")
