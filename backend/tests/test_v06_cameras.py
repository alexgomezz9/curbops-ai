"""Regression tests: real municipal KML image URLs, proxy security and 2026 loading resource."""
from fastapi.testclient import TestClient
from app.main import app
from app.store import store
from app.integrations.madrid import (SOURCES,_safe_image,parse_camera_kml,parse_loading_geojson)
from app.models import Camera,DataProvenance
import httpx
import pytest

KML=b'''<?xml version="1.0"?><kml><Document><Placemark>
<name>PLAZA TEST</name><Point><coordinates>-3.701,40.421,0</coordinates></Point>
<description><![CDATA[<img src=http://informo.munimadrid.es/cameras/Camara01301.jpg?v=17315>]]></description>
</Placemark></Document></kml>'''

def test_parses_documented_municipal_image_urls():
    items=parse_camera_kml(KML)
    assert len(items)==1
    assert items[0].image_url=='http://informo.munimadrid.es/cameras/Camara01301.jpg?v=17315'
    assert items[0].provenance.origin=='municipal_open_data'

def test_no_arbitrary_image_proxy_urls():
    assert _safe_image('http://127.0.0.1/local.jpg') is None
    assert _safe_image('http://169.254.169.254/latest.jpg') is None
    assert _safe_image('https://informo.madrid.es.evil.com/img.jpg') is None
    assert _safe_image('https://informo.madrid.es:444/secret.jpg') is None
    assert _safe_image('https://informo.madrid.es/image.svg') is None
    assert _safe_image('https://informo.madrid.es/images.jpg')

def test_loading_geojson_url_is_official_2026_resource():
    assert SOURCES['loading']['url'].endswith('/208072-0-carga-descarga-geo.geo')
    assert 'datos.madrid.es' in SOURCES['loading']['url']


def test_snapshot_endpoint_requires_loaded_camera():
    c=TestClient(app)
    response=c.get('/api/cameras/C-M000/snapshot')
    assert response.status_code==404


def test_snapshot_endpoint_uses_fixed_camera_image(monkeypatch):
    import app.main as m
    c=TestClient(app)
    with store.lock:
        original=store.override_cameras
        store.override_cameras=[Camera(id='C-M001',label='test',location=(-3.7,40.42),image_url='https://informo.madrid.es/cameras/Camara001.jpg',provenance=DataProvenance(origin='municipal_open_data',label='Ayuntamiento'))]
    async def fake_get(url):
        assert url.endswith('Camara001.jpg')
        return b'\xff\xd8\xff\xe0', 'image/jpeg', False
    monkeypatch.setattr(m,'camera_snapshot',fake_get)
    try:
        response=c.get('/api/cameras/C-M001/snapshot')
        assert response.status_code==200
        assert response.headers['content-type']=='image/jpeg'
        assert response.content.startswith(b'\xff\xd8')
    finally:
        with store.lock:store.override_cameras=original

@pytest.mark.asyncio
async def test_camera_image_proxy_rejects_html_payload(monkeypatch):
    from app.services import camera_images as ci
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def get(self,url,headers):
            return httpx.Response(200,content=b'<html>not a camera</html>',request=httpx.Request('GET',url),headers={'Content-Type':'image/jpeg'})
    monkeypatch.setattr(ci.httpx,'AsyncClient',lambda **kwargs:FakeClient())
    with pytest.raises(ValueError, match='JPEG or PNG'):
        await ci.camera_snapshot('https://informo.madrid.es/cameras/Camara55555.jpg')

@pytest.mark.asyncio
async def test_camera_image_proxy_rejects_off_host_redirect(monkeypatch):
    from app.services import camera_images as ci
    class FakeClient:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def get(self,url,headers):
            return httpx.Response(302,headers={'Location':'http://127.0.0.1/secret.jpg'},request=httpx.Request('GET',url))
    monkeypatch.setattr(ci.httpx,'AsyncClient',lambda **kwargs:FakeClient())
    with pytest.raises(ValueError,match='redirected outside'):
        await ci.camera_snapshot('https://informo.madrid.es/cameras/Camara55556.jpg')
