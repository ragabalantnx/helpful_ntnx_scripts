#!/bin/bash
#
# Check help_function below for more info on how to use the script.
#

AD_USERNAME=`whoami`

generate_post_data() {
  cat <<EOF
  {
    "name": "Static IPs for $AD_USERNAME:$CLUSTER_NAME",
    "retry": 1,
    "duration": 96,
    "resource_specs": [
      {
        "image_resource": false,
        "name": "$CLUSTER_NAME",
        "static_ips": [
          {
            "num_ips": 5
          }
        ],
        "is_new": false,
        "set_external_data_services_ip_address": false,
        "set_cluster_external_ip_address": false,
        "type": "\$NOS_CLUSTER",
        "resources": {
          "entries": [
            {
              "type": "\$NOS_CLUSTER",
              "name": "$CLUSTER_NAME"
            }
          ],
          "type": "static_resources",
          "infra": {
            "kind": "ON_PREM"
          }
        }
      }
    ],
    "expand_links": false,
    "tags": [],
    "lock_scheduled_deployment": false
  }
EOF
}

request_static_ips() {
  echo Invoking command: curl -u \$AD_USERNAME -k -X POST --header \
   "Content-Type: application/json" --header "Accept: application/json" \
   -d "$(generate_post_data)" "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments"
  OUTPUT=`curl -u $AD_USERNAME -k -X POST --header "Content-Type: application/json" --header "Accept: application/json" -d "$(generate_post_data)" "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments"`
  SCHEDULED_DEPLOYMENT_ID=`echo $OUTPUT | python  -c "import sys, json; print json.load(sys.stdin)['id']"`
  if [[ $? -ne 0 ]]; then
    echo "Error occurred making POST request to deploy static IPs for cluster $CLUSTER_NAME."
    echo "$OUTPUT"
    exit 1
  fi

  echo Invoking command: curl -k -X GET "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments/$SCHEDULED_DEPLOYMENT_ID"
  OUTPUT=`curl -k -X GET "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments/$SCHEDULED_DEPLOYMENT_ID"`
  DEPLOYMENT_ID=`echo $OUTPUT | python -c "import sys,json; print json.load(sys.stdin)['data']['deployments'][0]['\\$oid']"`

  printf "\n\n"
  echo "SCHEDULED_DEPLOYMENT_ID: $SCHEDULED_DEPLOYMENT_ID"
  echo "Deployment ID: $DEPLOYMENT_ID"

  wait_for_deployment_to_succeed $SCHEDULED_DEPLOYMENT_ID
}

wait_for_deployment_to_succeed() {
  SCHEDULED_DEPLOYMENT_ID=$1

  RETRY_COUNT=30
  while [[ $RETRY_COUNT -gt 0 ]];
  do
    echo "Waiting for the scheduled deployment $SCHEDULED_DEPLOYMENT_ID to complete.."
    OUTPUT=`curl --silent --show-error -k -X GET "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments/$SCHEDULED_DEPLOYMENT_ID"`
    if [[ ! -z $(echo $OUTPUT | grep '"status": "SUCCESS"') ]]; then
      echo "Scheduled Deployment $SCHEDULED_DEPLOYMENT_ID succeeded"
      break
    elif [[ ! -z $(echo $OUTPUT | grep '"status": "FAILED"') ]]; then
      echo "Scheduled Deployment $SCHEDULED_DEPLOYMENT_ID failed with"
      echo `echo $OUTPUT | python -c "import sys,json; print json.load(sys.stdin)['data'].get('message')"`
      exit 1
    fi
    (( RETRY_COUNT-- ))
    sleep 30
  done

  if [[ $RETRY_COUNT -eq 0 ]]; then
    echo "Timed out waiting for $SCHEDULED_DEPLOYMENT_ID to succeed."
    echo "Rerun the script with '-d <Scheduled Deployment ID>' option once the deployment succeeds."
    exit 1
  else
    pe_setup_managed_network $SCHEDULED_DEPLOYMENT_ID
  fi
}

