#! /usr/bin/python
"""
This script collects all the VMs information metrics for each minute and gives
the average among all the collected metrics
"""
import base64
import json
import ssl
import time
import urllib2
from collections import defaultdict
import pprint

# To Change
CLUSTER_IP_ADDRESS = "10.46.202.213"  # change to localhost to run locally
MINUTES_TO_RUN = 30
LOG_FILE_NAME = "get_vm_metrics_log_15.out"
#####
#####

VM_INFO_URL = "https://{}:9440/PrismGateway/services/rest/v1/vms/".format(CLUSTER_IP_ADDRESS)
USER_NAME = "admin"
PASSWORD = "Nutanix.123"
ssl._create_default_https_context = ssl._create_unverified_context
required_Stat_fields = ['controller_num_read_iops', 'controller_num_write_iops']
required_stat_by_1000 = ["controller_io_bandwidth_kBps", "controller_avg_io_latency_usecs"]
total_fields = len(required_stat_by_1000) + len(required_Stat_fields)
request = urllib2.Request(VM_INFO_URL)
base64string = base64.b64encode('%s:%s' % (USER_NAME, PASSWORD))
request.add_header("Authorization", "Basic %s" % base64string)
total_stat = [0] * total_fields
vmStats = defaultdict(lambda: [0] * total_fields)



def sum_lists(a, b):
  return list(map(lambda a, b: a + b, a, b))


with open(LOG_FILE_NAME, "w+", buffering=0) as f:
  pretty = pprint.PrettyPrinter(width=30, stream=f)
  f.write("Start Time {}: \n".format(time.ctime()))
  for i in range(1, MINUTES_TO_RUN + 1):
    result = urllib2.urlopen(request).read()
    result_json = json.loads(result)
    entities = result_json['entities']
    # filtering the entities for powered on VMs and non CVMs
    entities = sorted(entities, key=lambda item: item["vmName"])
    entities = [entity for entity in entities if entity["powerState"] == "on" and not entity["controllerVm"]]
    total_entity_stat = [0] * total_fields
    for entity in entities:
      vm_name = entity["vmName"]
      stat_vm = [int(entity["stats"][_metric]) for _metric in required_Stat_fields] \
                + [float(entity["stats"][_metric]) / 1000 for _metric in required_stat_by_1000]
      vmStats[vm_name] = sum_lists(vmStats[vm_name], stat_vm)
      total_entity_stat = sum_lists(total_entity_stat, stat_vm)

    avg_entity_stat = [val / (len(entities)) for val in total_entity_stat]
    total_stat = sum_lists(total_stat, avg_entity_stat)
    f.write((" ".join(["#"] * 20)))
    f.write("\nIteration {}: \n".format(i))
    f.write((" ".join(["#"] * 20)))
    f.write("\nAverage Entity Stat :\n{}\n".format(avg_entity_stat))
    f.write((" ".join(["#"] * 20)))
    time.sleep(60)

  # Updating the information in VMStats to average
  for k, list in vmStats.items():
    for i in range(len(list)):
      list[i] /= MINUTES_TO_RUN

  f.write((" ".join(["#"] * 20)))
  f.write("\nVM STATISTICS\n ")
  pretty.pprint(dict(vmStats))
  f.write("\n")
  f.write((" ".join(["#"] * 20)))
  total_stat = [float(val) / MINUTES_TO_RUN for val in total_stat]
  f.write("\n{}\n".format(total_stat))
  f.write((" ".join(["#"] * 20)))
  f.write("\nEnd Time {}: \n".format(time.ctime()))

