from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QRadioButton, QButtonGroup
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.utils import iface
from qgis.core import QgsProject, QgsMapLayer, QgsWkbTypes, QgsVectorLayer
import processing
import time
import os

def choose_layer_source():
    """Let user choose between existing layers or file system"""
    dialog = QDialog()
    dialog.setWindowTitle("Choose Data Source")
    dialog.setMinimumWidth(300)
    
    layout = QVBoxLayout()
    
    # Radio buttons for source selection
    layout.addWidget(QLabel("Choose your data source:"))
    
    button_group = QButtonGroup()
    existing_radio = QRadioButton("Use existing layer from project")
    file_radio = QRadioButton("Load from file system")
    
    button_group.addButton(existing_radio)
    button_group.addButton(file_radio)
    
    existing_radio.setChecked(True)  # Default selection
    
    layout.addWidget(existing_radio)
    layout.addWidget(file_radio)
    
    # Buttons
    button_layout = QHBoxLayout()
    ok_btn = QPushButton("OK")
    cancel_btn = QPushButton("Cancel")
    
    button_layout.addWidget(ok_btn)
    button_layout.addWidget(cancel_btn)
    layout.addLayout(button_layout)
    
    dialog.setLayout(layout)
    
    # Connect buttons
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)
    
    result = dialog.exec_()
    if result == QDialog.Accepted:
        return "existing" if existing_radio.isChecked() else "file"
    return None

def choose_existing_layer():
    """Let user choose from existing point layers"""
    layers = [layer for layer in QgsProject.instance().mapLayers().values() 
              if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry]
    
    if not layers:
        QMessageBox.critical(None, "Error", "No point layers found in project.")
        return None
    
    layer_names = [layer.name() for layer in layers]
    
    layer_name, ok = QInputDialog.getItem(None, "Select Layer", 
                                         "Choose a point layer:", 
                                         layer_names, 0, False)
    
    if ok and layer_name:
        for layer in layers:
            if layer.name() == layer_name:
                return layer
    return None

def load_layer_from_file():
    """Let user load a point layer from file system"""
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "Select Point Layer File",
        "",
        "Vector Files (*.shp *.gpkg *.geojson *.kml *.csv);;All Files (*)"
    )

    if not file_path:
        return None

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        # Load CSV as table first
        uri = f"file://{file_path}?type=csv&detectTypes=yes&xField=LONG_PLACEHOLDER&yField=LAT_PLACEHOLDER&crs=EPSG:4326"
        temp_layer = QgsVectorLayer(uri, "TempCSV", "delimitedtext")

        if not temp_layer.isValid():
            QMessageBox.critical(None, "Error", f"Could not load CSV: {file_path}")
            return None

        # Let user choose lat/lon fields
        lat_field, lon_field = choose_fields(temp_layer)
        if not lat_field or not lon_field:
            return None

        # Reconstruct the URI with selected fields
        uri = f"file://{file_path}?type=csv&detectTypes=yes&xField={lon_field}&yField={lat_field}&crs=EPSG:4326"
        point_layer = QgsVectorLayer(uri, os.path.basename(file_path), "delimitedtext")

        if not point_layer.isValid():
            QMessageBox.critical(None, "Error", f"Could not create point layer from CSV")
            return None

        QgsProject.instance().addMapLayer(point_layer)
        iface.messageBar().pushInfo("CSV Loaded", f"Added {point_layer.name()} to project")

        return point_layer

    else:
        # Handle normal vector files
        layer_name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsVectorLayer(file_path, layer_name, "ogr")

        if not layer.isValid():
            QMessageBox.critical(None, "Error", f"Could not load layer from {file_path}")
            return None

        if layer.geometryType() != QgsWkbTypes.PointGeometry:
            QMessageBox.critical(None, "Error", "Selected file is not a point layer.")
            return None

        QgsProject.instance().addMapLayer(layer)
        iface.messageBar().pushInfo("Layer Loaded", f"Added {layer_name} to project")
        return layer


