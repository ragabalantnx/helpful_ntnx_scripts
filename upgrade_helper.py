#!/usr/bin/env python
"""
Copyright (c) 2022 Nutanix Inc. All rights reserved.
Author: ragavendran.balakris@nutanix.com
"""
# pylint: disable=invalid-name, too-many-statements, too-many-locals
# pylint: disable=line-too-long
# pylint: disable=broad-except

import argparse
import sys
from framework.interfaces.http.http import HTTP

from framework.lib.nulog import ERROR
from framework.lib.nulog import INFO
from framework.lib.nulog import set_level
from framework.lib.nulog import STEP
from workflows.systest.entities.ssh_entity.ssh_cvm import SshCvm
from workflows.systest.entities.ssh_entity.ssh_pcvm import SshPcvm

requests = HTTP()
PE_PC_BUILD_MAPPING = {
  "master": "master",
  "fraser-6.0-stable": "fraser-6.0-stable-pc-0",
  "fraser-6.6-stable": "fraser-6.6-stable-pc-1",
  "fraser-6.6.1-stable": "fraser-6.6-stable-pc-1"
}


def check_url(url, is_exit=False):
  """
  Check URL reachability
  Args:
    url(str): HTTP URL
    is_exit(boolean): If true, process exits upon unreachability.
  Returns:
    Boolean: Availability of URL.
  """
  INFO("Checking URL {}".format(url))
  status = requests.head(url, verify=False).status_code
  if status != 200:
    INFO("{} URL not reachable".format(url))
    if is_exit:
      sys.exit(1)
    return False
  return True


def get_candidate_commits(url):
  """
  Helper to get commits from an artifact commits URL
  Args:
    url(str): commits URL
  Returns:
    list: List of working commits in the url
  """
  r = requests.get(url, verify=False)
  data = r.json()
  result = data["result"]["data"]
  normalized_result = [stat for stat in result if stat.get("audit")]
  if normalized_result:
    result = normalized_result
    result.sort(key=lambda x: x["audit"][0]["date_added"]["$date"], reverse=True)
  commit_candidates = []
  check_dup = set()
  # removing the duplicates
  for commit in [val["githash"] for val in result]:
    if commit not in check_dup:
      commit_candidates.append(commit)
    check_dup.add(commit)
  return commit_candidates


