from qgis.core import (QgsProject, QgsCoordinateReferenceSystem, QgsVectorLayer, 
                       QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsSymbol, 
                       QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsPalLayerSettings, 
                       QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from PyQt5.QtWidgets import QInputDialog
import requests
import gzip
import io
import pandas as pd
from datetime import datetime
import tempfile
import os

# Check project CRS
project = QgsProject.instance()
crs = project.crs()
datetime_str = datetime.now().strftime("%Y%m%d_%H%M")

if crs.authid() != "EPSG:4326":
    raise Exception("Project CRS must be EPSG:4326 (WGS 84). Please change CRS in Project Properties and re-run.")

# Get API key from user
api_key, ok = QInputDialog.getText(None, "OpenCellID API Key", "Enter your OpenCellID API Token:")
if not ok or not api_key:
    raise Exception(" API key is required!")

# Get MCC code (default Morocco)
mcc_code, ok = QInputDialog.getText(None, "Mobile Country Code", "Enter MCC code (e.g., 604 for Morocco):", text="604")
if not ok or not mcc_code:
    raise Exception(" MCC code is required!")

def download_opencellid_data(api_key, mcc_code):
    
    columns = [
        "reseau", "code_pays", "operateur", "zone", "antenne", "unite",
        "longitude", "latitude", "portee_en_m", "observations", 
        "modifiable", "creation", "mise_a_jour", "signal_moyen"
    ]
    
    url = f"https://opencellid.org/ocid/downloads?token={api_key}&type=mcc&file={mcc_code}.csv.gz"
    
    try:
        print("Downloading data from OpenCellID...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        

        content_type = response.headers.get('Content-Type', '')
        if 'text' in content_type:
            error_msg = response.text[:200]
            raise Exception(f"API Error: {error_msg}")
        
        print("Decompressing data...")
        compressed_file = io.BytesIO(response.content)
        with gzip.GzipFile(fileobj=compressed_file, mode='rb') as decompressed_file:
            text_stream = io.TextIOWrapper(decompressed_file, encoding='utf-8')
            df = pd.read_csv(text_stream, names=columns)
        
        if df.empty:
            raise Exception(f"No data found for MCC {mcc_code}")
        
        print(f"Raw data loaded: {len(df)} records")
        return df
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
    except Exception as e:
        if "API Error" in str(e):
            raise e
        raise Exception(f"Data processing error: {str(e)}")

def process_data(df):
    
    print("Processing data...")
    
    if "signal_moyen" in df.columns:
        df.drop("signal_moyen", inplace=True, axis=1)
    
    df.dropna(inplace=True)
    

    df["creation"] = pd.to_datetime(df["creation"], unit="s", errors='coerce')
    df["mise_a_jour"] = pd.to_datetime(df["mise_a_jour"], unit="s", errors='coerce')
    

    def map_to_generation(reseau):
        network_map = {
            "GSM": "2G", "UMTS": "3G", "LTE": "4G", 
            "NR": "5G", "CDMA": "CDMA"
        }
        return network_map.get(str(reseau).upper(), "Autre")
    

    def map_to_operator(operateur):
        if pd.isna(operateur):
            return "Inconnu"
        operator_map = {
            0: "Orange", 1: "IAM", 2: "INWI"
        }
        return operator_map.get(int(operateur), "Autre")
    
    df["reseau"] = df["reseau"].apply(map_to_generation)
    df["operateur"] = df["operateur"].apply(map_to_operator)
    
    

    print(f"Data cleaned: {len(df)} valid records")
    return df

def save_to_csv(df, mcc_code):

    
    csv_file = f"opencellid_mcc{mcc_code}_{datetime_str}.csv"
    csv_path = os.path.join(tempfile.gettempdir(), csv_file)
    
    try:
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"CSV saved: {csv_path}")
        return csv_path
    except Exception as e:
        print(f"Could not save CSV: {str(e)}")
        return None

def create_qgis_layer(df, mcc_code):

    
    print("Creating QGIS layer...")
    

    layer_name = f"Cell Towers MCC {mcc_code} - {datetime_str}"
    vl = QgsVectorLayer(f"Point?crs=EPSG:4326", layer_name, "memory")
    pr = vl.dataProvider()
    

    pr.addAttributes([
        QgsField("reseau", QVariant.String),
        QgsField("operateur", QVariant.String),
        QgsField("zone", QVariant.Int),
        QgsField("antenne", QVariant.Int),
        QgsField("observations", QVariant.Int),
        QgsField("longitude", QVariant.Float),
        QgsField("latitude", QVariant.Float),
        QgsField("portee_en_m", QVariant.Int),
        QgsField("creation", QVariant.String),
        QgsField("mise_a_jour", QVariant.String)
    ])
    vl.updateFields()
    

    for _, row in df.iterrows():
        try:
            feat = QgsFeature()
            point = QgsPointXY(float(row['longitude']), float(row['latitude']))
            feat.setGeometry(QgsGeometry.fromPointXY(point))
            feat.setAttributes([
                    row["reseau"],
                    row["operateur"],
                    row["zone"],
                    row["antenne"],
                    row["observations"],
                    row["longitude"],
                    row["latitude"],
                    row["portee_en_m"],
                    row["creation"],
                    row["mise_a_jour"]
            ])

            pr.addFeature(feat)
            

        except Exception as e:
            continue  
    
    vl.updateExtents()
    QgsProject.instance().addMapLayer(vl)
    


try:
    print("Starting OpenCellID import...")
    
    df = download_opencellid_data(api_key, mcc_code)
    df = process_data(df)
    
    if df.empty:
        raise Exception("No valid data to import")
    

    csv_path = save_to_csv(df, mcc_code)
    
    create_qgis_layer(df, mcc_code)
    

    
    
    
    print("OpenCellID data successfully imported!")
    print(f"Total cell towers: {len(df)}")
    print(f"Layer name: {layer.name()}")
    if csv_path:
        print(f" CSV location: {csv_path}")
    


except Exception as e:
    print(f" Error: {str(e)}")
    raise e