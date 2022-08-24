"""
Copyright (c) 2017 Nutanix Inc. All rights reserved.
Author: adam.roberts@nutanix.com
"""
# pylint: disable = broad-except,bare-except,import-error,wrong-import-position

import json
import os
import re
import sys

for path in os.listdir("/usr/local/nutanix/lib/py"):
  sys.path.insert(0, os.path.join("/usr/local/nutanix/lib/py", path))
from zeus.zookeeper_session import ZookeeperSession
from zeus.leadership import Leadership

ZK_SESSION = ZookeeperSession()

PROCESSES = {
  "Pithos": "pithos",
  "Curator": "curator",
  "InsightsDB": "insights",
  "Prism": "prism_monitor",
  "Arithmos": "arithmos",
  "Mantle": "mantle",
  "alert_manager": "alert_manager",
  "cassandra": "cassandra_monitor",
  "nfs_namespace_master": "nfs_namespace_master",
  "Zeus": "zookeeper_monitor",
  "Cerebro": "cerebro_master",
  "Castor": "castor_leader",
  "NGT": "nutanix_guest_tools_master",
  "Polaris": "polaris_master",
  "placement_solver": "placement_solver:0"
}

PY_PROCESSES = {
  "Lazan": "lazan_master",
  "Uhura": "uhura_master",
  "Ergon": "ergon_master",
  "Acropolis": "acropolis_master",
  "Microseg": "microseg_master",
  "Microsegmentation": "microsegmentation_master",
  "Genesis": "genesis_cluster_manager",
  "aplos_engine": "aplos_engine_leader",
  "cluster_config": "cluster_config_master",
  "delphi": "delphi_master",
  "catalog": "catalog_master",
  "magneto": "magneto_master",
  "flow": "flow_master",
  "kanon": "kanon_master",
  "snmp_manager": "snmp_manager",
  "minerva_cvm": "minerva_service",
  "anduril": "anduril_leadership",
  "atlas": "atlas_master",
  "cluster_health": "health_scheduler_master"
}

GO_PROCESSES = {
  "achilles": "achilles_master",
  "arjun": "arjun_master",
  "durga": "durga_master",
  "epsilon": "epsilon_master",
  "gadarz": "gadarz_master",
  "indra": "indra_master",
  "karan": "karan_master",
  "metropolis": "metropolis",
  "narad": "narad_master",
  "narsil": "Narsil",
  "network_service": "NetworkService"
}


MASTER_IPS = {}
MASTER_UUIDS = {}
GOMASTER_IPS = {}


def get_process_masters():
  """
  Get Process Masters

  Method to obtain mastership information for all of the non-Python and non-Go
  processes
  """
  for result_key, process in PROCESSES.items():
    zk_files = ZK_SESSION.list(
      '/appliance/logical/leaders/{}'.format(process))

    if not zk_files:
      continue

    for zk_file in zk_files:
      zk_val = ZK_SESSION.get(
        '/appliance/logical/leaders/{}/{}'.format(process, zk_file))

      if "Currently leader (Y/N): Yes" not in zk_val:
        continue

      if zk_val:
        MASTER_IPS.update(
          {result_key: re.findall(r'[0-9]+(?:\.[0-9]+){3}', zk_val)[0]})
        break


def get_pyprocess_masters():
  """
  Get PyProcess Masters

  Method to obtain mastership information for all of the Python processes
  """
  for result_key, zk_file in PY_PROCESSES.items():
    leadership = Leadership(zk_file, ZK_SESSION)
    master = leadership.leader_value()

    if not master:
      continue

    if result_key in ["Genesis", "snmp_manager",
                      "minerva_cvm", "cluster_health"]:
      MASTER_IPS.update({result_key: master})
    else:
      MASTER_UUIDS.update({result_key: master})


def get_goprocess_masters():
  """
  Get GoProcess Masters

  Method to obtain mastership information for all of the Go processes
  """
  for result_key, goproc in GO_PROCESSES.items():
    zk_files = ZK_SESSION.list(
      '/appliance/logical/goleaders/{}'.format(goproc))

    if not zk_files:
      continue

    for zk_file in zk_files:
      zk_val = ZK_SESSION.get(
        '/appliance/logical/goleaders/{}/{}'.format(goproc, zk_file))

      try:
        master = json.loads(zk_val)['ip']
      except ValueError:
        master = zk_val.split(':')[0]

      if goproc in ["Narsil"]:
        MASTER_UUIDS.update({result_key: master})
      else:
        MASTER_IPS.update({result_key: master})
      break


def get_master_data():
  """
  Get Master Data

  Handles the ThreadPoolExecutor for running all process mastership
  collections.  Assembles and prints the obtained data.
  """

  get_process_masters()
  get_pyprocess_masters()
  get_goprocess_masters()

  result = {}
  result["cvm_ips"] = MASTER_IPS
  result["host_uuids"] = MASTER_UUIDS

  backplane_ip_flag = any(not backplaneip.startswith('10.') for process,
                          backplaneip in result["cvm_ips"].items())
  if backplane_ip_flag:
    if get_backplane_network_segment_status() == "Enabled":
      backplane_mgmt_ip_mapping = get_backplane_mgmt_ip_mapping()
      result["cvm_ips"].update({process: backplane_mgmt_ip_mapping[
        backplaneip] \
                                for process, backplaneip in
                                result["cvm_ips"].items() if
                                not backplaneip.startswith('10.')})
  print json.dumps(result)


def get_backplane_mgmt_ip_mapping():
  """
  Get backplane management ip mapping

  Returns:
    dict of cvmips with corresponding backplaneips.
  """
  backplane_ip_mapping_dict = {}
  cmd = 'svmips 2>&1'
  cvmips = (os.popen(cmd).read()).split()
  for cvm in cvmips:
    cmd = 'ssh %s "/sbin/ifconfig eth2 | grep -i "inet' % cvm
    try:
      out = os.popen(cmd).read()
      backplane_ip = re.search(r'inet\s+([\d\.]+)\s+', out)
      backplane_ip_mapping_dict[backplane_ip.group(1)] = cvm
    except Exception as exc:
      print "Getting eth0 ip encounted exception: {}".format(exc)

  return backplane_ip_mapping_dict

def get_backplane_network_segment_status():
  """
  Gets the backplane network segment status

  Returns:
    Enabled(str): if the network segment backplane is enabled
  """
  cmd = 'network_segment_status --last_task 2>&1'
  out = os.popen(cmd).read()
  if re.search(r"Network Segmentation is currently enabled for "
               r"backplane", out):
    return 'Enabled'

get_master_data()

