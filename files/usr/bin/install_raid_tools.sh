#!/usr/bin/env bash
RELEASE="wheezy"
#if [ "x$(lsb_release --id 2>/dev/null|grep -q Ubuntu;echo $?)" = "x0" ];then
#    RELEASE="precise"
#fi

do_aptget() {
    export UCF_FORCE_CONFFOLD=1
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y --force-yes\
        -o Dpkg::Options::="--force-confold" \
        mdadm\
        3ware-status\
        tw-cli\
        3dm2\
        aacraid-status\
        arcconf\
        hrconf\
        cciss-vol-status\
        hpacucli\
        megaraid-status\
        megactl\
        megamgr\
        dellmgr\
        megaclisas-status\
        megacli\
        megaide-status\
        megaide-spyd\
        mpt-status\
        lsiutil\
        sas2ircu\
        sas2ircu-status
        #adaptec-universal-storage-snmpd\
        #adaptec-universal-storage-mib\
        #adaptec-storage-manager-agent\
        #adaptec-storage-manager-common\

}
install_debian() {
    if [ "x$(grep -q "hwraid.le-vert.net" $(find /etc/apt/sources.list* -type f);echo ${?})" != "x0" ];then
        if [ ! -e /etc/apt/sources.list.d/ ];then
            mkfir /etc/apt/sources.list.d/
        fi
        echo "deb http://hwraid.le-vert.net/debian ${RELEASE} main" >> /etc/apt/sources.list.d/hwraid.list
    fi
    if [ "x$(apt-key list|grep -q le-ver;echo $?)" = "x0" ];then
        wget -O - http://hwraid.le-vert.net/debian/hwraid.le-vert.net.gpg.key | sudo apt-key add -
    fi
    do_aptget
    if [ "x$?" != "x0" ];then
        apt-get update > /dev/null
        do_aptget
    fi
    for i in /etc/default/sas2ircu-statusd\
         /etc/default/aacraid-statusd\
         /etc/default/3ware-statusd\
         /etc/default/cciss-vol-statusd\
         /etc/default/megaide-statusd\
         /etc/default/megaraid-statusd\
         /etc/default/sas2ircu-statusd\
         /etc/default/aacraid-statusd\
         /etc/default/megaclisas-statusd\
         /etc/default/megaraidsas-statusd\
         /etc/default/mpt-statusd;do
        if [ ! -e ${i} ];then
cat > "${i}" << EOF
RUN_DAEMON=no
EOF
        ${i//default/init.d} stop
        update-rc.d -f $(basename $i) remove
        fi
    done
}

if test -e /etc/debian_version;then
    install_debian
fi
