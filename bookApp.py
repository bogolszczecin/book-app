#fastAPI functionality imports
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError, validator, Field
from pydantic.functional_validators import AfterValidator
from typing import Optional, List, Annotated
import uvicorn
#Database SQL Lite and data types imports
from sqlalchemy import inspect, func, create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, class_mapper
from datetime import datetime
#GIS features imports
from scipy.spatial import KDTree
from math import radians, sin, cos, sqrt, atan2
import requests
import folium
from folium.plugins import MarkerCluster

app = FastAPI()
# manage SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base = declarative_base()

# --CLASS-- creating address class along with fields definition
class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String, index=True, nullable=False)
    dateCreated = Column(DateTime, default=datetime.now)
    latitude = Column(Float)
    longitude = Column(Float)

Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class AddressInput(BaseModel):
    name: str
    address: str
    latitude: float = Field(..., description="Latitude of the address. Must be in the range [-90, 90]")
    longitude: float = Field(..., description="Longitude of the address. Must be in the range [-180, 180]")

    @validator("latitude")
    def latitude_must_be_valid(cls, value):
        if value < -90 or value > 90:
            raise ValueError("Latitude must be in the range [-90, 90]")
        return value

    @validator("longitude")
    def longitude_must_be_valid(cls, value):
        if value < -180 or value > 180:
            raise ValueError("Longitude must be in the range [-180, 180]")
        return value

# Function to save address to SQLite database
def save_address_to_db(name: str, address: str, latitude: float, longitude: float):
    db = SessionLocal()
    db_address = Address(address=address, name=name, latitude=latitude, longitude=longitude)
    db.add(db_address)
    db.commit()
    db.refresh(db_address)
    db.close()

# Endpoint to add address functionality
@app.post("/add_address/")
def add_address(name: str, address: str, latitude: float, longitude: float):
    """
     Add address to SQLite database.

     Args:
         *Address input data including*

         name - string value containing name of the address point eq. Noname Company Ltd.
         address - string value containing address of the point eq. N637 295, 4460 Grâce-Hollogne, Belgium
         latitude - decimal float value of latitude of the point eq. 50.64743109543702
         longitude - decimal float value of longitude of the point eq. 5.496302759941758

     Returns:
         *dict: A message indicating the success of the operation and the address of new place.*

     Raises:
         *HTTPException: If there are incorrect coordinate values of the new address.*
     """
    try:
        save_address_to_db(name, address, latitude, longitude)
        return {"message": "Address added successfully", "address": address}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding address: {str(e)}")

# Endpoint to edit an address by its ID
@app.put("/edit_address/")
def edit_address_by_id(address_id: int, name: Optional[str] = None, address: Optional[str] = None,
                       latitude: Optional[float] = Query(None, ge=-90, le=90),
                       longitude: Optional[float] = Query(None, ge=-180, le=180)):
    db = SessionLocal()
    try:
        # Retrieve the address by ID
        db_address = db.query(Address).filter(Address.id == address_id).first()

        # Check if the address with the given ID exists
        if db_address is None:
            raise HTTPException(status_code=404, detail="Address not found")

        # Update the address fields with the provided values
        if name is not None:
            db_address.name = name
        if address is not None:
            db_address.address = address
        if latitude is not None:
            db_address.latitude = latitude
        if longitude is not None:
            db_address.longitude = longitude

        # Commit the changes to the database
        db.commit()
        db.refresh(db_address)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error editing address: {str(e)}")
    finally:
        db.close()

    return {"message": "Address updated successfully", "address_id": address_id}

# Function to remove address by ID
def remove_address_from_db(db, address_id: int):
    address = db.query(Address).filter(Address.id == address_id).first()
    if address:
        db.delete(address)
        db.commit()
        return True
    else:
        return False