pe_setup_managed_network() {
  SCHEDULED_DEPLOYMENT_ID=$1

  OUTPUT=`curl -k -X GET "https://rdm.eng.nutanix.com/api/v1/scheduled_deployments/$SCHEDULED_DEPLOYMENT_ID"`
  # In case of failure, the output has "\n" characters which json.load doesn't
  # understand so need to convert stdin to string and remove "\n".
  IS_SUCCESS=`echo $OUTPUT | python -c "import sys,json; print json.loads(sys.stdin.read().replace('\n', ''))['success']"`

  # Comparing with True instead of true because python changes true from True in
  # the json output.
  [[ $IS_SUCCESS == "True" ]] || (echo "Failed to fetch scheduled deployment for"\
    "$SCHEDULED_DEPLOYMENT_ID. Error: $OUTPUT." && exit 1)

  DEPLOYMENT_ID=`echo $OUTPUT | python -c "import sys,json; print json.load(sys.stdin)['data']['deployments'][0]['\\$oid']"`

  OUTPUT=`curl -k https://rdm.eng.nutanix.com/api/v1/deployments/$DEPLOYMENT_ID`
  # In case of failure, the output has "\n" characters which json.load doesn't
  # understand so need to convert stdin to string and remove "\n".
  IS_SUCCESS=`echo $OUTPUT | python -c "import sys,json; print json.loads(sys.stdin.read().replace('\n', ''))['success']"`

  echo "Fetched data from:"
  echo "SCHEDULED_DEPLOYMENT_ID: $SCHEDULED_DEPLOYMENT_ID"
  echo "DEPLOYMENT_ID: $DEPLOYMENT_ID"
  echo ""

  # Comparing with True instead of true because python changes true from True in
  # the json output.
  [[ $IS_SUCCESS == "True" ]] || (echo "Failed to fetch deployment for"\
    "$DEPLOYMENT_ID. Error: $OUTPUT." && exit 1)

  STATIC_IP_ADDRESSES=`echo $OUTPUT | tr ',' '\n' | grep ipaddress | awk '{print $2}' | tr -d '"'`
  echo "Static IP addresses: $STATIC_IP_ADDRESSES"

  # Get the SVM IP. In case of multi-node PE, get the first SVMIP using head -1.
  ANY_SVM_IP=`echo $OUTPUT | tr ',' '\n' | grep '^\s*"svm_ip"' | awk '{print $2}' | tr -d '"' | head -1`
  echo "Random SVM IP address: $ANY_SVM_IP"

  # Get the Gateway IP
  GATEWAY_IP=`echo $OUTPUT | tr ',' '\n' | grep gateway | head -1 | awk '{print $2}' | tr -d '"'`
  echo "Gateway: $GATEWAY_IP"

  # Get the Network IP Prefix
  NETWORK_PREFIX=`echo $OUTPUT | tr ',' '\n' | grep \"network\" | tail -1 | awk '{print $2}' | tr -d '"'`
  echo "Network Prefix: $NETWORK_PREFIX"

  # Get the Netmask
  NETMASK=`echo $OUTPUT | tr ',' '\n' | grep netmask | tail -1 | awk '{print $2}' | tr -d '"'`
  echo "NETMASK: $NETMASK"

  ACLI="/usr/local/nutanix/bin/acli"

  if [ ! -f /tmp/ntnx_ssh_keys_dir/nutanix ]; then
    wget -P /tmp/ntnx_ssh_keys_dir/ http://10.41.24.49:9000/ssh_keys/nutanix
    chmod 600 /tmp/ntnx_ssh_keys_dir/nutanix
  fi

  SSH_CMD="ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i /tmp/ntnx_ssh_keys_dir/nutanix nutanix@$ANY_SVM_IP"

  VLAN_ID=`echo $($SSH_CMD $ACLI -o json net.list) | python -c "import sys,json; print json.load(sys.stdin)['data'][0]['id']"`
  echo "vlan ID to be used for creation of subnet: $VLAN_ID"

  SUBNET_NAME="sub1"
  # Create the net.
  $SSH_CMD $ACLI net.create $SUBNET_NAME vlan=$VLAN_ID ip_config=$GATEWAY_IP/$NETMASK
  echo "Subnet $SUBNET_NAME created."

  OUTPUT=`cat /etc/resolv.conf | grep -i nameserver | awk '{print $2}'`
  DNS_SERVER_IPS=`echo $OUTPUT | tr ' ' ','`

  $SSH_CMD $ACLI net.update_dhcp_dns $SUBNET_NAME servers=$DNS_SERVER_IPS
  echo "DNS Server IPs $DNS_SERVER_IPS added to the subnet."

  for IP in $STATIC_IP_ADDRESSES ; do
    $SSH_CMD $ACLI net.add_dhcp_pool $SUBNET_NAME start=$IP end=$IP
  done
  echo "Static IP Addresses $STATIC_IP_ADDRESSES added to the pool of subnet $SUBNET_NAME."
}

help_function() {
cat << EOF

Run this script from your Dev VM. This script can request static IP resources
and/or setup a managed network. This script uses "whoami" as username to make
RDM calls. If you want to use some other user name then manually edit the
AD_USERNAME field in this script.

Script usage:
    To request static IP resources and setup a managed network, use -c.
    If static IP resources are requested and just managed network needs to be setup, use -d.
    Use either -c or -d. If both are used, only -d will be considered.
    As part of requesting static IP resources, request to RDM will be made so RDM password will need to be entered.

Example usage:       
    sh rdm_request_static_ips_and_setup_managed_network.sh -c <JARVIS cluster name>
    sh rdm_request_static_ips_and_setup_managed_network.sh -d <Scheduled Deployment ID>
EOF
exit 0
}

while getopts "c:d:u:h" opt
do
   case "$opt" in
      c ) CLUSTER_NAME="$OPTARG" ;;
      d ) SCHEDULED_DEPLOYMENT_ID="$OPTARG" ;;
      u ) AD_USERNAME="$OPTARG" ;;
      h ) help_function ;;
      ? ) help_function ;; # Print help_function in case parameter is non-existent
   esac
done

if [[ ! -z $SCHEDULED_DEPLOYMENT_ID ]]; then
  pe_setup_managed_network $SCHEDULED_DEPLOYMENT_ID
elif [[ ! -z $CLUSTER_NAME ]]; then
  request_static_ips $CLUSTER_NAME
else
  help_function
fi
