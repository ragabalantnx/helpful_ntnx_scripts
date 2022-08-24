"""
Copyright (c) 2022 Nutanix Inc. All rights reserved.
Author: ragavendran.balakris@nutanix.com
"""
# pylint: disable=invalid-name
# nulint: disable=ImportsValidator
import sys
import requests
from collections import defaultdict
try:
  from requests.exceptions import ConnectionError, ReadTimeout
  from requests.packages.urllib3 import disable_warnings
  disable_warnings()
except Exception:
  pass
RDM_GET_DEPLOYMENT_URL = ("http://rdm.eng.nutanix.com/api/v1/"
                          "scheduled_deployments/%s?expand=deployments")
PE_CLUSTER = "$NOS_CLUSTER"
PC_CLUSTER = "$PRISM_CENTRAL"
LTSS = "$LTSS"


def get_allocated_resource_details(deployment_id):
  """
  Fetches the allocated resource details from RDM.

  Args:
    deployment_id(str): The deployment id in string.

  """

  rdm_get_url = RDM_GET_DEPLOYMENT_URL % deployment_id
  rdm_get_resp = requests.get(rdm_get_url, verify=False)
  rdm_json = rdm_get_resp.json()
  output_str = []
  resource_str = []
  resource_map = defaultdict(int)
  for resource in rdm_json["data"]["deployments"]:
    if resource["type"] == PE_CLUSTER:
      output_str.append(
        "NOS:{}".format(resource["allocated_resource"]["name"]))
      resource_map[PE_CLUSTER] += 1
      resource_str.append("PE_{} : {}".format(
        resource_map[PE_CLUSTER], resource["allocated_resource"]["svm_ip"]))
    if resource["type"] == PC_CLUSTER:
      output_str.append("PC:{}".format(resource["allocated_resource"]["ip"]))
      resource_map[PC_CLUSTER] += 1
      resource_str.append("PC_{} : {}".format(
        resource_map[PC_CLUSTER], resource["allocated_resource"]["ip"]))

    if resource["type"] == LTSS:
      output_str.append("LTSS:{}".format(
        resource["allocated_resource"]["host"]))
      resource_map[LTSS] += 1
      resource_str.append("LTSS_{} : {}".format(
        resource_map[LTSS], resource["allocated_resource"]["host"]))

  output_str = " ".join(output_str)
  print("\nNutest Resource String:")
  print("\n" +
       "*" * len(output_str) + "\n" +
       output_str +
       "\n" +
       "*" * len(output_str) + "\n"
       )

  print("\nResource IP information:")
  print("\n" +
       "*" * 50 + "\n" +
       "\n".join(resource_str) +
       "\n" +
       "*" * 50 + "\n"
       )

if __name__ == "__main__":
  deploy_id = sys.argv[1]
  get_allocated_resource_details(deploy_id)