# Endpoint to remove addresses by IDs
@app.delete("/remove_addresses/")
def remove_addresses(address_ids: str):
    """
    Remove addresses by their IDs.

    Args:

        address_ids - Comma-separated (,) string of address IDs to remove single addresses
        and/or dash-separated (-) string of address IDs to remove multiple addresses eg. 1,3,5,10-13

    Returns:
        *dict: A message indicating the success of the operation and the IDs of the removed addresses: 1,3,5,10,11,12,13*

    Raises:
        *HTTPException: If no addresses are found with the provided IDs.*
    """
    db = SessionLocal()
    removed_addresses = []
    for address_id in address_ids.split(","):
        if address_id.strip() == "":
            continue  # Skip empty fields
        #allowing user removing addresses in easier input way with 4-6 as 4,5,6 format example
        if "-" in address_id:
            start, end = map(int, address_id.split("-"))
            for i in range(start, end + 1):
                if remove_address_from_db(db, str(i)):
                    removed_addresses.append(str(i))
        if remove_address_from_db(db, address_id):
            removed_addresses.append(address_id)
    db.close()
    if removed_addresses:
        return {"message": "Addresses removed successfully", "removed_ids": removed_addresses}
    else:
        raise HTTPException(status_code=404, detail="Addresses not found, please make sure that: "
                                                    "1. You input addresses ID in the correct format"
                                                    "2. Addresses exisit in database")

# Helper function to convert SQLAlchemy objects to dictionaries
def obj_to_dict(obj):
    return {column.key: getattr(obj, column.key) for column in class_mapper(obj.__class__).columns}

# Function to generate a map with markers for addresses
def generate_map(address_data):
    """
    Generate a map with markers for the given addresses.

    Args:
        address_data (list): List of dictionaries containing address information.

    Returns:
        str: HTML code for the map visualization.
    """
    # Create a map centered at the first address
    map_center = (address_data[0]["latitude"], address_data[0]["longitude"])
    map_obj = folium.Map(location=map_center, zoom_start=10)
    marker_cluster = MarkerCluster().add_to(map_obj)
    # Add markers for each address
    for address in address_data:
        folium.Marker([address["latitude"], address["longitude"]], popup=address["name"]).add_to(map_obj)

        # Create a custom HTML popup for the marker with name and ID
        popup_html = f"<b>Name:</b> {address['name']}<br><b>ID:</b> {address['id']}"

        # Create the marker and add it to the MarkerCluster layer
        folium.Marker(
            location=[address["latitude"], address["longitude"]],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="green"),
        ).add_to(marker_cluster)
    # Convert the map object to HTML
    map_html = map_obj.get_root().render()
    return map_html

