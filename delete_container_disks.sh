#! /usr/bin/bash


container_name=$1

if [[ -z $container_name ]];then
	echo "Requires the container name as argument"
	exit 1
fi

echo "Deleting $container_name"
output=$(ncli container list name=$container_name | grep -m 1 .) 
container_id=${output##*::}

vdisks=$(vdisk_config_printer -container_id=$container_id | grep ^vdisk_id | awk '{print $2}')

for vdisk in ${vdisks[@]}; do
	vdisk_info=$(vdisk_config_printer -container_id=$container_id -id=$vdisk)
	if [[ $vdisk_info =~ "to_remove" ]]; then
		continue
	else	
		echo "to_remove: true" |edit_vdisk_config -vdisk_id=$vdisk -editor="tee -a"	
	fi
done

ncli container remove name=$container_name ignore-small-files=true