def choose_fields(layer):
    """Let user choose latitude and longitude fields"""
    field_names = [f.name() for f in layer.fields()]
    
    # Choose latitude field
    lat_field, ok = QInputDialog.getItem(None, "Select Latitude Field", 
                                        "Choose the latitude field:", 
                                        field_names, 0, False)
    if not ok:
        return None, None
    
    # Choose longitude field
    lon_field, ok = QInputDialog.getItem(None, "Select Longitude Field", 
                                        "Choose the longitude field:", 
                                        field_names, 0, False)
    if not ok:
        return None, None
    
    return lat_field, lon_field

def get_api_key():
    """Get API key from user"""
    # Try to get from settings first
    api_key = QSettings().value("plugin/ORS Tools/api_key", "")
    
    api_key, ok = QInputDialog.getText(None, "ORS API Key", 
                                      "Enter your OpenRouteService API key:", 
                                      text=api_key)
    
    if ok and api_key:
        QSettings().setValue("plugin/ORS Tools/api_key", api_key)
        return api_key
    return None

def get_isochrone_settings():
    """Get isochrone settings from user"""
    # Ranges
    ranges, ok = QInputDialog.getText(None, "Isochrone Ranges", 
                                     "Enter ranges (comma-separated, e.g., '5,10,15'):", 
                                     text="5,10")
    if not ok:
        return None, None, None, None
    
    # Metric (time vs distance)
    metrics = ["Time (minutes)", "Distance (meters)"]
    metric_choice, ok = QInputDialog.getItem(None, "Range Type", 
                                            "Choose range type:", 
                                            metrics, 0, False)
    if not ok:
        return None, None, None, None
    metric = 0 if "Time" in metric_choice else 1
    
    profile_mapping = {
    "Driving Car": 0,
    "Foot Walking": 6
}

    # Ask the user
    profiles = list(profile_mapping.keys())
    profile_choice, ok = QInputDialog.getItem(None, "Transport Profile",
                                            "Choose transport profile:",
                                            profiles, 0, False)
    if not ok:
        return None, None, None, None

    # Use the mapped value directly
    profile = profile_mapping[profile_choice]
    
    # Location type
    location_types = ["Start point", "Destination point"]
    location_choice, ok = QInputDialog.getItem(None, "Location Type", 
                                              "Choose location type:", 
                                              location_types, 0, False)
    if not ok:
        return None, None, None, None
    location_type = location_types.index(location_choice)
    
    return ranges, metric, profile, location_type

