#!/usr/bin/network python
# -*- coding: utf-8 -*-
'''

.. _module_mc_network:

mc_network / network registry
============================================

If you alter this module and want to test it, do not forget
to deploy it on minion using::

  salt '*' saltutil.sync_modules

Documentation of this module is available with::

  salt '*' sys.doc mc_network

'''
# Import python libs
import logging
import mc_states.utils
import re
from salt.utils.odict import OrderedDict

__name = 'network'

log = logging.getLogger(__name__)


def sort_ifaces(infos):
    a = infos[0]
    key = a
    if re.match('^(eth0)', key):
        key = '100___' + a
    if re.match('^(eth[123456789][0123456789]+\|em|wlan)', key):
        key = '200___' + a
    if re.match('^(lxc\|docker)', key):
        key = '300___' + a
    if re.match('^(veth\|lo)', key):
        key = '900___' + a
    return key


def get_broadcast(dn, ip):
    '''Get a server broadcase
    ipsubnet.255
    '''
    num = '255'
    gw = '.'.join(ip.split('.')[:-1] + [num])
    return gw


def get_netmask(dn, ip):
    '''Get a server netmask
    default to ipsubnet.255
    '''
    netmask = '255.255.255.0'
    return netmask


def get_gateway(dn, ip):
    '''Get a server gateway
    default to ipsubnet.254
    except for online where the gw == ipsubnet.1
    '''
    num = '254'
    if 'online-' in dn:
        num = '1'
    gw = '.'.join(ip.split('.')[:-1] + [num])
    return gw


def get_dnss(dn, ip):
    '''Get server dnss
    '''
    defaults = ['127.0.0.1', '8.8.8.8', '4.4.4.4']
    if 'ovh-' in dn:
        defaults.insert(1, '213.186.33.99')
    if 'online-' in dn:
        defaults.insert(1, '62.210.16.6')
        defaults.insert(1, '62.210.16.7')
    return ' '.join(defaults)


def get_fo_netmask(dn, ip):
    '''Get netmask for an ip failover
    '''
    netmask = '255.255.255.255'
    return netmask


def get_fo_broadcast(dn, ip):
    '''Get broadcast for an ip failover
    '''
    broadcast = ip
    return broadcast


def settings():
    '''
    network registry

    networkManaged
        Do we manage the network configuration
    interfaces
        Dict of configuration for network interfaces
    main_ip
      main server ip
    hostname
      main hostname
    domain
      main domain
    devhost_ip
      devhost ip
    '''
    @mc_states.utils.lazy_subregistry_get(__salt__, __name)
    def _settings():
        saltmods = __salt__
        grains = __grains__
        pillar = __pillar__
        data = {'interfaces': {}, 'ointerfaces': []}
        grainsPref = 'makina-states.localsettings.'
        providers = __salt__['mc_provider.settings']()
        # Does the network base config file have to be managed via that
        # See makina-states.localsettings.network
        # Compat for the first test!
        data['networkManaged'] = (
            saltmods['mc_utils.get']('makina-states.network_managed', False)
            or saltmods['mc_utils.get'](grainsPref + 'network.managed', False))

        # ip managment
        default_ip = None
        ifaces = grains['ip_interfaces'].items()
        ifaces.sort(key=sort_ifaces)
        devhost_ip = None
        forced_ifs = {}
        devhost = __salt__['mc_nodetypes.registry']()['is']['devhost']
        for iface, ips in ifaces:
            if ips:
                if not default_ip:
                    default_ip = ips[0]
                if (iface == 'eth1') and devhost:
                    devhost_ip = ips[0]
                if providers['have_rpn'] and (iface in ['eth1', 'em1']):
                    # configure rpn with dhcp
                    forced_ifs[iface] = {}
        if not default_ip:
            default_ip = '127.0.0.1'
        # hosts managment via pillar
        data['makinahosts'] = makinahosts = []
        # main hostname
        domain_parts = grains['id'].split('.')
        data['devhost_ip'] = devhost_ip
        data['main_ip'] = saltmods['mc_utils.get'](
            grainsPref + 'main_ip', default_ip)
        data['hostname'] = saltmods['mc_utils.get'](
            grainsPref + 'hostname', domain_parts[0])
        default_domain = ''
        if len(domain_parts) > 1:
            default_domain = '.'.join(domain_parts[1:])
        data['domain'] = saltmods['mc_utils.get'](
            grainsPref + 'domain', default_domain)
        data['fqdn'] = saltmods['mc_utils.get']('nickname', grains['id'])
        if data['domain']:
            data['makinahosts'].append({
                'ip': '{main_ip}'.format(**data),
                'hosts': '{hostname} {hostname}.{domain}'.format(**data)
            })
        data['hosts_list'] = hosts_list = []
        for k, edata in pillar.items():
            if k.endswith('makina-hosts'):
                makinahosts.extend(edata)
        # -loop to create a dynamic list of hosts based on pillar content
        for host in makinahosts:
            ip = host['ip']
            for dnsname in host['hosts'].split():
                hosts_list.append(ip + ' ' + dnsname)
        netdata = saltmods['mc_utils.defaults'](
            'makina-states.localsettings.network', data)
        # retro compat
        for imapping in netdata['ointerfaces']:
            for ikey, idata in imapping.items():
                ifname = idata.get('ifname', ikey)
                iconf = netdata['interfaces'].setdefault(ifname, {})
                iconf.update(idata)
        netdata['interfaces'].update(forced_ifs)
        for ifc, data in netdata['interfaces'].items():
            data.setdefault('ifname', ifc)
        # get the order configuration
        netdata['interfaces_order'] = [a for a in netdata['interfaces']]
        return netdata
    return _settings()


def dump():
    return mc_states.utils.dump(__salt__,__name)

#
# -*- coding: utf-8 -*-
__docformat__ = 'restructuredtext en'

# vim:set et sts=4 ts=4 tw=80:
