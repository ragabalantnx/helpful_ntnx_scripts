#! /usr/bin/python
"""
"""
import base64
import json
import ssl
import time
import urllib2
from collections import defaultdict
import pprint
import requests
import logging
import pprint
import sys
import datetime
from paramiko import SSHClient

# These two lines enable debugging at httplib level (requests->urllib3->http.client)
# You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# The only thing missing will be the response.body which is not logged.
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
#http_client.HTTPConnection.debuglevel = 1

# You must initialize logging, otherwise you'll not see debug output.
#logging.basicConfig()
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True

PE_IP_ADDRESS = sys.argv[1]
PC_IP_ADDRESS = sys.argv[2]
SEARCH_TERM = sys.argv[3]

ssh = SSHClient()
ssh.load_system_host_keys()
ssh.connect(PE_IP_ADDRESS,22,"nutanix","nutanix/4u")

VM_LIST_URL = "https://{}:9440/api/nutanix/v2.0/vms?filter=vm_name%3D%3D{}".format(PE_IP_ADDRESS, SEARCH_TERM)
USER_NAME = "admin"
PASSWORD = "Nutanix.123"
base64string = base64.b64encode('%s:%s' % (USER_NAME, PASSWORD))
headers = {'Authorization' : "Basic %s" % base64string, "Content-Type" : "application/json"}
vm_list_response = requests.get(url = VM_LIST_URL, headers = headers, verify = False)
response_json = json.loads(vm_list_response.content)

vm_data = []

for vm in response_json['entities']:
  vm_data_entry = {
    "vm_name" : vm.get('name'),
    "vm_uuid" : vm.get('uuid')
  }
  vm_data.append(vm_data_entry)

vm_ips = []
vm_create_rp_url = "https://{}:9440/api/dataprotection/v4.0.a2/config/recovery-points".format(PC_IP_ADDRESS)
vm_rp_name_map = {}
for entry in vm_data:
  vm_name = entry.get('vm_name')
  print "create rp for {}".format(vm_name)
  uuid = entry.get('vm_uuid')
  timestamp = int(time.time() * 1000000)
  rp_name = "rp_{}_{}".format(vm_name,timestamp)
  rp_create_payload = {
    "name": rp_name,
    "recoveryPointType": "CRASH_CONSISTENT",
    "vmReferenceList": [uuid]
  }
  vm_create_rp_response = requests.post(url = vm_create_rp_url, headers = headers, verify = False, data = json.dumps(rp_create_payload))
  if vm_create_rp_response.status_code == 202:
    print "created recovery point for vm {}".format(vm_name)
    vm_rp_name_map.update({vm_name : rp_name})

print vm_rp_name_map

rp_names = vm_rp_name_map.values()

time.sleep(90)

vm_rp_list_url = "https://{}:9440/api/dataprotection/v4.0.a2/config/recovery-points".format(PC_IP_ADDRESS)
vm_list_rp_response = requests.get(url = vm_rp_list_url, headers = headers, verify = False)
all_rp_list = json.loads(vm_list_rp_response.content).get('data')
vm_rp_uuid_list = []

for rp in all_rp_list:
  rp_name = rp.get('name')
  if rp_name in rp_names:
    vm_rp_uuid_list.append(rp.get('extId'))


# Get AZ UUID
az_list_url = "https://{}:9440/api/nutanix/v3/availability_zones/list".format(PC_IP_ADDRESS)
az_payload = {"kind": "availability_zone"}
az_list_response = requests.post(url = az_list_url, headers = headers, verify = False, data = json.dumps(az_payload))
all_az_list = json.loads(az_list_response.content).get('entities')
target_az = all_az_list[1]
target_az_uuid = target_az.get('metadata').get('uuid')

time.sleep(10)

# Replicate RPs
for rp_uuid in vm_rp_uuid_list:
  vm_rp_replicate_url = "https://{}:9440/api/dataprotection/v4.0.a2/config/recovery-points/{}/$actions/replicate".format(PC_IP_ADDRESS, rp_uuid)
  replicate_payload = {
    "targetAvailabilityZoneId": target_az_uuid
  }
  vm_rp_replicate_response = requests.post(url = vm_rp_replicate_url, headers = headers, verify = False, data = json.dumps(replicate_payload))
  if vm_rp_replicate_response.status_code == 202:
    print "Replicated recovery point {}".format(rp_uuid)
  