def run_batch_isochrones():
    """Main function to run batch isochrones"""
    
    # Step 1: Choose data source
    source_type = choose_layer_source()
    if not source_type:
        return
    
    # Step 2: Get the layer
    if source_type == "existing":
        layer = choose_existing_layer()
    else:
        layer = load_layer_from_file()
    
    if not layer:
        return
    
    print(f"Selected layer: {layer.name()} with {layer.featureCount()} features")
    
    # Step 3: Choose fields
    lat_field, lon_field = choose_fields(layer)
    if not lat_field or not lon_field:
        return
    
    print(f"Using fields - Latitude: {lat_field}, Longitude: {lon_field}")
    
    # Step 4: Get API key
    api_key = get_api_key()
    if not api_key:
        return
    
    # Step 5: Get isochrone settings
    ranges, metric, profile, location_type = get_isochrone_settings()
    if ranges is None:
        return
    
    print(f"Settings - Ranges: {ranges}, Metric: {metric}, Profile: {profile}, Location type: {location_type}")
    
    # Step 6: Process features
    isochrone_features = []
    request_counter = 0
    start_time = time.time()
    total_features = layer.featureCount()
    processed_count = 0
    error_count = 0
    
    print(f"Starting batch processing of {total_features} points...")
    iface.messageBar().pushInfo("Processing", f"Starting batch processing of {total_features} points...")
    
    for feature in layer.getFeatures():
        try:
            lat = feature[lat_field]
            lon = feature[lon_field]
            
            # Skip if coordinates are None or invalid
            if lat is None or lon is None:
                print(f"Skipping feature with invalid coordinates: lat={lat}, lon={lon}")
                error_count += 1
                continue
            
            coord = f"{lon},{lat} [EPSG:4326]"
            
            result = processing.run("ORS Tools:isochrones_from_point", {
                'INPUT_PROVIDER': 0,
                'INPUT_PROFILE': profile,
                'INPUT_POINT': coord,
                'INPUT_METRIC': metric,
                'INPUT_RANGES': ranges,
                'INPUT_SMOOTHING': None,
                'LOCATION_TYPE': location_type,
                'INPUT_AVOID_FEATURES': [],
                'INPUT_AVOID_BORDERS': None,
                'INPUT_AVOID_COUNTRIES': '',
                'INPUT_AVOID_POLYGONS': None,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })
            
            output_layer = result['OUTPUT']
            
            # Add all features from this isochrone result
            for iso_feature in output_layer.getFeatures():
                isochrone_features.append(iso_feature)
            
            request_counter += 1
            processed_count += 1
            
            print(f"Processed {processed_count}/{total_features} points - Generated isochrones for ({lat}, {lon})")
            
            # Update progress in message bar
            if processed_count % 5 == 0:  # Update every 5 features
                iface.messageBar().clearWidgets()
                iface.messageBar().pushInfo("Processing", f"Processed {processed_count}/{total_features} points...")
            
            # Respect the 20 requests/min limit (rate limiting)
            if request_counter >= 20:
                elapsed = time.time() - start_time
                if elapsed < 60:
                    sleep_time = 60 - elapsed
                    print(f"Rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
                    iface.messageBar().pushInfo("Rate Limit", f"Pausing for {sleep_time:.1f} seconds (API rate limit)...")
                    time.sleep(sleep_time)
                request_counter = 0
                start_time = time.time()
                
        except Exception as e:
            print(f"Error processing point ({lat}, {lon}): {str(e)}")
            error_count += 1
            continue
    
    # Step 7: Create merged layer
    if isochrone_features:
        print(f"Creating merged layer with {len(isochrone_features)} isochrone features...")
        
        merged_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", f"Isochrones_{layer.name()}", "memory")
        merged_provider = merged_layer.dataProvider()
        
        # Get field structure from the first isochrone feature
        if len(isochrone_features) > 0:
            # Use the fields from the first feature's layer
            sample_feature = isochrone_features[0]
            if hasattr(sample_feature, 'fields'):
                merged_provider.addAttributes(sample_feature.fields())
            else:
                # Fallback: create a temporary result to get field structure
                try:
                    temp_coord = f"{list(layer.getFeatures())[0][lon_field]},{list(layer.getFeatures())[0][lat_field]} [EPSG:4326]"
                    temp_result = processing.run("ORS Tools:isochrones_from_point", {
                        'INPUT_PROVIDER': 0,
                        'INPUT_PROFILE': profile,
                        'INPUT_POINT': temp_coord,
                        'INPUT_METRIC': metric,
                        'INPUT_RANGES': ranges,
                        'INPUT_SMOOTHING': None,
                        'LOCATION_TYPE': location_type,
                        'INPUT_AVOID_FEATURES': [],
                        'INPUT_AVOID_BORDERS': None,
                        'INPUT_AVOID_COUNTRIES': '',
                        'INPUT_AVOID_POLYGONS': None,
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    })
                    temp_layer = temp_result['OUTPUT']
                    merged_provider.addAttributes(temp_layer.fields())
                except:
                    pass  # Continue without fields if this fails
            
            merged_layer.updateFields()
        
        # Add all collected features to the merged layer
        merged_provider.addFeatures(isochrone_features)
        merged_layer.updateExtents()
        
        # Add the merged layer to the project
        QgsProject.instance().addMapLayer(merged_layer)
        
        success_msg = f"Success! Generated {len(isochrone_features)} isochrones from {processed_count} points"
        if error_count > 0:
            success_msg += f" ({error_count} errors)"
        
        print(success_msg)
        iface.messageBar().clearWidgets()
        iface.messageBar().pushSuccess("Complete", success_msg)
        
    else:
        error_msg = f"No isochrones were created. Processed: {processed_count}, Errors: {error_count}"
        print(error_msg)
        iface.messageBar().clearWidgets()
        iface.messageBar().pushWarning("No Results", error_msg)

# Run the function
run_batch_isochrones()