from app.models import TrafficSensor
from app.services.traffic_delta import summarize_changes

def point(id,level):
    return TrafficSensor(id=id,location=(-3.7,40.42),service_level=level)

def test_changes_requires_two_actual_snapshots():
    assert not summarize_changes([], [point('1',2)], None,'now')['available']

def test_worsening_and_improvements_are_computed_without_predictions():
    result=summarize_changes([point('1',0),point('2',3),point('3',1)],
        [point('1',3),point('2',2),point('3',1),point('4',0)], 'prior','current')
    assert result['available']
    assert result['compared_sensor_count']==3
    assert result['worsened']==1
    assert result['improved']==1
    assert result['changed'][0]['id']=='1'
    assert result['changed'][0]['delta']==3

def test_unclassified_points_are_excluded_from_comparison():
    result=summarize_changes([point('1',None)],[point('1',3)],'a','b')
    assert result['compared_sensor_count']==0
    assert result['changed']==[]
