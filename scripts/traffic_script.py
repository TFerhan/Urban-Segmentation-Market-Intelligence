from qgis.PyQt.QtWidgets import QInputDialog, QMessageBox, QFileDialog
from qgis.core import QgsVectorLayer, QgsProject
import pandas as pd
import geopandas as gpd
import osmnx as ox
import geopandas as gpd
import datetime
import pandas as pd
import math
import geopandas as gpd
from shapely import wkt
from geopandas.tools import sjoin_nearest
import requests

def show_error(msg):
    QMessageBox.critical(None, "Erreur", msg)

def get_graph_data(city = "Casablanca", country = "Morocco", coords = None, network_type = "drive" ):
  try:
    if coords:
      return ox.graph_from_bbox(coords, network_type=network_type)
    return ox.graph_from_place(f"{city}, {country}", network_type=network_type)
  except Exception as e:
    print(f"Error in get_graph_data: {e}")
    return None

def get_intersection_points(G, num_intersections=1):
  try:
    intersection_nodes = [node for node, degree in G.degree() if degree > num_intersections]
    intersection_points = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in intersection_nodes]
    return intersection_points
  except Exception as e:
    print(f"Error in get_intersection_points: {e}")
    return []

def jump_five_steps(inter_points, steps = 2):
  try:
    new_inter = []
    end = len(inter_points)
    for i in range(0, end, steps):
      new_inter.append(inter_points[i])
    return new_inter
  except Exception as e:
    print(f"Error in jump_five_steps: {e}")
    return []

def coords_to_wkt_line(coords):
  try:
    if isinstance(coords, str):
        return coords
    points = ", ".join(f"{pt['longitude']} {pt['latitude']}" for pt in coords)
    return f"LINESTRING({points})"
  except Exception as e:
    print(f"Error in coords_to_wkt_line: {e}")
    return ""

def tomtom_to_seg(data):
  try:
    segments = data["flowSegmentData"]
    wkt_segment = coords_to_wkt_line(segments["coordinates"]["coordinate"])
    segments["coordinates"] = wkt_segment
    return segments
  except Exception as e:
    print(f"Error in tomtom_to_seg: {e}")
    return {}

