"""Regression tests for 2026 loading GeoJSON and CSV, including realistic UTM coordinates."""
import pytest
import httpx
from pyproj import Transformer
from app.integrations import madrid


def test_parse_official_csv_utm30():
    lon,lat=-3.70,40.42
    x,y=Transformer.from_crs('EPSG:4326','EPSG:25830',always_xy=True).transform(lon,lat)
    data=f'Codigo Reserva;Gis_X;Gis_Y;Direccion;Distrito;Horario\n123;{x:.3f};{y:.3f};Calle Mayor;Centro;8 a 20\n'.encode()
    rows=madrid.parse_loading_csv(data)
    assert len(rows)==1
    assert rows[0].label=='Calle Mayor'
    assert abs(rows[0].location[0]-lon)<1e-4
    assert abs(rows[0].location[1]-lat)<1e-4
    assert rows[0].provenance.origin=='municipal_open_data'


def test_csv_rejects_outside_region():
    rows=madrid.parse_loading_csv(b'Gis_X;Gis_Y;Direccion\n0;0;Somewhere else\n')
    assert rows==[]


@pytest.mark.asyncio
async def test_geojson_falls_back_to_official_csv(monkeypatch):
    lon,lat=-3.7,40.42
    x,y=Transformer.from_crs('EPSG:4326','EPSG:25830',always_xy=True).transform(lon,lat)
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def get(self,url,headers):
            req=httpx.Request('GET',url)
            if url.endswith('.geo'):
                return httpx.Response(200,content=b'<feed xmlns="http://www.w3.org">x</feed>',headers={'Content-Type':'application/xml'},request=req)
            assert url.endswith('208072-1-carga-descarga-csv.csv')
            return httpx.Response(200,content=f'Gis_X;Gis_Y;Direccion\n{x:.3f};{y:.3f};Calle Mayor\n'.encode(),headers={'Content-Type':'text/csv'},request=req)
    monkeypatch.setattr(madrid.httpx,'AsyncClient',lambda **kwargs:FakeClient())
    rows=await madrid.fetch_source('loading')
    assert len(rows)==1
    assert rows[0].label=='Calle Mayor'