def get_pc_pe_build_urls(branch, **kwargs):
  """
  Get PC pe build urls
  Args:
    branch(str): PC/NOS Branch
    kwargs(dict): Dict of keyword args
  Returns:
    dict: commit dict
  """
  max_tries = 20
  commit_dict = {}
  nos_build_url = kwargs.get('nos_build_url', None)
  pc_build_url = kwargs.get('pc_build_url', None)
  build_type = kwargs.get('build_type', None)
  pc_branch = kwargs.get('pc_branch') or PE_PC_BUILD_MAPPING.get(branch)
  if not build_type:
    build_type = "release"
  nos_tags = ""
  if branch == "master":
    nos_tags = "tags=DIAL_TEST_PASS&"
  elif build_type == "release":
    nos_tags = "tags=SMOKE_PASSED&"

  # Commit candidates
  nos_url = "https://artifact-api.eng.nutanix.com/artifacts?{2}product=aos&branch={0}&build_type={1}".format(branch, build_type, nos_tags)
  pc_url = "https://artifact-api.eng.nutanix.com/artifacts?tags=PC_SMOKE_PASSED&product=pc&branch={0}&build_type={1}".format(pc_branch, build_type)

  # bail out if URLs aren't reachable
  check_url(nos_url, is_exit=True)
  check_url(pc_url, is_exit=True)

  nos_candidates = get_candidate_commits(nos_url)
  pc_candidates = get_candidate_commits(pc_url)
  common_candidates = [commit for commit in nos_candidates if commit in pc_candidates]
  nos_commit = next(iter(nos_candidates), "")
  pc_commit = None

  # Nos Build
  if not nos_build_url:
    iter_tries = max_tries
    search_candidates_nos = common_candidates + nos_candidates
    search_candidates_nos = search_candidates_nos[:max_tries]
    nos_commit_iter = iter(search_candidates_nos)
    nos_build_url = None

    while iter_tries:
      iter_tries -= 1
      nos_commit = next(nos_commit_iter, None)
      if not nos_commit:
        INFO("None of the nos commits are reachable. Hence exiting \n{}".format("\n".join(search_candidates_nos)))
        sys.exit(1)

      nos_build_url = "http://phx-builds.corp.nutanix.com/builds/nos-builds/{0}/{1}/{2}/tar/nutanix_installer_package-{2}-{0}-{1}.tar.gz".format(branch, nos_commit, build_type)
      if check_url(nos_build_url):
        break

  if not pc_build_url:
  # PC Build
    iter_tries = max_tries
    # start with the nos commit which was reachable, then proceed with the common candidates lastly the pc candidates
    search_candidates_pc = [nos_commit] + common_candidates + pc_candidates
    search_candidates_pc = search_candidates_pc[:max_tries]
    pc_commit_iter = iter(search_candidates_pc)
    pc_build_url = None
    while iter_tries:
      iter_tries -= 1
      pc_commit = next(pc_commit_iter, None)
      if not pc_commit:
        INFO("None of the pc commits are reachable. Hence exiting \n{}".format("\n".join(search_candidates_pc)))
        sys.exit(1)
      file_name = "nutanix_installer_package_pc-{2}-{0}-{1}-x86_64.tar.gz".format(
        pc_branch, pc_commit, build_type)
      pc_build_url = "http://phx-builds.corp.nutanix.com/builds/nos-builds/{0}/{1}-PC/x86_64/{2}/tar/{3}".format(pc_branch, pc_commit, build_type, file_name)
      if check_url(pc_build_url):
        break

  commit_dict["nos_build_url"] = nos_build_url
  commit_dict["pc_build_url"] = pc_build_url
  commit_dict["commit_id"] = nos_commit
  commit_dict["pc_commit_id"] = pc_commit
  return commit_dict


def upgrade_pc(arg_object):
  """
  Method to upgrade PC cluster
  Args:
    arg_object(Object): Arg Object
  Returns:
    None
  """
  _ssh = SshPcvm(ip=arg_object.ip)
  commit = arg_object.commit
  branch = arg_object.branch
  upgrade_url = None
  if commit == "latest":
    commit_dict = get_pc_pe_build_urls(branch, build_type=arg_object.build_type)
    commit = commit_dict["pc_commit_id"]
    upgrade_url = commit_dict["pc_build_url"]

  if not upgrade_url:
    file_name = "nutanix_installer_package_pc-{2}-{0}-{1}-x86_64.tar.gz".format(
      branch, commit, arg_object.build_type)
    upgrade_url = "http://phx-eo-filer-prod-1.corp.nutanix.com/builds/nos-builds/{0}/{1}-PC/x86_64/{2}/tar/{3}".format(
      branch, commit, arg_object.build_type, file_name)
    check_url(upgrade_url, is_exit=True)

  STEP("Upgrading PC cluster: [{}] to commit: [{}]".format(arg_object.ip, commit))
  INFO("PC Cluster to be upgraded with Upgrade URL")
  INFO("COMMIT: {}".format(commit))
  INFO("URL: {}".format(upgrade_url))

  if arg_object.dryrun:
    return

  STEP("Removing old files")
  _ssh.run_cmd(cmd="/bin/rm -rf {}".format("~/install"))
  _ssh.run_cmd(cmd="/bin/rm  {}".format("~/nutanix_installer_package*"))

  STEP("Downloading Upgrade URL {}".format(upgrade_url))
  _ssh.run_cmd(cmd="wget {}".format(upgrade_url), timeout=300)
  INFO("Download complete")

  STEP("Unzipping the Tar ball")
  _ssh.run_cmd(cmd="tar -zxvf {}".format(file_name), timeout=300)
  INFO("Unzip complete")

  STEP("Removing the Tar ball")
  _ssh.run_cmd(cmd="/bin/rm {}".format(file_name))
  INFO("Remove complete")

  STEP("Upgrading PC")
  _ssh.run_cmd(cmd="source /etc/profile; /home/nutanix/install/bin/cluster -i /home/nutanix/install upgrade", timeout=3000)


