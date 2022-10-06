#!/usr/bin/env python
"""
Copyright (c) 2022 Nutanix Inc. All rights reserved.
Author: ragavendran.balakris@nutanix.com
"""
# pylint: disable=invalid-name, no-member, line-too-long, broad-except

import argparse

import time
from framework.lib.nulog import set_level
from framework.entities.cluster.nos_cluster import NOSCluster
from framework.lib.nulog import INFO

if __name__ == "__main__":
  set_level("DEBUG")
  arg_parser = argparse.ArgumentParser(
    description='Mount containers to a CVM')

  arg_parser.add_argument('cluster', help="cvm name/IP")
  arg_object = arg_parser.parse_args()
  cluster_obj = NOSCluster(cluster=arg_object.cluster)

  iterations = 100
  sleep_secs = 20

  for iter in range(1, iterations+1):
    INFO("Iteration : {}".format(iter))
    for svm in cluster_obj.svms:
      INFO("Restart Cerebro in {}".format(svm.ip))
      svm.execute("source /etc/profile; genesis stop Cerebro && cluster start")
      INFO("Sleeping for {}".format(sleep_secs))
      time.sleep(sleep_secs)
