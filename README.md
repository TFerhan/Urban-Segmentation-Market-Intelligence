# Retail Site Selection Project

## Overview

This project aims to optimize the selection of new store locations for a major retail chain in Morocco by leveraging diverse data sources and advanced spatial data analysis techniques. The goal is to identify the best areas for store implantation based on socio-demographic, urban, and competitive factors, using machine learning and geographic information systems (GIS).

## Data Sources

The project integrates multiple heterogeneous data sources, including:  
- Public socio-economic datasets from the Moroccan High Commission for Planning (HCP) and data.gov.ma  
- Real estate data scraped from online platforms (prices per square meter by neighborhood)  
- Geospatial data from OpenStreetMap, Google Maps API, OpenCelliD, and OpenRouteService  
- Traffic and mobility data via APIs from TomTom, Waze, and Google Maps  
- Competitor store locations obtained via web scraping from major retailers in the area  
- Internally inferred data such as building typologies and urban segmentation created by data processing and labeling

## Tools & Technologies

- Python (BeautifulSoup, Requests, Selenium, Pandas, OSMnx)  
- GIS Software (QGIS)  
- APIs (Google Maps, OpenCelliD, OpenRouteService, TomTom Traffic, Waze)  
- Power BI for interactive dashboards and visualizations

## Current Status

- Data collection and preprocessing are ongoing, with several datasets already collected and integrated.  
- Building type classification data is being labeled and prepared for machine learning model training.  
- Power BI dashboards have been created for initial exploratory analysis.  
- Further work will focus on model development, evaluation, and deployment.

## How to Use

1. Clone the repository  
2. Explore raw data under `data/raw`  
3. Run scripts in the `scripts` folder to reproduce data preprocessing  
4. Open notebooks for analysis and feature engineering  
5. View Power BI dashboards in the `powerbi` folder  
6. Use QGIS projects for detailed geospatial analysis  

## Contact

For questions or collaboration, please contact:  
**Taha FERHAN**  
Email: taha.ferhan@hotmail.com
HuggingFace: https://huggingface.co/tferhan

---

Thank you for your interest!
