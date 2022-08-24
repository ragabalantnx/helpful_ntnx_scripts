#!/bin/sh

## This snapclones a given base vdisk into multiple number of clones
# arg1 : base_vdisk to be snapclonned [ Format /ctnr_name/vdisk_name ] 
# arg2: the clone name to be used after snapclonning
# arg3: The number of snapclones required



TIMESTAMP=`date +"%Y%m%d_%H%M%S"`
base_vdisk=${1:-""}
base_clone_name=${2:-"disk_${TIMESTAMP}_"}
number_snap_clones=${3:-1}

IFS='/' read -ra vdisk_vals <<< "$base_vdisk"

if [ ${#vdisk_vals[@]} -le 1 ]; then
    echo "Vdisk passed should be of format /container_name/vdisk_name"
    exit
fi
container_name=${vdisk_vals[1]}

echo "creating clones of disk : $base_vdisk"
echo "The created clone disks will have prefix : $base_clone_name"
echo "The number of snap clones that will be created is : $number_snap_clones"



for i in `seq $number_snap_clones` ; do
    snap_clone="ncli snap clone src-file=$base_vdisk dest-files=/${container_name}/${base_clone_name}_${i}"
    echo "Executing command $snap_clone"
    $snap_clone
done

