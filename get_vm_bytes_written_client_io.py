#! /usr/bin/python
"""
Copyright (c) 2021 Nutanix Inc. All rights reserved.
Authors: ragavendran.balakris@nutanix.com

This script gets the bytes written by vms.
usage: python get_vm_bytes_written_client_io.py vm_name_1, vm_name_2 ..
"""
# pylint: disable=too-many-locals,import-error, too-many-statements
# nulint: disable=ImportsValidator

import sys
import os
import base64
import json
import platform
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VdiskNode(object):
  """
  Class for holding vdisk data retrieved using `vdisk_config_printer`
  """
  # Required values from Vdisk Config Printer
  vdisk_vars = ["vdisk_id", "vdisk_name", "nfs_file_name"]

  def __init__(self, vdisk_info):
    """
    Constructor for vdisk class

    Args:
      vdisk_info(dict): vdisk information obtained from vdisk_config_printer
      for a each vdisk

    """
    self.nfs_file_name = None
    for var in self.vdisk_vars:
      value = vdisk_info.get(var)
      if value:
        self.__dict__[var] = value
      else:
        self.__dict__[var] = None


def get_vdisk_config():
  """
  Gets a list vdisk configs from vdisk config printer. Each vdisk config is a
  dict

  Returns:
    list of parsed vdisk configs in the form of dict.
  """
  cmd = "source /etc/profile; /usr/local/nutanix/bin/vdisk_config_printer"
  output = os.popen(cmd).read().strip()
  vdisk_info_list = output.split("\n\n")
  config_list = []
  vdisk_nfs_map = {}
  for vdisk_info in vdisk_info_list:
    config = {}
    config_list.append(config)
    for line in vdisk_info.split("\n"):
      if ": " in line:
        key, val = line.split(": ", 1)
        config[key.strip()] = val.strip().strip('"')

  for config in config_list:
    vdisk_node = VdiskNode(config)
    vdisk_nfs_map[vdisk_node.nfs_file_name] = vdisk_node
  return vdisk_nfs_map


def get_json_content(url):
  """
  Helper function to get the json content of the specified URL.

  Args:
    url(str): URL to which the json data has to be loaded from.

  Returns:
    dict: dict of the json response
  """
  import requests
  user_name = "admin"
  pass_word = "Nutanix.123"
  base64string = base64.b64encode('%s:%s' % (user_name, pass_word))
  headers = {'Authorization': "Basic %s" % base64string,
             "Content-Type": "application/json"}

  response = requests.get(url=url, headers=headers, verify=False)
  return json.loads(response.content)


def get_reachable_ips(ip_list):
  """
  Get reachable ip addresses from a given list of ip. The list of reachable
  ips are returned.

  Args:
    ip_list(list<str>): The list of IP addresses
  Returns:
    ip_list(list<str>): The list of IP addresses that are pingable.
  """
  reachable_ips = []
  suppress_str = " > /dev/null 2>&1 "
  for ip in ip_list:
    ping_str = "-n 1" if platform.system().lower() == "windows" else "-c 1"
    retry = 0
    while retry < 3:
      result = os.system("ping " + ping_str + suppress_str + " " + ip) == 0
      if result:
        reachable_ips.append(ip)
        break
      retry = retry + 1
      ping_str = "-n 1" if platform.system().lower() == "windows" else "-c 3"
  return reachable_ips


def stats_from_counters_cli():
  """
  Gets the counters_cli stats and returns a map of vdisk id to the counter
  stats.

  Returns:
    dict of stats collected using `counters_cli`
  """
  svm_ips = os.popen("svmips").read().split()
  svm_ips = get_reachable_ips(svm_ips)

  # Reading the stats of the vdisks and saving for later context
  counters_stats_cmd = "ssh {} 'source /etc/profile; " \
                       "counters_cli read --component stargate --family vdisk'"\
                       " 2> /dev/null"
  stats_output = {}
  for ip in svm_ips:
    counters_stats = os.popen(counters_stats_cmd.format(ip)).read().strip()
    # the first line is timestamp (which has to be removed)
    counters_stats = counters_stats.split("\n", 1)[-1]
    counters_stats = counters_stats.replace("\n", "")
    stats_json = json.loads(counters_stats)
    counter_vdisk_stats = stats_json.get('vdisks')
    for vdisk_stat in counter_vdisk_stats:
      stats_output[str(vdisk_stat.get('vdisk_id'))] = vdisk_stat
  return stats_output


def get_write_bytes(vdisk_stat):
  """
  Parse the output returned for vdisk in `stats_from_counters_cli` and
  give the required params needed for output

  Args:
    vdisk_stat(dict): dict of counter cli stat for a vdisk
  Returns:
    Int of the write bytes
  """
  write_bytes = 0
  if vdisk_stat:
    write_bytes = vdisk_stat['raw']['write_bytes']
  return int(write_bytes)


# Main function
def main():
  """
  Main function which prints the vdisk stats for the vms.

  Returns:
    None
  """
  svm_ip_cmd = "source /etc/profile; hostname -I | awk '{print $1}'"
  svm_ip = os.popen(svm_ip_cmd).read().strip()
  vm_list_url = "https://{}:9440/api/nutanix/v2.0/vms?" \
                "include_vm_disk_config=true".format(svm_ip)

  vm_name_list = None
  if len(sys.argv) > 1:
    vm_name_list = sys.argv[1]
    vm_name_list = vm_name_list.split(",")

  # Reading the stats across all the vdisks
  counter_cli_stats = stats_from_counters_cli()
  vdisk_config_map = get_vdisk_config()

  # Reading the VM, Vdisk APIs and saving the data
  response_json = get_json_content(vm_list_url)
  vm_data = [{"vm_uuid": vm.get("uuid"),
              "vm_disk_info": vm.get("vm_disk_info")}
             for vm in response_json['entities']
             if not vm_name_list or vm.get("name") in vm_name_list]

  vm_bytes_data = {}

  for vm_info in vm_data:
    vm_uuid = vm_info["vm_uuid"]
    vm_bytes_data[vm_uuid] = 0

    for vdisk in vm_info["vm_disk_info"]:
      vdisk_uuid = vdisk.get("disk_address", {}).get("vmdisk_uuid")
      vdisk_config = vdisk_config_map.get(vdisk_uuid)
      if not vdisk_config:
        continue
      vdisk_id = vdisk_config.vdisk_id
      vm_bytes_data[vm_uuid] += get_write_bytes(counter_cli_stats.get(
        vdisk_id, {}))

  print json.dumps(vm_bytes_data, indent=4)


main()
