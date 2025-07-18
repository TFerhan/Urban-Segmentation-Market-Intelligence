from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField
from qgis.PyQt.QtCore import QVariant
import requests
import pandas as pd
from PyQt5.QtWidgets import QInputDialog
from datetime import datetime

project = QgsProject.instance()
crs = project.crs()

datetime_str = datetime.now().strftime("%Y%m%d_%H%M")

if crs.authid() != "EPSG:4326":
    raise Exception("Project CRS must be EPSG:4326 (WGS 84). Please set the correct CRS and re-run.")


canvas = iface.mapCanvas()
extent = canvas.extent()

bottom_left = f"{extent.yMinimum()},{extent.xMinimum()}"
top_right = f"{extent.yMaximum()},{extent.xMaximum()}"


api_key, ok = QInputDialog.getText(None, "API Key", "Enter your Waze API Key:")
if not ok or not api_key:
    raise Exception("API key is required!")


def get_raw_jams_from_waze(api_key, bottom_left, top_right):
    url = "https://waze.p.rapidapi.com/alerts-and-jams"
    querystring = {
        "bottom_left": bottom_left,
        "top_right": top_right,
        "max_alerts": "100",
        "max_jams": "10000"
    }
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "waze.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raises HTTPError for bad status codes
        data = response.json()
        jams = data.get("data", {}).get("jams", [])
        return jams
    except requests.exceptions.HTTPError as http_err:
        msg = f"HTTP Error {response.status_code}: {response.text}"
        raise Exception(f"API request failed – {msg}")
    except requests.exceptions.RequestException as req_err:
        raise Exception(f"Network error: {req_err}")
    except Exception as err:
        raise Exception(f"Unexpected error: {err}")

def coords_to_wkt_line(coords):
    if isinstance(coords, str):
        return coords
    points = ", ".join(f"{pt['lon']} {pt['lat']}" for pt in coords)
    return f"LINESTRING({points})"


def jams_to_csv(jams, filename):
    columns = ['jam_id', 'type', 'level', 'severity', 'line_coordinates', 'start_location', 'end_location',
               'speed_kmh', 'length_meters', 'delay_seconds', 'block_alert_id', 'block_alert_type',
               'block_alert_description', 'block_alert_update_datetime_utc', 'block_start_datetime_utc',
               'publish_datetime_utc', 'update_datetime_utc', 'country', 'city', 'street']
    data = []

    for jam in jams:
        jam["line_coordinates"] = coords_to_wkt_line(jam.get("line_coordinates", []))
        data.append(jam)

    df = pd.DataFrame(data, columns=columns)
    df.to_csv(filename, index=False)
    return df



def display_jams_layer(df):
    vl = QgsVectorLayer("LineString?crs=EPSG:4326", f"Waze Jams {datetime_str}", "memory")
    pr = vl.dataProvider()
    pr.addAttributes([
        QgsField("jam_id", QVariant.String),
        QgsField("type", QVariant.String),
        QgsField("level", QVariant.Int),
        QgsField("severity", QVariant.String),
        QgsField("speed_kmh", QVariant.Double),
        QgsField("length_m", QVariant.Double),
        QgsField("delay_sec", QVariant.Double),
        QgsField("city", QVariant.String),
        QgsField("street", QVariant.String)
    ])
    vl.updateFields()

    for _, row in df.iterrows():
        geom = QgsGeometry.fromWkt(row["line_coordinates"])
        feat = QgsFeature()
        feat.setGeometry(geom)
        feat.setAttributes([
            row["jam_id"], row["type"], row["level"], row["severity"],
            row["speed_kmh"], row["length_meters"], row["delay_seconds"],
            row["city"], row["street"]
        ])
        pr.addFeature(feat)

    vl.updateExtents()
    QgsProject.instance().addMapLayer(vl)


print("Fetching jams...")
jams = get_raw_jams_from_waze(api_key, bottom_left, top_right)
print(f"{len(jams)} jams retrieved.")
if not jams:
    raise Exception("No jams retrieved.")


csv_file = f"waze_jams_{datetime_str}.csv"

df = jams_to_csv(jams, csv_file)
print(f"Saved to {csv_file}")
display_jams_layer(df)
print("Layer added to QGIS.")

