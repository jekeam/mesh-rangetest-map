import os
import glob
import pandas as pd
import folium
from folium import plugins
from folium.plugins import HeatMap, MeasureControl


def create_heatmap_layer(csv_file):
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"⚠️ Не удалось прочитать {csv_file}: {e}")
        return None

    # Фильтрация
    if "payload" not in df.columns:
        print(f"⚠️ В {csv_file} нет колонки 'payload' — пропускаем.")
        return None

    df_filtered = df[df["payload"].str.contains(r"seq \d+", na=False)]
    required_cols = ["rx lat", "rx long", "rx snr"]
    if not all(col in df_filtered.columns for col in required_cols):
        print(f"⚠️ В {csv_file} не хватает колонок {required_cols} — пропускаем.")
        return None

    df_filtered = df_filtered[required_cols].dropna()
    df_filtered = df_filtered[
        (df_filtered["rx lat"].apply(lambda x: isinstance(x, (int, float))))
        & (df_filtered["rx long"].apply(lambda x: isinstance(x, (int, float))))
        & (df_filtered["rx lat"].between(-90, 90))
        & (df_filtered["rx long"].between(-180, 180))
        & (df_filtered["rx snr"].apply(lambda x: isinstance(x, (int, float))))
    ]

    if df_filtered.empty:
        print(f"❌ В {csv_file} нет валидных данных.")
        return None

    # Собираем данные для heatmap
    heat_data = []
    for _, row in df_filtered.iterrows():
        snr = float(row["rx snr"])
        lat = float(row["rx lat"])
        lon = float(row["rx long"])

        # Нормализуем SNR: чем выше SNR — тем выше вес
        weight = max(0.0, min(1.0, (snr + 21.0) / 33.0))
        heat_data.append([lat, lon, weight])

    if not heat_data:
        return None

    # Создаём FeatureGroup
    layer_name = os.path.basename(csv_file).replace(".csv", "")
    fg = folium.FeatureGroup(name=layer_name)

    # Добавляем heatmap
    HeatMap(heat_data, radius=20, blur=10, min_opacity=0.4, max_val=1.0).add_to(fg)

    return fg


def add_snr_legend(m):
    # Создаём HTML-легенду
    legend_html = """
    <div style="
        position: fixed; 
        bottom: 50px; 
        right: 10px; 
        z-index: 999; 
        background-color: white; 
        padding: 10px; 
        border: 2px solid grey;
        border-radius: 5px;
        font-family: Arial, sans-serif;
        font-size: 12px;
        box-shadow: 0 0 10px rgba(0,0,0,0.5);
        ">
        <b>SNR (dB)</b><br>
        <div style="display: block;">
            <div style="width: auto; height: 15px; background: linear-gradient(to right, red, yellow, green);"></div>
            <div style="margin-top: 5px; display: flex; justify-content: space-between; width: auto; font-size: 10px;">
                <span>-21</span>
                <span>-13</span>
                <span>-5</span>
                <span>4</span>
                <span>12</span>
            </div>
        </div>
        <div style="font-size: 10px; margin-top: 5px;">
            <i>Примечание: На карте "горячие" области (красно-жёлтые) = высокий SNR (хороший сигнал).</i>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = glob.glob(os.path.join(script_dir, "*.csv"))

    if not csv_files:
        print("❌ Нет CSV-файлов в папке. Положите сюда результаты тестов.")
        return

    print(f"📁 Найдено {len(csv_files)} CSV-файлов. Обработка...")

    # Базовая карта
    first_df = pd.read_csv(csv_files[0])
    first_df_filtered = first_df[first_df["payload"].str.contains(r"seq \d+", na=False)]
    first_df_filtered = first_df_filtered[["rx lat", "rx long"]].dropna()
    first_df_filtered = first_df_filtered[
        (first_df_filtered["rx lat"].apply(lambda x: isinstance(x, (int, float))))
        & (first_df_filtered["rx long"].apply(lambda x: isinstance(x, (int, float))))
        & (first_df_filtered["rx lat"].between(-90, 90))
        & (first_df_filtered["rx long"].between(-180, 180))
    ]
    if not first_df_filtered.empty:
        center_lat = first_df_filtered["rx lat"].mean()
        center_lon = first_df_filtered["rx long"].mean()
    else:
        center_lat, center_lon = 0, 0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="OpenStreetMap", control_scale=True)

    # Measure Tool
    m.add_child(
        MeasureControl(
            primary_length_unit="meters",
            secondary_length_unit="miles",
        )
    )



    # Добавляем базовые слои
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
        name="Esri WorldImagery",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors,'
        '<a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> '
        '(<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
        name="OpenTopoMap",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="Map tiles by CartoDB, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
        name="CartoDB Positron",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}{r}.png",
        attr="Map tiles by CartoDB, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
        name="CartoDB Positron (No Labels)",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}{r}.png",
        attr="Map tiles by CartoDB, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
        name="CartoDB Dark Matter (No Labels)",
        show=False,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="Map tiles by CartoDB, under CC BY 3.0. Data by OpenStreetMap, under ODbL.",
        name="CartoDB Dark Matter",
        show=False,
    ).add_to(m)

    # Добавляем слои для каждого CSV
    for csv_file in csv_files:
        layer = create_heatmap_layer(csv_file)
        if layer:
            layer.add_to(m)

    # Добавляем легенду
    add_snr_legend(m)

    # Управление слоями
    folium.LayerControl(collapsed=False).add_to(m)

    output_file = "rangetest-map.html"
    m.save(output_file)
    print(f"✅ Готово! Откройте '{output_file}' в браузере.")


if __name__ == "__main__":
    main()
