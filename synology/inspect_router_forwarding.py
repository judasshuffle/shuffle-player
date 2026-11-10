"""Read-only UPnP inspection of the existing router's TCP-8001 rule.

Never calls AddPortMapping or DeletePortMapping. Manual/static rules may not be
visible through UPnP, so absence here does not establish their destination.
"""
import json
import socket
import time
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

GATEWAY = '192.168.68.1'


def gateway_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'http' and parsed.username is None and parsed.hostname
            and socket.gethostbyname(parsed.hostname) == GATEWAY)


def inspect():
    locations = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.settimeout(.4)
        for destination in ((GATEWAY, 1900), ('239.255.255.250', 1900)):
            message = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n'
                       'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n')
            sock.sendto(message.encode('ascii'), destination)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(16384)
            except socket.timeout:
                continue
            for line in data.decode('iso-8859-1').splitlines():
                if line.lower().startswith('location:'):
                    location = line.split(':', 1)[1].strip()
                    if gateway_url(location): locations.add(location)
    if not locations:
        print('Router did not advertise a readable UPnP description. TCP-8001 forwarding destination remains unknown.')
        return
    found = False
    for location in sorted(locations):
        with urlopen(location, timeout=4) as response:
            document = ET.fromstring(response.read(256 * 1024))
        for service in document.findall('.//{*}service'):
            kind = service.findtext('{*}serviceType', '')
            if ':WANIPConnection:' not in kind and ':WANPPPConnection:' not in kind:
                continue
            control = urljoin(location, service.findtext('{*}controlURL', ''))
            if not gateway_url(control): continue
            found = True
            action = 'GetSpecificPortMappingEntry'
            body = ('<?xml version="1.0"?>'
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                    f'<s:Body><u:{action} xmlns:u="{kind}">'
                    '<NewRemoteHost></NewRemoteHost><NewExternalPort>8001</NewExternalPort>'
                    f'<NewProtocol>TCP</NewProtocol></u:{action}></s:Body></s:Envelope>')
            request = Request(control, data=body.encode('utf-8'), headers={
                'Content-Type':'text/xml; charset="utf-8"', 'SOAPAction':f'"{kind}#{action}"'})
            try:
                with urlopen(request, timeout=4) as response:
                    result = ET.fromstring(response.read(65536))
                values = {node.tag.split('}')[-1]:node.text for node in result.iter()}
                print(json.dumps({'external_port':8001, 'protocol':'TCP',
                    'internal_client':values.get('NewInternalClient'),
                    'internal_port':values.get('NewInternalPort'), 'enabled':values.get('NewEnabled')}))
            except HTTPError as error:
                result = ET.fromstring(error.read(65536))
                codes = [node.text for node in result.iter() if node.tag.split('}')[-1] == 'errorCode']
                print('UPnP rule query returned fault', ','.join(codes) or str(error.code),
                      '; manual router rules still require inspection.')
    if not found:
        print('Router descriptions expose no readable WAN forwarding service. Destination remains unknown.')


if __name__ == '__main__':
    try:
        inspect()
    except (OSError, ET.ParseError) as error:
        print('Read-only router inspection failed:', str(error))
