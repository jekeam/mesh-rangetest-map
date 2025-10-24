import os
import pandas as pd
import folium
from folium.plugins import HeatMap
from branca.element import Template, MacroElement


def create_heatmap(csv_files, output_html="rangetest-heatmap.html"):
    all_data = []

    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"⚠️ Файл {csv_file} не найден, пропускаю.")
            continue

        df = pd.read_csv(csv_file)
        cols = [c.lower().strip() for c in df.columns]
        df.columns = cols

        lat_col = next((c for c in cols if "lat" in c), None)
        lon_col = next((c for c in cols if "lon" in c or "lng" in c), None)
        rssi_col = next((c for c in cols if "rssi" in c or "dbm" in c), None)
        snr_col = next((c for c in cols if "snr" in c), None)

        if not lat_col or not lon_col:
            print(f"⚠️ В файле {csv_file} нет координатных колонок, пропускаю.")
            continue

        df = df.dropna(subset=[lat_col, lon_col])
        if len(df) == 0:
            continue

        print(f"✅ Загружен {csv_file} ({len(df)} строк)")
        all_data.append((df, lat_col, lon_col, rssi_col, snr_col))

    if not all_data:
        print("❌ Нет корректных CSV с нужными данными.")
        return

    first_df, lat_col, lon_col, *_ = all_data[0]
    m = folium.Map(location=[first_df[lat_col].mean(), first_df[lon_col].mean()],
                   zoom_start=13, tiles="OpenStreetMap", control_scale=True)

    # --- Добавляем все карты (как раньше) ---
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri",
        name="Esri WorldImagery"
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr='Map data © OpenStreetMap contributors, SRTM | Style © OpenTopoMap (CC-BY-SA)',
        name="OpenTopoMap"
    ).add_to(m)

    folium.TileLayer("CartoDB positron", name="CartoDB Light").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="CartoDB Dark").add_to(m)

    # --- Добавляем тепловые карты ---
    for df, lat_col, lon_col, rssi_col, snr_col in all_data:
        # RSSI
        if rssi_col:
            heat_data_rssi = [
                [row[lat_col], row[lon_col], max(0, min(1, (row[rssi_col] + 130) / 50))]
                for _, row in df.iterrows() if not pd.isna(row[rssi_col])
            ]
            if heat_data_rssi:
                HeatMap(
                    heat_data_rssi,
                    name=f"RSSI Heatmap ({os.path.basename(csv_file)})",
                    radius=30,
                    blur=10,
                    min_opacity=0.4,
                    gradient={0.0: 'blue', 0.5: 'lime', 0.75: 'yellow', 1.0: 'red'}
                ).add_to(m)

        # SNR
        if snr_col:
            heat_data_snr = [
                [row[lat_col], row[lon_col], max(0, min(1, (row[snr_col] + 20) / 40))]
                for _, row in df.iterrows() if not pd.isna(row[snr_col])
            ]
            if heat_data_snr:
                HeatMap(
                    heat_data_snr,
                    name=f"SNR Heatmap ({os.path.basename(csv_file)})",
                    radius=30,
                    blur=10,
                    min_opacity=0.4,
                    gradient={0.0: 'purple', 0.3: 'blue', 0.6: 'lime', 1.0: 'yellow'}
                ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # --- Легенда сверху ---
    legend_html = """
    {% macro html(this=None, kwargs=None) %}
    <div style="
        position: fixed;
        top: 10px; left: 50%;
        transform: translateX(-50%);
        width: 320px;
        background: rgba(255, 255, 255, 0.92);
        border-radius: 10px;
        padding: 10px;
        font-size: 13px;
        z-index: 9999;
        box-shadow: 0 0 10px rgba(0,0,0,0.3);
    ">
        <b>📶 RSSI (dBm)</b><br>
        <div style="height:10px;background:linear-gradient(to right, blue, lime, yellow, red);margin:5px 0;"></div>
        <span style="float:left;">−130</span><span style="float:right;">−80</span><br style="clear:both;">
        <b>📡 SNR (dB)</b><br>
        <div style="height:10px;background:linear-gradient(to right, purple, blue, lime, yellow);margin:5px 0;"></div>
        <span style="float:left;">−20</span><span style="float:right;">+20</span>
    </div>
    {% endmacro %}
    """
    macro = MacroElement()
    macro._template = Template(legend_html)
    m.get_root().add_child(macro)

    m.save(output_html)
    print(f"✅ Тепловая карта создана: {output_html}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = [os.path.join(script_dir, f) for f in os.listdir(script_dir) if f.endswith(".csv")]
    if not csv_files:
        print("❌ CSV не найдены.")
    else:
        create_heatmap(csv_files)

