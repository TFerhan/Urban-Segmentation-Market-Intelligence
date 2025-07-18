import google_colab_selenium as gs
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

def get_html(city):
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")


    driver = gs.Chrome(options=options)


    search_query = f"parapharmacie {city} Maroc"
    print(search_query)
    driver.get(f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}")


    time.sleep(3)


    sidebar_xpath = '//div[contains(@class, "m6QErb") and contains(@class, "ecceSd")]'

    scrollable_div = driver.find_element(By.XPATH, sidebar_xpath)

    try:

      divSideBar = driver.find_element(By.CSS_SELECTOR, "div[aria-label^='Results for']")

      keepScrolling = True
      count = 0
      while keepScrolling:
          print(count)
          divSideBar.send_keys(Keys.PAGE_DOWN)
          time.sleep(0.5)
          divSideBar.send_keys(Keys.PAGE_DOWN)
          time.sleep(0.5)
          html=driver.find_element(By.TAG_NAME, "html").get_attribute('outerHTML')
          count += 1
          if(count>200):
              keepScrolling=False
          if(html.find("You've reached the end of the list.")!=-1):
              keepScrolling=False

      html = driver.page_source
      with open(f"{search_query}.html", "w", encoding="utf-8") as f:
          f.write(html)
      driver.quit()
    except Exception as e:
      driver.quit()
      return ""

    print("✅ Done. HTML saved.")
    driver.quit()
    return html

import json
from bs4 import BeautifulSoup
import pandas as pd
import re

def get_parapharmacie_data(city, html_code):
    sop = BeautifulSoup(html_code, "lxml")
    data = []

    # Loop over all location cards
    for div in sop.select("div.Nv2PK.THOPZb"):
        name = div.select_one("div.qBF1Pd")
        name = name.text.strip() if name else None
        print(name)

        # Get map link (where lat/lon are embedded)
        a_tag = div.select_one("a.hfpxzc")
        href = a_tag["href"] if a_tag else None

        # Extract latitude and longitude from the URL using regex
        lat, lon = None, None
        if href:
            match = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", href)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))

        # Try to extract image
        img = div.select_one("img")
        image_url = img["src"] if img else None

        # Address, phone, status, category
        address = phone = status = category = None
        for w4 in div.select("div.W4Efsd span span"):
            txt = w4.get_text(strip=True)
            if txt.lower().startswith("bd") or "avenue" in txt.lower():
                address = txt
            elif txt.startswith("06") or txt.startswith("+212"):
                phone = txt
            elif txt.lower() in ["ouvert", "fermé"]:
                status = txt
            elif not category:
                category = txt

        data.append({
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "address": address,
            "phone": phone,
            "status": status,
            "category": category,
            "image_url": image_url
        })


    print("len data : " + str(len(data)))
    rest = pd.DataFrame(data)
    rest.to_csv(f"parapharmacie_{city}.csv", index=False)
    return data

import time

def get_para(city, retries=3, wait=3):
    for attempt in range(retries):
        html_code = get_html(city)
        if html_code:
            data = get_parapharmacie_data(city, html_code)
            if data:
                return data
        print(f"🔁 Retry {attempt+1}/{retries} for {city}")
        time.sleep(wait)
    print(f"❌ Failed to scrape data for {city} after {retries} attempts.")
    return []

def get_all_par(cities):
  all_data = []
  for city in cities:
    print(f"Starting {city}")
    data = get_para(city)
    print("city data got : " , len(data))
    if not data:
      continue
    all_data.extend(data)
  df = pd.DataFrame(all_data)
  df.to_csv("parapharmacies_all_maroc.csv", index=False)
  return all_data

import requests
url = "https://en.wikipedia.org/wiki/List_of_cities_in_Morocco"

# Send a GET request to the page
response = requests.get(url)
soup = BeautifulSoup(response.content, "lxml")

# Find the specific table by class name
table = soup.find("table", class_="wikitable")
# Extract table headers
headers = [re.sub(r'\[.*?\]', '', th.text).strip() for th in table.find_all("th")]

cities = headers[3:]

