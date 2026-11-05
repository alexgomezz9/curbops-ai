from app.integrations.madrid import parse_incidents_xml,parse_loading_geojson,parse_camera_kml,_safe_image


def test_incident_parser_handles_fixture():
    xml=b'<incidencias><incidencia><codigo>17</codigo><descripcion>Corte calle</descripcion><latitud>40.4200</latitud><longitud>-3.700</longitud></incidencia></incidencias>'
    rows=parse_incidents_xml(xml)
    assert len(rows)==1
    assert rows[0].kind=='closure'
    assert rows[0].provenance.origin=='municipal_open_data'


def test_loading_parser_only_accepts_valid_wgs84_points():
    data={'features':[{'type':'Feature','geometry':{'type':'Point','coordinates':[-3.70,40.42]},'properties':{'Direccion':'Calle Mayor'}},
                      {'type':'Feature','geometry':{'type':'Point','coordinates':[2,48]},'properties':{}}]}
    rows=parse_loading_geojson(data)
    assert len(rows)==1 and rows[0].label=='Calle Mayor'


def test_kml_camera_parsing():
    kml=b'<kml><Document><Placemark><name>Sample</name><Point><coordinates>-3.70,40.42,0</coordinates></Point></Placemark></Document></kml>'
    assert len(parse_camera_kml(kml))==1
    assert _safe_image('https://malicious.example/a.jpg') is None
