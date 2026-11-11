"""Read-only deployment verification; no authorized station mutations."""
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from owner_request import signed_request

PUBLIC='http://shuffle.tplinkdns.com:8001'
LAN='http://192.168.68.81:8094'

def read(request):
    with urlopen(request,timeout=45) as response: return response.status,response.read()

def status(request,expected):
    try: actual,body=read(request)
    except HTTPError as error: actual,body=error.code,error.read()
    assert actual==expected,(getattr(request,'full_url',request),actual,expected)
    return body

owner=json.loads(status(signed_request(PUBLIC,'/api/dj',{'action':'state'}),200))
assert owner['can_control'] and 'control_token' not in owner
private_key=(Path(__file__).parent/'secrets/owner-key').read_bytes().strip()
for path,file in [('/dr-screen',None),('/dr-screen-entity.js','dr-screen-entity.js'),
                  ('/dr-screen.js','dr-screen.js'),('/dr-dj.js','dr-dj.js'),
                  ('/dr-remote', 'dr-remote.html'),('/dr-remote.js','dr-remote.js'),('/sha256.js','sha256.js')]:
    body=status(PUBLIC+path,200)
    assert private_key not in body, 'Private key leaked in public asset'
    if file: assert hashlib.sha256(body).digest()==hashlib.sha256((Path(__file__).parent/file).read_bytes()).digest()
    else:
        assert body.count(b'<audio')==1 and b'src="/stream.mp3"' in body
        assert b'/station.js' not in body
    print('Public HTTP 200:',PUBLIC+path)
with urlopen(PUBLIC+'/',timeout=15) as response:
    assert response.url==PUBLIC+'/dr-screen'
for path in ['/app.js','/station.js','/api/search','/api/shuffle','/api/styles']:
    status(PUBLIC+path,403)
for path in ['/secrets/owner-key','/install-owner-remote.js','/compose.yaml']:
    status(PUBLIC+path,404)
visitor=json.loads(status(PUBLIC+'/api/station',200))
assert visitor['can_control'] is False and 'control_token' not in visitor and 'queue' not in visitor
for action in ['play','append','shuffle','next']:
    body=json.dumps({'action':action,'query':'Bob Dylan','owner':True,'username':'Dan'}).encode()
    status(Request(PUBLIC+'/api/dj',data=body,headers={'Content-Type':'application/json'}),403)
status(Request(LAN+'/api/station/control',data=b'{"action":"next"}',headers={'Content-Type':'application/json'}),403)
status(Request(PUBLIC+'/api/station/control',data=b'{"action":"next"}',headers={'Content-Type':'application/json'}),403)
request=signed_request(PUBLIC,'/api/dj',{'action':'state'})
status(request,200);status(request,403)
result=json.loads(status(signed_request(PUBLIC,'/api/dj',{'action':'search','query':'play 70s Bob Dylan'}),200))
assert result['tracks'] and all('id' in track for track in result['tracks'])
after=json.loads(status(signed_request(PUBLIC,'/api/dj',{'action':'state'}),200))
assert [t['id'] for t in owner['queue']]==[t['id'] for t in after['queue']]
assert len(status(LAN+'/',200))>5000
print('Signed owner state/search passed; unsigned, forged-owner, replay and legacy mutations denied.')
print('LAN dashboard private; queue unchanged; no credential returned or printed.')