cities.index("Casablanca")

continue_cities = cities[49:]
continue_cities

# Commented out IPython magic to ensure Python compatibility.
!mkdir continue_fn
# %cd continue_fn

findings = get_all_par(continue_cities)

import os
import pandas as pd

def concat_csv_from_folder(folder_path, output_file):
    all_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    df_list = []

    for file in all_files:
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path)
        df_list.append(df)

    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.to_csv(output_file, index=False)
    print(f"Saved combined CSV to {output_file}")


folder_path = "/content/"
output_file = "maroc_parapharmacies.csv"

concat_csv_from_folder(folder_path, output_file)

df= pd.read_csv("/content/continue_fn/maroc_parapharmacies.csv")
df.head()

df.info()

df.drop_duplicates(inplace=True)

# Commented out IPython magic to ensure Python compatibility.
# %cd ..

df.to_csv("maroc_parapharmacie.csv", index=False)

df

df.info()



casa = get_all_par(["casablanca"])

!pip install geopandas shapely

para_df = pd.read_csv("/content/maroc_parapharmacie.csv")
pharma_df = pd.read_csv("/content/pharmacies_deduped.csv")

para_df.head()

import geopandas as gpd
from shapely.geometry import Point

gdf_para = gpd.GeoDataFrame(para_df, geometry=gpd.points_from_xy(para_df.longitude, para_df.latitude), crs="EPSG:4326")
gdf_para = gdf_para.to_crs(epsg=3857)

gdf_pharma = gpd.GeoDataFrame(pharma_df, geometry=gpd.points_from_xy(pharma_df.longitude, pharma_df.latitude), crs="EPSG:4326")
gdf_pharma = gdf_pharma.to_crs(epsg=3857)

gdf_para = gdf_para.reset_index(drop=True)
gdf_pharma = gdf_pharma.reset_index(drop=True)

buffer_distance = 60

pharma_buffers = gdf_pharma.geometry.buffer(buffer_distance)

pharma_buffers_gs = gpd.GeoSeries(pharma_buffers)

pharma_sindex = pharma_buffers_gs.sindex

def is_within_buffer(point):
    possible_matches_index = list(pharma_sindex.intersection(point.bounds))
    possible_matches = pharma_buffers_gs.iloc[possible_matches_index]
    return any(possible_matches.contains(point))

mask_to_keep = ~gdf_para.geometry.apply(is_within_buffer)

gdf_para_filtered = gdf_para[mask_to_keep]

para_sindex = gdf_para.sindex

# Define distance thresholds
distance_list = [20, 40, 60, 80, 100]
filtered_versions = []

# Loop over distances
for dist in distance_list:
    print(f"Filtering with buffer = {dist} meters...")
    # Create buffer around para points
    para_buffer = gdf_para.geometry.buffer(dist)
    para_buffer_gs = gpd.GeoSeries(para_buffer)
    para_buffer_sindex = para_buffer_gs.sindex

    # Check which pharmacies are NOT within any buffer
    def is_close(pharma_point):
        possible_idx = list(para_buffer_sindex.intersection(pharma_point.bounds))
        possible_buffers = para_buffer_gs.iloc[possible_idx]
        return any(possible_buffers.contains(pharma_point))

    mask = ~gdf_pharma.geometry.apply(is_close)
    filtered = gdf_pharma[mask].copy().reset_index(drop=True)
    filtered_versions.append(filtered)

# Save each filtered version as a CSV
for dist, df in zip(distance_list, filtered_versions):
    df_out = df.to_crs(epsg=4326)  # Optional: reproject back to lat/lon before saving
    df_out.drop(columns='geometry').to_csv(f"pharmacies_filtered_{dist}m.csv", index=False)

gdf['buffer'] = gdf.geometry.buffer(50)
joined = gpd.sjoin(gdf[['name', 'geometry', 'buffer']], gdf_compare[['name', 'geometry']],
                   how='inner', predicate='intersects')

gdf_para_filtered.info()

gdf_para_filtered.to_csv("cleaned_parapharmacie_maroc.csv", index=False)
