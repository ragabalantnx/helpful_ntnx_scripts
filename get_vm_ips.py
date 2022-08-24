#! /usr/bin/python
"""
This script collects all the VMs information metrics for each minute and gives
the average among all the collected metrics
"""
import base64
import json
import ssl
import urllib2
import sys
import re
from collections import defaultdict

args = sys.argv

# To Change

CLUSTER_IP_ADDRESS = args[1] if len(args) > 1 else "localhost"
VM_NAME_PATTERNS = args[2].split(",") if len(args) > 2 else []
IP_PATTERN = args[3] if len(args) > 3 else "10.*"
#####

VM_INFO_URL = "https://{}:9440/PrismGateway/services/rest/v1/vms/".format(CLUSTER_IP_ADDRESS)
USER_NAME = "admin"
PASSWORD = "Nutanix.123"
ssl._create_default_https_context = ssl._create_unverified_context
request = urllib2.Request(VM_INFO_URL)
base64string = base64.b64encode('%s:%s' % (USER_NAME, PASSWORD))
request.add_header("Authorization", "Basic %s" % base64string)

result = urllib2.urlopen(request).read()
result_json = json.loads(result)
entities = result_json['entities']
# filtering the entities for powered on VMs and non CVMs
entities = sorted(entities, key=lambda item: item["vmName"])
entities = [entity for entity in entities if
            entity["powerState"] == "on" and not entity["controllerVm"]]

vm_ip_list = defaultdict(list)
for entity in entities:
  ip_list = None
  for vm_name in VM_NAME_PATTERNS:
    if re.search(vm_name, entity["vmName"]):
      ip_list = vm_ip_list[vm_name]
      ips = entity["ipAddresses"]
      ip_list.append([str(ip) for ip in ips if re.search(IP_PATTERN, ip)][0])
      break

for key, ip_list in vm_ip_list.items():
  print(key+" : ")
  print(" ".join(ip_list))
