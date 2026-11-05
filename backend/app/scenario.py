"""Reproducible demo. Every business datum here is invented, not municipal data."""
from .models import Delivery, Vehicle, Incident, LoadingZone, Camera, DataProvenance

DEPOT = (-3.7012, 40.41745)
SYNTHETIC = DataProvenance(origin='synthetic', label='CurbOps fictional rehearsal scenario')

DELIVERIES = [
    Delivery(id='D-101', customer='Mercado San Miguel', location=(-3.7096, 40.4155), district='Centro', scheduled_minutes=42, priority='critical'),
    Delivery(id='D-102', customer='Studio Norte', location=(-3.7119, 40.4228), district='Centro', scheduled_minutes=58, priority='urgent'),
    Delivery(id='D-103', customer='Gran Vía Retail', location=(-3.7048, 40.4206), district='Centro', scheduled_minutes=35, priority='standard'),
    Delivery(id='D-104', customer='Príncipe Pío Lab', location=(-3.7184, 40.4215), district='Moncloa', scheduled_minutes=100),
    Delivery(id='D-105', customer='Chueca Supply', location=(-3.6972, 40.4229), district='Centro', scheduled_minutes=53, priority='urgent'),
    Delivery(id='D-106', customer='Alcalá Medical', location=(-3.6879, 40.4197), district='Salamanca', scheduled_minutes=88),
    Delivery(id='D-107', customer='Retiro Essentials', location=(-3.6849, 40.4148), district='Retiro', scheduled_minutes=80, priority='urgent'),
    Delivery(id='D-108', customer='Atocha Distribution', location=(-3.6948, 40.4097), district='Arganzuela', scheduled_minutes=72),
    Delivery(id='D-109', customer='Embajadores Hub', location=(-3.7027, 40.4098), district='Centro', scheduled_minutes=66),
    Delivery(id='D-110', customer='Argüelles Works', location=(-3.7168, 40.4309), district='Moncloa', scheduled_minutes=105),
    Delivery(id='D-111', customer='Recoletos Office', location=(-3.6897, 40.4243), district='Salamanca', scheduled_minutes=78),
    Delivery(id='D-112', customer='La Latina Corner', location=(-3.7102, 40.4125), district='Centro', scheduled_minutes=48),
    Delivery(id='D-113', customer='Conde Duque Atelier', location=(-3.7101, 40.4284), district='Centro', scheduled_minutes=89),
    Delivery(id='D-114', customer='Goya Pharmacy', location=(-3.6789, 40.4251), district='Salamanca', scheduled_minutes=120, priority='urgent'),
    Delivery(id='D-115', customer='Lavapiés Collective', location=(-3.7012, 40.4095), district='Centro', scheduled_minutes=74),
]
VEHICLES = [
    Vehicle(id='V-01', driver='Elena Martín', callsign='VAN 01', color='#2ADBC2', capacity=7, location=DEPOT,
            stop_ids=['D-101','D-104','D-103','D-110','D-112']),
    Vehicle(id='V-02', driver='Hugo Serrano', callsign='VAN 02', color='#FCB95A', capacity=7, location=DEPOT,
            stop_ids=['D-114','D-109','D-107','D-105','D-106']),
    Vehicle(id='V-03', driver='Carmen Gil', callsign='VAN 03', color='#AE91FF', capacity=7, location=DEPOT,
            stop_ids=['D-108','D-113','D-111','D-115','D-102']),
]
INCIDENTS = [
    Incident(id='I-901', title='Gran Vía · partial closure', location=(-3.7058,40.42035), kind='closure', severity='high',
             radius_m=330, detail='Scenario: carriageway restriction along a short section of Gran Vía.', provenance=SYNTHETIC),
    Incident(id='I-902', title='Alcalá · maintenance works', location=(-3.6903,40.4191), kind='roadworks', severity='medium',
             radius_m=210, detail='Scenario: works affecting one lane near Plaza de Cibeles.', provenance=SYNTHETIC),
    Incident(id='I-903', title='Atocha · event footprint', location=(-3.6929,40.4099), kind='event', severity='low',
             radius_m=170, detail='Scenario: temporary pedestrian event perimeter.', provenance=SYNTHETIC),
]
LOADING_ZONES = [
    LoadingZone(id='L-11',label='Calle Mayor · sample bay',location=(-3.7090,40.4157),district='Centro',provenance=SYNTHETIC),
    LoadingZone(id='L-12',label='Calle Alcalá · sample bay',location=(-3.6894,40.4200),district='Salamanca',provenance=SYNTHETIC),
    LoadingZone(id='L-13',label='Embajadores · sample bay',location=(-3.7032,40.4088),district='Centro',provenance=SYNTHETIC),
    LoadingZone(id='L-14',label='Fuencarral · sample bay',location=(-3.7028,40.4268),district='Centro',provenance=SYNTHETIC),
    LoadingZone(id='L-15',label='Serrano · sample bay',location=(-3.6871,40.4275),district='Salamanca',provenance=SYNTHETIC),
]
CAMERAS = [
    Camera(id='C-01',label='Gran Vía / Callao · mock location',location=(-3.7068,40.4204),provenance=SYNTHETIC),
    Camera(id='C-02',label='Cibeles · mock location',location=(-3.6928,40.4192),provenance=SYNTHETIC),
]
