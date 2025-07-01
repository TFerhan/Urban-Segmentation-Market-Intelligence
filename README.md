# Urban-Segmentation-Market-Intelligence

This Project consist of using satellite imagery, and other geospatial and socio-demographic data to help in the decision of store placement within Group LabelVie (Carrefour) but its potential cover any other Real Estate Insights in terms of business value one should take it on consideration.

First finetuning Segformer b4 512x512 on Casablanca satellite images of different urban level, villas to Apparts to Bidonvilles.

Gathering and labeling the data is the most hard part in terms of time and also in quality, using QGIS Software to get tiles and then GDAL to form 512x512 raster from that tile of a resolution of 0.3 (Zoom 19).

Saving those tiles in a format of JPEG of 90% quality, as this format keep quality and in same time small size , at the opposite of TIFF images which take very large memory. 

All files including the pre-processing in QGIS and in python will be included in this Repo, some scripts that add layers in QGIS about some road traffic or telecommunication data require a key API, but all the 

other data will be open source including the tiles and the model so feel free to use it in any function.

Updating the Project every day ...