# Endpoint to retrieve address count and data showing how many addresses are already stored in DB
@app.get("/db", response_class=HTMLResponse)
def read_address_database():
    """
    Show addresses present in the database and embed the map visualization in the response.

    Returns:
        HTMLResponse: HTML response containing the map visualization and address data.
    """
    try:
        db = SessionLocal()
        address_objects = db.query(Address).all()
        address_count = len(address_objects)

        # Convert Address objects to dictionaries
        address_data = [obj_to_dict(address) for address in address_objects]

        # Generate map visualization
        map_html = generate_map(address_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading address database: {str(e)}")
    finally:
        db.close()

    # Construct the HTML response with the map visualization and address data
    html_content = f"""
    <html>
    <head>
        <title>Address Map</title>
    </head>
    <body>
        <div style='text-align: center;'><b>{address_count} addresses found in the database</b></div>
        <div>{map_html}</div>
        <div>{address_data}</div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)

# Function to create KD-tree from addresses, effective way to create spatial ordered database of addresses (the more points we have the more use from this we get)
def create_kd_tree(addresses):
    coordinates = [(address.latitude, address.longitude) for address in addresses]
    kd_tree = KDTree(coordinates)
    return kd_tree
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points

    Args:
        lat1 (float): Latitude of the first point in degrees.
        lon1 (float): Longitude of the first point in degrees.
        lat2 (float): Latitude of the second point in degrees.
        lon2 (float): Longitude of the second point in degrees.

    Returns:
        float: The distance between the two points in kilometers.
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    radius_of_earth_km = 6371.0  # Radius of the Earth in kilometers
    distance = radius_of_earth_km * c

    return distance
@app.post("/distance_calculation")
def distance_calculation(lat1: float = Query(..., ge=-90, le=90, description="Latitude of the address. Must be in the range [-90, 90]"),
                         lon1: float = Query(..., ge=-180, le=180, description="Longitude of the address. Must be in the range [-180, 180]"),
                         lat2: float = Query(..., ge=-90, le=90, description="Latitude of the address. Must be in the range [-90, 90]"),
                         lon2: float = Query(..., ge=-180, le=180, description="Longitude of the address. Must be in the range [-180, 180]")):
    """
    Calculate distance between points.

    Args:

        lat1 - latitude of the first point eg. 15.2352465
        lon1 -  longitude of the first point eg.-45.123412
        lat1 - latitude of the second point eg. 15.151355
        lon1 -  longitude of the second point eg.-47.134412

    Returns:
        *A message indicating the success of the operation and the distance between input points given in kilometers*

    Raises:
        *HTTPException: If there was problem in calculating distance between the points.*
    """
    try:
        db = SessionLocal()
        return {"distance [km]": haversine_distance(lat1, lon1, lat2, lon2)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding distance between given points: {str(e)}")
    finally:
        db.close()

# Endpoint to find addresses within a certain distance from a start_point point using KD-tree
@app.post("/addresses_in_buffer/")
def addresses_in_buffer(buffer_distance_km: float,
                        start_point_latitude: float = Query(..., ge=-90, le=90, description="Latitude of the address. Must be in the range [-90, 90]"),
                        start_point_longitude: float = Query(..., ge=-180, le=180, description="Longitude of the address. Must be in the range [-180, 180]")):
    """
    Find addresses within a certain distance from a starting point.

    Args:
        buffer_distance_km (float): The radius of the buffer area in kilometers.

        start_point_latitude (float): Latitude of the starting point. Must be in the range [-90, 90]

        start_point_longitude (float): Longitude of the starting point. Must be in the range [-180, 180]

    Returns:
        dict: A message indicating the success of the operation and either the addresses found within the buffer area or information about the closest address and its distance if no addresses are found within the buffer distance.

    Raises:
        HTTPException: If there was a problem finding addresses in the given buffer area.
    """
    try:
        db = SessionLocal()
        # Retrieve all addresses from the database
        addresses = db.query(Address).all()
        # Create KD-tree from addresses
        kd_tree = create_kd_tree(addresses)
        deg_in_km = 40075/360 #Equator = 40075km, 360 degrees in full circle, we get each degree equivalent in km
        # Convert buffer distance to degrees latitude and longitude
        buffer_distance_deg = buffer_distance_km / deg_in_km

        # Define the query point
        query_point = (start_point_latitude, start_point_longitude)

        # Query KD-tree for addresses within the buffer distance
        nearby_indices = kd_tree.query_ball_point(query_point, buffer_distance_deg)
        # If no addresses found within the buffer distance
        if not nearby_indices:
            # Find the closest address
            closest_index = kd_tree.query(query_point)[1]
            closest_address = addresses[closest_index]

            # Calculate the distance to the closest address
            closest_distance_km = haversine_distance(start_point_latitude, start_point_longitude, closest_address.latitude,
                                                     closest_address.longitude)

            # In case there is no address point in given distance, we inform how far is closest point.
            return {
                "message": "WARNING     No addresses found within the buffer distance.",
                "closest_address": closest_address.__dict__,
                "closest_distance_km": closest_distance_km
                }

        addresses_in_buffer = [addresses[i] for i in nearby_indices]

        return {"message": "Found addresses in the given area:",
                "addresses_in_buffer": addresses_in_buffer
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding addresses in buffer: {str(e)}")
    finally:
        db.close()

def geocode(address: str) -> dict:
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data:
            # Extract latitude and longitude from the response
            latitude = float(data[0]["lat"])
            longitude = float(data[0]["lon"])
            return {"latitude": latitude, "longitude": longitude}
        else:
            raise ValueError("Address not found")
    else:
        raise ConnectionError("Unable to connect to the geocoding service")

from fastapi import HTTPException

@app.post("/geocode/")
def geocode_address(address: str):
    """
    Geocode the given address.

    Args:

        address: The address to geocode eg. Starzynskiego 8, Szczecin, Polska

    Returns:
        dict: A dictionary containing the latitude and longitude of the given address.
    """

    try:
        coordinates = geocode(address)
        return coordinates
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except ConnectionError as ce:
        raise HTTPException(status_code=500, detail=str(ce))

