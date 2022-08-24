#!/usr/bin/python2.7
"""
Usage python apply_nutest_patch_jp.py <job_profile_name_regex> <patch_url>
set patch_url empty to remove patch urls from job profiles
"""
# nulint: disable=nulint

import sys
import requests
import time
try:
  from requests.exceptions import ConnectionError, ReadTimeout
  from requests.packages.urllib3 import disable_warnings

  disable_warnings()
except Exception:
  pass

import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(
  '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)
log.addHandler(consoleHandler)


def _send_request(method, url, session=None, payload={}):
  """
  This method is wrapper method for various requests methods like GET, POST and
    PUT.
  Args:
    method(str): http method to use.
    url(str): url to be send to requests method.
    session(requests session object): requests session object, with logged into
      JITA.
    payload(dict): payload to be send to POST, PUT method.
  Returns:
    requests response object.
  """

  if method == "GET":
    r = requests.get(url, verify=False)
  if method == "POST":
    r = session.post(url, json=payload, verify=False)
  if method == "PUT":
    r = session.put(url, json=payload, verify=False)
  return r

def get_session(username="jita", password="jita"):
  session = requests.session()
  session.post("https://jita.eng.nutanix.com/login",
               {"username": username, "password": password}, verify=False)
  return session

def update_all_job_profiles(session, job_name_regex, patch_url):
  get_job_id_url = "https://jita.eng.nutanix.com/api/v2/job_profiles?search={0}".format(
    job_name_regex)
  count = 0
  while count < 5:
    try:
      r = _send_request("GET", get_job_id_url, session=session)
      data = r.json()
      break
    except:
      count += 1
      log.info(
        "Job profile get failed, trying after 2 seconds, retry count {0}/5".format(
          count))
      time.sleep(2)
  else:
    log.info("Trying one final time.")
    r = _send_request("GET", get_job_id_url, session=session)
    data = r.json()
  jp_names_found = [jp["name"] for jp in data["data"]]
  log.info("The following job profiles will be updated. "
           "Type yes to continue. Else will be aborted !!. \n"
           "============================================================\n"
           "{}".format(
    "\n".join(jp_names_found)
  ))
  val = raw_input("yes to continue. no to exit\n")
  log.info("You have entered: {}".format(val))
  if val.lower().strip() != "yes":
    log.info("Exiting")
    sys.exit(1)
  for data_dict in data["data"]:
    update_job_profiles(session, data_dict["_id"]["$oid"], patch_url)

def update_job_profiles(session, job_profile_id, patch_url=None):
  needed_fields = [u'nutest_commit', u'resource_manager_json',
                   u'build_selection', u'requested_hardware', u'git',
                   u'cluster_selection', u'nutest_branch', u'test_sets',
                   u'services', u'infra']

  url = "https://jita.eng.nutanix.com/api/v2/job_profiles/{0}".format(
    job_profile_id)
  count = 0
  while count < 5:
    try:
      r = _send_request("GET", url, session=session)
      data_json = r.json()
      log.info("Updating job profile: {0}".format(data_json["data"]["name"]))
      break
    except:
      count += 1
      log.info(
        "job profile get failed, trying after 2 seconds, retry count {0}/5".format(
          count))
      time.sleep(2)
  else:
    log.info("Trying once final time.")
    r = _send_request("GET", url, session=session)
    data_json = r.json()
  payload = {}
  for key in data_json["data"]:
    if key in needed_fields:
      payload[key] = data_json["data"][key]

  payload["patch_url"] = patch_url
  count = 0
  while count < 5:
    try:
      r_put = _send_request("PUT", url, session=session, payload=payload)
      log.info("Job profile updated successfully.")
      break
    except:
      count += 1
      log.info(
        "job profile put failed, trying after 2 seconds, retry count {0}/5".format(
          count))
      time.sleep(2)


if __name__ == "__main__":
  jp_name = sys.argv[1]
  patch_url = None
  if len(sys.argv) > 2:
    patch_url = sys.argv[2]
  session = get_session()
  update_all_job_profiles(session, jp_name, patch_url)