def get_tomtom_data(latitude, longitude, api_key, zoom=19):
  try:
    
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/{zoom}/json?point={latitude}%2C{longitude}&unit=KMPH&openLr=true&key={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
      print("Problem with fetching data...")
      return {}
    data = response.json()
    
    return data
  except Exception as e:
    print(f"Error in get_tomtom_data: {e}")
    return {}

def get_traffic_data(city = "Casablanca", country = "Morocco", coords = None, degree=1, network_type = "drive", steps = 2, zoom = 19, api_key ="UkmMPDWyw5AEJ0rXg4IvlDZC2DrRNJIR"):
  try:
    G = get_graph_data(city, country, coords, network_type)
    if G is None:
      return pd.DataFrame(), None
    
    intersections = get_intersection_points(G, degree)
    new_intersections = jump_five_steps(intersections, steps)
    print(f"Found {len(new_intersections)} intersections after jumping {steps} steps")
    traffic_data = []
    count = 0

    for inter in new_intersections:
        latitude, longitude = inter
        data = get_tomtom_data(latitude, longitude, api_key, zoom)
        if not data:
            continue
        traffic_data.append(tomtom_to_seg(data))
        count += 1
    print(f"Fetched traffic data for {count} intersections")
    df = pd.DataFrame(traffic_data)
    df["created"] = datetime.datetime.now().isoformat()
    df.drop_duplicates(inplace=True)
    edges = ox.graph_to_gdfs(G, nodes=False)
    return df, edges
  except Exception as e:
    print(f"Error in get_traffic_data: {e}")
    return pd.DataFrame(), None

def estimer_largeur_route(row):
  try:
    defaults = {
        'motorway': 18,
        'motorway_link': 9,
        'trunk': 13,
        'trunk_link': 9,
        'primary': 11,
        'primary_link': 9,
        'secondary': 8.5,
        'secondary_link': 7.5,
        'tertiary': 6.5,
        'tertiary_link': 6,
        'residential': 6,
        'unclassified': 5
    }

    highway = row.get('highway', None)

    if isinstance(highway, list):
        highway = highway[0] if highway else None


    default_width = defaults.get(highway, 6)
    lanes = row.get('lanes', None)
    voie_moyenne = 3.25


    if lanes is None or (isinstance(lanes, float) and math.isnan(lanes)):
        return default_width

    try:

        if isinstance(lanes, list):
            lanes_int = max(int(float(l)) for l in lanes)


        elif isinstance(lanes, str):
            lanes_int = int(float(lanes))

        elif isinstance(lanes, (int, float)):
            lanes_int = int(lanes)

        else:
            return default_width

        est_width = lanes_int * voie_moyenne
        return max(est_width, default_width)

    except Exception as e:
        print(f"Error with lanes={lanes}: {e}")
        return default_width
  except Exception as e:
    print(f"Error in estimer_largeur_route: {e}")
    return 6

def clean_lanes(val):
  try:
    if isinstance(val, list):
        return val[0]
    return val
  except Exception as e:
    print(f"Error in clean_lanes: {e}")
    return val

def get_roads_data(edges):
  try:
    rows_lanes = {"lanes": [], "highway":[], "geometry":[], "oneway":[], "length":[]}
    for i, row in edges.iterrows():
        rows_lanes["lanes"].append(row.get("lanes", None))
        rows_lanes["highway"].append(row.get("highway", None))
        rows_lanes["geometry"].append(row.get("geometry", None))
        rows_lanes["oneway"].append(row.get("oneway", None))
        rows_lanes["length"].append(row.get("length", None))
    df = pd.DataFrame(rows_lanes)
    df["lanes_clean"] = df["lanes"].apply(clean_lanes)
    df["lanes_clean"] = pd.to_numeric(df["lanes_clean"], errors="coerce")
    lanes_by_highway = (
      df.dropna(subset=["lanes_clean"])
        .groupby("highway")["lanes_clean"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else x.median())
        .to_dict()
    )

    df["lanes_filled"] = df.apply(
      lambda row: lanes_by_highway.get(row["highway"]) if pd.isna(row["lanes_clean"]) else row["lanes_clean"],
      axis=1
    )
    df.drop(columns=["lanes", "lanes_clean"], inplace=True)
    df.rename(columns={"lanes_filled": "lanes"}, inplace=True)
    df["width_estimated"] = df.apply(estimer_largeur_route, axis=1)
    return df
  except Exception as e:
    print(f"Error in get_roads_data: {e}")
    return pd.DataFrame()

def join_tomtom_road(tomtom_df, road_df):
  try:
    road_traffic = tomtom_df.copy()
    road_traffic["geometry"] = road_traffic["coordinates"].apply(wkt.loads)
    osmnx_gdf = gpd.GeoDataFrame(road_df, geometry="geometry", crs="EPSG:3857")
    tomtom_gdf = gpd.GeoDataFrame(road_traffic, geometry="geometry", crs="EPSG:3857")
    tomtom_gdf = tomtom_gdf.reset_index().rename(columns={"index": "traffic_id"})
    tomtom_join_road = gpd.sjoin_nearest(tomtom_gdf, osmnx_gdf, how="left", distance_col="dist")
    tomtom_best_match = (
      tomtom_join_road
      .sort_values("dist")
      .drop_duplicates(subset="traffic_id")
      .reset_index(drop=True)
    )
    date_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")

    tomtom_best_match.to_csv(f"tomtom_best_match_road_{date_time}.csv", index=False)
    print(f"Data saved to tomtom_best_match_road_{date_time}.csv")
    return tomtom_best_match
  except Exception as e:
    print(f"Error in join_tomtom_road: {e}")
    return pd.DataFrame()

def get_full_data_tomtom_road(city = "Casablanca", country = "Morocco", coords = None, degree=1, network_type = "drive", steps = 2, zoom = 19,  api_key ="UkmMPDWyw5AEJ0rXg4IvlDZC2DrRNJIR"):
  print("Fetching traffic data...")
  try:
    traffic_df, edges = get_traffic_data(city, country, coords, degree, network_type, steps, zoom, api_key)
    print("Traffic data fetched successfully")
    if traffic_df.empty or edges is None:
      print("Error: No traffic data or edges obtained")
      return pd.DataFrame()
    
    road_df = get_roads_data(edges)
    print("Road data fetched successfully")
    if road_df.empty:
      print("Error: No road data obtained")
      return pd.DataFrame()
    
    final_data = join_tomtom_road(traffic_df, road_df)
    print("Data joined successfully")
    return final_data
  except Exception as e:
    print(f"Error in get_full_data_tomtom_road: {e}")
    return pd.DataFrame()

try :
    api_key, ok = QInputDialog.getText(None, "Clé API TomTom", "Entrez votre clé API :")
    if not ok or not api_key:
        raise Exception("Clé API non fournie")

    # 2. Choisir la méthode de localisation
    options = ["Coordonnées manuelles", "Ville + Pays", "Étendue de la carte (canvas)"]
    method, ok = QInputDialog.getItem(None, "Méthode de localisation", "Choisissez :", options, editable=False)
    if not ok:
        raise Exception("Méthode de localisation non choisie")

    # Variables à passer
    coords = None
    city = None
    country = None
    degree = 2
    network_type = "drive"
    steps = 2

    # 3. Selon le choix, demander les infos
    if method == "Coordonnées manuelles":
            text, ok = QInputDialog.getText(None, "Coordonnées", 
                "Entrez les coordonnées sous forme : ouest, sud, est, nord\nExemple : -7.6,33.2,-7.4,33.5")
            if not ok or not text:
                raise Exception("Coordonnées non fournies")
            try:
                parts = [x.strip() for x in text.split(",")]
                if len(parts) != 4:
                    raise ValueError("Vous devez entrer exactement 4 valeurs séparées par des virgules.")
                coords = tuple(float(x) for x in parts)
            except Exception as e:
                raise Exception(f"Format invalide des coordonnées : {e}")

    elif method == "Ville + Pays":
        city, ok1 = QInputDialog.getText(None, "Ville", "Nom de la ville :")
        country, ok2 = QInputDialog.getText(None, "Pays", "Nom du pays :")
        if not ok1 or not ok2:
            raise Exception("Ville ou pays non fournis")

    elif method == "Étendue de la carte (canvas)":
        canvas = iface.mapCanvas()
        extent = canvas.extent()
        crs = canvas.mapSettings().destinationCrs()
        if crs.authid() != "EPSG:4326":
            raise Exception("Le CRS doit être EPSG:4326")
        # bbox: west, south, east, north
        coords = (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())
        print("Étendue de la carte :", coords)

    # 4. Niveau de zoom
    zoom_str, ok = QInputDialog.getText(None, "Zoom", "Niveau de zoom (1–19) : (vide = 19 par défaut)")
    if not ok:
        raise Exception("Zoom non fourni")
    if not zoom_str.strip():  # vide
        zoom = 19
    else:
        try:
            zoom = int(zoom_str.strip())
            if zoom > 19:
                QMessageBox.warning(None, "Zoom limité", "Zoom trop élevé. Il est plafonné à 19.")
                zoom = 19
            elif zoom < 1:
                raise Exception("Zoom trop faible. Il doit être entre 1 et 19.")
        except:
            raise Exception("Zoom invalide. Entrez un nombre entier entre 1 et 19.")
        

    
    degree_str, ok = QInputDialog.getText(None, "Degré d'intersection", "Degré d'intersection : (vide = 1 par défaut)")
    if not ok:
        raise Exception("Degré d'intersection non fourni")  
    if not degree_str.strip():
        degree = 1
    else:
        try:
            degree = int(degree_str.strip())
            if degree <= 0:
                raise Exception("Degré d'intersection invalide. Il doit être supérieur à 0.")
        except:
            raise Exception("Degré d'intersection invalide. Entrez un nombre entier positif supérieur à 0.")
        
        
    steps_str, ok = QInputDialog.getText(None, "Pas de saut de routes", "Pas de saut (2 par défaut) : (vide = 2 par défaut)")
    if not ok:
        raise Exception("Pas de saut non fourni")
    if not steps_str.strip():  
        steps = 2
    else:
        try:
            steps = int(steps_str.strip())
            if steps < 1:
                raise Exception("Pas de saut invalide. Il doit être supérieur à 0.")
        except:
            raise Exception("Pas de saut invalide. Entrez un nombre entier positif.")



    df = get_full_data_tomtom_road(city=city, country=country, coords=coords, zoom=zoom, api_key=api_key)

    if df.empty:
        raise Exception("Aucune donnée retournée")


    # Convertir en GeoDataFrame avec géométries valides
    gdf = gpd.GeoDataFrame(df, geometry=df["geometry"], crs="EPSG:3857")
    if gdf["geometry"].dtype == "object":
        gdf["geometry"] = gdf["geometry"].apply(wkt.loads)

    # Demander à l'utilisateur où enregistrer le fichier
    file_path, _ = QFileDialog.getSaveFileName(
        None,
        "Enregistrer le fichier de trafic",
        "traffic_roads.gpkg",
        "GeoPackage (*.gpkg);;CSV (*.csv)"
    )

    if not file_path:
        raise Exception("Aucun chemin de sauvegarde sélectionné.")

    # Déterminer le format de sauvegarde
    if file_path.endswith(".csv"):
        # Pour CSV, convertir la géométrie en WKT
        gdf["geometry"] = gdf["geometry"].apply(lambda g: g.wkt)
        gdf.to_csv(file_path, index=False)
        print(f"Fichier CSV enregistré : {file_path}")
    else:
        # Par défaut, enregistrer en GeoPackage
        gdf.to_file(file_path, driver="GPKG", layer="traffic_roads")
        print(f"Fichier GeoPackage enregistré : {file_path}")

        # Ajouter dans QGIS si c'est un fichier spatial
        layer = QgsVectorLayer(f"{file_path}|layername=traffic_roads", "Traffic Roads", "ogr")
        if not layer.isValid():
            raise Exception("Échec du chargement de la couche")
        QgsProject.instance().addMapLayer(layer)



except Exception as e:
    show_error(str(e))