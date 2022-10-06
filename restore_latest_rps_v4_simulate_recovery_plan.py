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
import re
import numpy as np
from framework.entities.cluster.nos_cluster import NOSCluster
from framework.entities.cluster.prism_central_cluster import PrismCentralCluster
from workflows.systest.lib.ltss_aos_helper import get_entity_rp_map_ltss

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

PC_IP_ADDRESS = sys.argv[1]
LTSS_IP = sys.argv[2]
vm_regex = sys.argv[3]
try:
  PRINT_ONLY = sys.argv[4]
except IndexError:
  PRINT_ONLY = "false"

USER_NAME = "admin"
PASSWORD = "Nutanix.123"
base64string = base64.b64encode('%s:%s' % (USER_NAME, PASSWORD))
headers = {'Authorization' : "Basic %s" % base64string, "Content-Type" : "application/json"}

pc_cluster = PrismCentralCluster(cluster=PC_IP_ADDRESS)

# Fetch latest RPs for all top-level RPs in LTSS
vm_rp_map_ltss = get_entity_rp_map_ltss(ltss_ip=LTSS_IP)
for vm_uuid, rps in vm_rp_map_ltss.iteritems():
  vm_rp_map_ltss[vm_uuid] = sorted(rps, key=lambda x: x["creation_time"], reverse=True)

latest_rps = []
for vm_uuid, rps in vm_rp_map_ltss.iteritems():
  latest_rps.append(rps[0])

rps_to_restore = []
for rp in latest_rps:
  entity_name = rp.get('live_entity_list')[0].get('name')
  if re.search(r'^%s' % vm_regex, entity_name):
    rps_to_restore.append(rp.get('uuid'))

print rps_to_restore

batches = 5

PRINT_ONLY = 'false'
if PRINT_ONLY != "print_only":
  # Issue restore for the requested rps
  rps_in_batches = np.array_split(rps_to_restore, batches)
  for rp_list in rps_in_batches:
    for rp in rp_list:
      RESTORE_V4_URL = "https://{}:9440/api/dataprotection/v4.0.a2/config/recovery-points/{}/$actions/restore".format(PC_IP_ADDRESS,rp)
      request_response = requests.post(url = RESTORE_V4_URL, headers = headers, verify = False)
      response_json = json.loads(request_response.content)
#      print response_json
      print "Submitted restore request for {}".format(rp)
    print "Sleep after submitting {} requests".format(len(rp_list))
    print "Sleeping for 50 secs"
    time.sleep(50)