def upgrade_nos(arg_object):
  """
  Method to upgrade NOS cluster
  Args:
    arg_object(Object): Arg Object
  Returns:
    None
  """
  _ssh = SshCvm(ip=arg_object.ip)
  commit = arg_object.commit
  branch = arg_object.branch
  upgrade_url = None
  if commit == "latest":
    commit_dict = get_pc_pe_build_urls(branch, build_type=arg_object.build_type)
    commit = commit_dict["commit_id"]
    upgrade_url = commit_dict["nos_build_url"]

  if not upgrade_url:
    file_name = "nutanix_installer_package-{2}-{0}-{1}.tar.gz".format(
      branch, commit, arg_object.build_type)
    upgrade_url = "http://phx-eo-filer-prod-1.corp.nutanix.com/builds/nos-builds/{0}/{1}/{2}/tar/{3}".format(
      branch, commit, arg_object.build_type, file_name)
    check_url(upgrade_url, is_exit=True)

  STEP("Upgrading NOS in cluster: [{}] to commit: [{}]".format(arg_object.ip, commit))
  INFO("Nos Cluster to be upgraded with Upgrade URL")
  INFO("COMMIT: {}".format(commit))
  INFO("URL: {}".format(upgrade_url))

  if arg_object.dryrun:
    return

  STEP("Removing old files")
  _ssh.run_cmd(cmd="/bin/rm -rf {}".format("~/install"))
  _ssh.run_cmd(cmd="/bin/rm  {}".format("~/nutanix_installer_package*"))

  STEP("Downloading Upgrade URL {}".format(upgrade_url))
  _ssh.run_cmd(cmd="wget {}".format(upgrade_url), timeout=300)
  INFO("Download complete")

  STEP("Unzipping the Tar ball")
  _ssh.run_cmd(cmd="tar -zxvf {}".format(file_name), timeout=300)
  INFO("Unzip complete")

  STEP("Removing the Tar ball")
  _ssh.run_cmd(cmd="/bin/rm {}".format(file_name))
  INFO("Remove complete")

  STEP("Upgrading NOS")
  _ssh.run_cmd(cmd="source /etc/profile; /home/nutanix/install/bin/cluster -i /home/nutanix/install upgrade", timeout=3000)

def upgrade_cluster(arg_object):
  """
  Method to upgrade the cluster to the required version
  Args:
    arg_object(Object): Arg Object
  """
  if arg_object.resource == "nos":
    upgrade_nos(arg_object)
  elif arg_object.resource == "pc":
    upgrade_pc(arg_object)
  else:
    ERROR("Upgrade can be done on either nos or pc object")


if __name__ == "__main__":
  set_level("DEBUG")
  arg_parser = argparse.ArgumentParser(
    description='Triggers the Upgrade helper arguments')

  arg_parser.add_argument('ip', help="cvm/pcvm IP where the upgrade has to be run", required=True)

  arg_parser.add_argument('--resource', help='Whether upgrade "pc" or "nos"(default)', default="nos")
  arg_parser.add_argument('--build_type', help="Release(default)or OPT build", default="release")
  arg_parser.add_argument('--build_source', help="filer(default) or nucloud", default="filer")
  arg_parser.add_argument('--commit', help="Commit to upgrade to (default: latest)", default="latest")
  arg_parser.add_argument('--branch', help="master(default) or branch", default="master")
  arg_parser.add_argument('--dryrun', help="Dryrun without upgrading", action='store_true')
  arg_list = arg_parser.parse_args()

  upgrade_cluster(arg_list)


