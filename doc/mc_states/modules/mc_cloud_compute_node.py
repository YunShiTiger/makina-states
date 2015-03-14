#!/usr/bin/env python
'''
.. _module_mc_cloud_compute_node:

mc_cloud_compute_node / cloud compute node related functions
==============================================================



'''

__docformat__ = 'restructuredtext en'
# Import python libs
import logging
import copy
import random
import os
from mc_states.utils import memoize_cache
import msgpack
import mc_states.utils
from salt.utils.odict import OrderedDict
import msgpack.exceptions
from salt.utils.pycrypto import secure_password
import msgpack.exceptions
try:
    import netaddr
    HAS_NETADDR = True
except ImportError:
    HAS_NETADDR = False

from mc_states import api

__name = 'mc_cloud_compute_node'

log = logging.getLogger(__name__)

VIRT_TYPES = {'docker': {'supported': False},
              'xen': {'supported': False},
              'openvz': {'supported': False},
              'lxc': {'supported': True},
              'kvm': {'supported': True}}
_RP = 'reverse_proxies'
_SW_RP = 'shorewall_reverse_proxies'
_CUR_API = 2
_default = object()
PREFIX = 'makina-states.cloud.compute_node'


def get_all_vts(supported=None):
    '''
    Get makina-states.cloud VTS

        * supported=None: all
        * supported=True: supported vt
        * supported=False: unsupported vt
    '''
    vts = copy.deepcopy(VIRT_TYPES)
    if supported is not None:
        for i in [a
                  for a in vts
                  if vts[a].get('supported') != supported]:
            vts.pop(i, None)
    return vts


def get_vts(supported=True):
    '''
    Alias to get_all_vts
    At the difference of supported is True by default
    '''
    return get_all_vts(supported=supported)


def default_settings():
    '''
    Default compute node settings

    target
        target minion id

    all_vms
        contain compute node vms on compute node
        contain all vms on controller
        A mapping indexed by vm minion ids and containing some info::

           {vm name: virt type}

    all_targets
        a mapping indexed by target minions ids
        containing either only the compute node on compute node
        all the compute nodes on controller
    vms
        vms on compute node or empty dict

    targets
        a mapping indexed by target minions ids containing also vms and
        supported vt

    reverse_proxies
        mapping of reverse proxies info

    domains
        list of domains served by host

    vts
        a list of supported virt types (lxc)

    has
        global configuration toggle

        firewall
            global firewall toggle

    ssh_port_range_start
        from where we start to enable ssh NAT ports.
        Default to 40000.

    ssh_port_range_end

        from where we end to enable ssh NAT ports.
        Default to 50000.

    Basically the compute node needs to:

        - setup reverse proxying
        - setup it's local internal addressing dns to point to private ips
        - everything else that's local to the compute node

    The computes nodes are often created implicitly by registration of vms
    on specific drivers like LXC but you can register some manually.

    makina-states.cloud.compute_node.settings.targets.devhost11.local: {}

    To add or modify a value, use the mc_utils.default habitual way of
    modifying the default dict.
    '''
    target = __grains__['id']
    data = {'has': {'firewall': True},
            'target': target,
            'vms': OrderedDict(),
            'domains': [],
            'vts': [],
            'ssl_certs': [],
            'http_port': 80,
            'https_port': 443,
            'reverse_proxies': default_reverse_proxy(target),
            'ssh_port_range_start': 40000,
            'ssh_port_range_end': 50000,
            'snmp_port_range_start': 30000,
            'snmp_port_range_end': 39999}
    return data


def get_targets(vt=None, ttl=30):
    '''
    Return all vms indexed by targets
    '''
    def _do(vt=None):
        data = OrderedDict()
        cloudSettings = __salt__['mc_cloud.extpillar_settings']()
        vm_confs = __salt__['mc_pillar.get_cloud_conf_by_vts']()
        dvts = [a for a in VIRT_TYPES if cloudSettings.get(a)]
        for cvt in dvts:
            all_vt_infos = vm_confs.get(cvt, {})
            for t in all_vt_infos:
                target = data.setdefault(t, {})
                vts = target.setdefault('vts', [])
                vms = target.setdefault('vms', {})
                if cvt not in vts:
                    vts.append(cvt)
                if vt and (vt != cvt):
                    continue

                for vmname in all_vt_infos[t]['vms']:
                    vms.setdefault(vmname, {'vt': cvt, 'target': t})
        return data
    cache_key = 'mc_cloud_cn.get_targets{0}'.format(vt)
    return copy.deepcopy(memoize_cache(_do, [vt], {}, cache_key, ttl))


def get_vms(vt=None, vm=None, ttl=30):
    '''
    Returns vms indexed by name
    '''
    def _do(vt, vm):
        _targets = get_targets(vt=vt)
        rdata = {}
        for target, tdata in _targets.items():
            for tvm, vmdata in tdata['vms'].items():
                rdata[tvm] = vmdata
        if vm:
            rdata = rdata[vm]
        _targets = get_targets(vt=vt)
        return rdata
    cache_key = 'mc_cloud_cn.get_vm{0}{1}'.format(vt, vm)
    return memoize_cache(_do, [vt, vm], {}, cache_key, ttl)


def get_vm(vm, ttl=30):
    def _do(vm):
        try:
            return get_vms(vm=vm)
        except KeyError:
            raise KeyError('{0} vm not found'.format(vm))
    cache_key = 'mc_cloud_cn.get_vm{0}'.format(vm)
    return memoize_cache(_do, [vm], {}, cache_key, ttl)


def target_for_vm(vm, target=None, ttl=30):
    '''
    Get target for a vm
    '''
    def _do(vm, target=None):
        return get_vm(vm)['target']
    cache_key = 'mc_cloud_cn.target_for_vm{0}{1}'.format(vm, target)
    return memoize_cache(_do, [vm, target], {}, cache_key, ttl)


def vt_for_vm(vm, target=None):
    '''
    Get VT for a vm
    '''
    return get_vm(vm)['vt']


def get_vms_for_target(target, vt=None):
    '''
    Return all vms for a target
    '''
    return get_targets(vt=vt).get(target, {}).get('vms', {})


def get_targets_and_vms_for_vt(vt):
    _s = __salt__
    data = get_targets(vt=vt)
    for cn in [a for a in data]:
        if not data[cn]['vms']:
            data.pop(cn, None)
    return data


def get_vms_per_type(target):
    '''
    Return all vms indexed by vt for a special target
    '''
    all_targets = OrderedDict()
    for vt in VIRT_TYPES:
        per_type = all_targets.setdefault(vt, set())
        all_infos = get_targets_and_vms_for_vt(vt)
        for vmname in all_infos.get(target, {}).get('vms', []):
            per_type.add(vmname)
    for i in [a for a in all_targets]:
        all_targets[i] = [a for a in all_targets[i]]
    return all_targets


def _encode(value):
    '''encode using msgpack backend'''
    return msgpack.packb({'value': value})


def _fencode(filep, value):
    '''
    Encode in a file using msgpack backend
    '''
    dfilep = os.path.dirname(filep)
    if not os.path.exists(dfilep):
        os.makedirs(dfilep)
    with open(filep, 'w') as fic:
        fic.write(_encode(value))
    try:
        os.chmod(filep, 0700)
    except:
        pass


def _decode(filep):
    '''decode in a file using msgpack backend'''
    value = None
    try:
        if os.path.exists(filep):
            with open(filep) as fic:
                rvalue = fic.read()
                value = msgpack.unpackb(rvalue)['value']
    except msgpack.exceptions.UnpackValueError:
        log.error('decoding error, removing stale {0}'.format(filep))
        os.unlink(filep)
        value = None
    return value


def del_conf_for_target(target, setting):
    '''Register a specific setting for a specific target'''
    target = target.replace('.', '')
    cloudSettings = __salt__['mc_cloud.extpillar_settings']()
    filep = os.path.join(cloudSettings['compute_node_pillar_dir'],
                         target, 'settings',
                         setting + '.pack')
    if os.path.exists(filep):
        os.unlink(filep)


def set_conf_for_target(target, setting, value):
    '''Register a specific setting for a specific target'''
    target = target.replace('.', '')
    cloudSettings = __salt__['mc_cloud.extpillar_settings']()
    filep = os.path.join(cloudSettings['compute_node_pillar_dir'],
                         target, 'settings',
                         setting + '.pack')
    _fencode(filep, value)
    return value


def get_conf_for_target(target, setting, default=None):
    '''get the stored specific setting for a specific target'''
    target = target.replace('.', '')
    cloudSettings = __salt__['mc_cloud.extpillar_settings']()
    filep = os.path.join(cloudSettings['compute_node_pillar_dir'],
                         target, 'settings', setting + '.pack')
    value = default
    if os.path.exists(filep):
        value = _decode(filep)
    return value


def set_conf_for_vm(vm, setting, value, target=None):
    if target is None:
        target = target_for_vm(vm)
    target = target.replace('.', '')
    vm = vm.replace('.', '')
    cloudSettings = __salt__['mc_cloud.extpillar_settings']()
    filep = os.path.join(cloudSettings['compute_node_pillar_dir'],
                         target, 'vms', vm, 'settings',
                         setting + '.pack')
    _fencode(filep, value)
    return value


def get_conf_for_vm(vm, setting, default=None, target=None):
    '''.'''
    if target is None:
        target = target_for_vm(vm)
    target = target.replace('.', '')
    vm = vm.replace('.', '')
    cloudSettings = __salt__['mc_cloud.extpillar_settings']()
    filep = os.path.join(cloudSettings['compute_node_pillar_dir'],
                         target, 'vms', vm, 'settings', setting + '.pack')
    value = default
    if os.path.exists(filep):
        value = _decode(filep)
    return value


def find_mac_for_vm(vm, default=None, target=None):
    '''
    Generate and assign a mac addess to a specific
    vm on a specific host
    '''
    if target is None:
        target = target_for_vm(vm)
    mac = get_conf_for_vm(vm, 'mac', target=target)
    if not mac:
        mac = default
    if not mac:
        mac = gen_mac()
        if not mac:
            raise Exception(
                'Error while setting grainmac for {0}/{1}'.format(target, vm))
        set_conf_for_vm(vm, 'mac', mac, target=target)
    return mac


def find_password_for_vm(vm, default=None, pwlen=32, target=None):
    '''
    Return the vm password after creating it
    the first time
    '''
    if target is None:
        target = target_for_vm(vm)
    password = get_conf_for_vm(vm, 'password', target=target)
    if not password:
        password = default
    if not password:
        password = secure_password(pwlen)
        if not password:
            raise Exception('Error while setting password '
                            'grain for {0}/{1}'.format(target, vm))
    return password


def _construct_ips_dict(target):
    allocated_ips = get_conf_for_target(target, 'allocated_ips')
    sync = False
    if (allocated_ips is None) or (not isinstance(allocated_ips, dict)):
        allocated_ips = {}
    for k in ['api', 'ips']:
        if k not in allocated_ips:
            sync = True
    allocated_ips.setdefault('api', _CUR_API)
    allocated_ips.setdefault('ips', {})
    if sync:
        set_conf_for_target(target, 'allocated_ips', allocated_ips)
    return allocated_ips


def get_allocated_ips(target):
    '''
    Get the allocated ips for a specific target
    '''
    allocated_ips = _construct_ips_dict(target)
    return allocated_ips


def remove_allocated_ip(target, ip, vm=None):
    '''
    Remove any ip from the allocated IP registry.
    If vm is specified, it must also match a vm
    which is allocated to this ip
    '''
    sync = False
    all_ips = get_allocated_ips(target)
    if ip in all_ips['ips'].values():
        for i in [a for a in all_ips['ips']]:
            if all_ips['ips'][i] == ip:
                if vm is not None and vm == i:
                    continue
                del all_ips['ips'][i]
                sync = True
    if sync:
        set_conf_for_target(target, 'allocated_ips', all_ips)
    return get_allocated_ips(target)['ips']


def find_ip_for_vm(vm,
                   default=None,
                   network=api.NETWORK,
                   netmask=api.NETMASK,
                   target=None):
    '''
    Search for:

        - an ip already allocated
        - an random available ip in the range

    To get and maybe allocate an ip for a vm call

        find_ip_for_vm(target, vmname)

    For force/set an ip use::

        set_allocated_ip(target, vmname, '1.2.3.4')

    '''
    if target is None:
        target = target_for_vm(vm)
    if not HAS_NETADDR:
        raise Exception('netaddr required for ip generation')
    allocated_ips = get_allocated_ips(target)
    ip4 = None
    vmdata = get_vms()[vm]
    vt = vmdata.get('vt', None)
    if vt:
        try:
            ip4 = get_conf_for_vm(vm, 'ip4', target=target)
        except msgpack.exceptions.UnpackValueError:
            ip4 = None
    if not ip4:
        ip4 = default
    if not ip4:
        # get network bounds
        network = netaddr.IPNetwork('{0}/{1}'.format(network, netmask))
        # converts stringued ips to IPAddress objects
        all_ips = allocated_ips['ips'].values()
        for try_ip in network[2:-2]:  # skip the firsts and last for gateways
            parts = try_ip.bits().split('.')
            stry_ip = "{0}".format(try_ip)
            if (
                stry_ip in all_ips  # already allocated
            ) or (
                parts[-1] in ['00000000', '11111111']  # 10.*.*.0 or 10.*.*.255
            ):
                continue
            else:
                ip4 = stry_ip
                break
            raise Exception('Did not get an available ip in the {2} network'
                            ' for {0}/{1}'.format(target, vm, vt))
        set_conf_for_vm(vm, 'ip4', ip4, target=target)
    if not ip4:
        raise Exception('Did not get an available ip for {0}/{1}'.format(
            target, vm))
    cur_ip = allocated_ips['ips'].get(vm)
    if ip4 and (ip4 != cur_ip):
        allocated_ips['ips'][vm] = ip4
        set_conf_for_target(target, 'allocated_ips', allocated_ips)
    return ip4


def set_allocated_ip(vm, ip, target=None):
    '''
    Allocate an ip for a vm on a compute node for a specific vt

    >>> set_allocated_ip(target, vmname, '2.2.3.4')

    '''
    if target is None:
        target = target_for_vm(vm)
    allocated_ips = get_allocated_ips(target)
    allocated_ips['ips'][vm] = ip
    set_conf_for_vm(vm, 'ip4', ip, target=target)
    set_conf_for_target(target, 'allocated_ips', allocated_ips)
    return get_allocated_ips(target)


def domains_for(target, domains=None):
    _s = __salt__
    if domains is None:
        domains = []
    vms = get_vms_per_type(target)
    for vt, vm_ids in vms.items():
        for vm in vm_ids:
            domains = _s['mc_cloud_vm.domains_for'](vm, domains=domains)
    domains = _s['mc_utils.uniquify']([target] + domains)
    return domains


def gen_mac():
    return ':'.join(map(lambda x: "%02x" % x, [0x00, 0x16, 0x3E,
                                               random.randint(0x00, 0x7F),
                                               random.randint(0x00, 0xFF),
                                               random.randint(0x00, 0xFF)]))


def default_reverse_proxy(target):
    data = OrderedDict([('target', target),
                        ('sw_proxies', []),
                        ('http_proxy', OrderedDict()),
                        ('http_backends', OrderedDict()),
                        ('https_proxy', OrderedDict()),
                        ('https_backends', OrderedDict())])
    return data


def _get_next_available_port(ports, start, stop):
    for i in range(start, stop + 1):
        if i not in ports:
            return i
    raise ValueError('mc_compute_node: No more available ssh port in'
                     '{0}:{1}'.format(start, stop))


def get_kind_port(vm, target=None, kind='ssh'):
    _s = __salt__
    if target is None:
        target = __salt__['mc_cloud_compute_node.target_for_vm'](vm)
    _settings = _s['mc_cloud_compute_node.cn_extpillar_settings'](target)
    start = int(_settings[kind + '_port_range_start'])
    end = int(_settings[kind + '_port_range_end'])
    kind_map = get_conf_for_target(target, kind + '_map', {})
    for a in [a for a in kind_map]:
        kind_map[a] = int(kind_map[a])
    port = kind_map.get(vm, None)
    if port is None:
        port = _get_next_available_port(kind_map.values(), start, end)
        _s['mc_cloud_compute_node.set_kind_port'.format(kind)](
            vm, port, target=target, kind=kind)
    return port


def set_kind_port(vm, port, target=None, kind='ssh'):
    if target is None:
        target = __salt__['mc_cloud_compute_node.target_for_vm'](vm)
    kind_map = get_conf_for_target(target, kind + '_map', {})
    if kind_map.get(vm, None) != port:
        kind_map[vm] = port
        set_conf_for_target(target, kind + '_map', kind_map)
    return get_conf_for_target(target, kind + '_map', {}).get(vm, None)


def set_ssh_port(vm, port, target=None):
    return set_kind_port(vm, port, target=target, kind='ssh')


def get_ssh_port(vm, target=None):
    return get_kind_port(vm, target=target, kind='ssh')


def set_snmp_port(vm, port, target=None):
    return set_kind_port(vm, port, target=target, kind='snmp')


def get_snmp_port(vm, target=None):
    return get_kind_port(vm, target=target, kind='snmp')


def default_has(vts=None, **kwargs):
    if vts is None:
        vts = {}
    for vt in VIRT_TYPES:
        vts.setdefault(vt, bool(kwargs.get(vt, False)))
    return vts


def _add_server_to_backends(reversep, frontend, backend_name, domain, ip):
    '''The domain is ppurely informative here'''
    _s = __salt__
    kind = 'http'
    if ' ssl ' in frontend['bind']:
        kind = 'https'
    _backends = reversep['{0}_backends'.format(kind)]
    bck = _backends.setdefault(backend_name, OrderedDict())
    default_raw_opts = [
        'balance roundrobin',
        #'source 0.0.0.0 usesrc clientip'
    ]
    # for now rely on settings xforwardedfor header
    if reversep['{0}_proxy'.format(kind)].get(
        'http_proxy_mode', 'xforwardedfor'
    ) == 'xforwardedfor':
        # retry to enable full chain keepalive setups
        # default_raw_opts.append('option http-server-close')
        default_raw_opts.append('option http-keep-alive')
        default_raw_opts.append('option forwardfor')
    bck = _s['mc_utils.dictupdate']({'name': backend_name,
                                     'raw_opts': [],
                                     'servers': []}, bck)
    srv = {'name': 'srv_{0}{1}'.format(domain, len(bck['servers']) + 1),
           'bind': '{0}:80'.format(ip),
           'opts': 'check'}
    [bck['raw_opts'].append(a)
     for a in default_raw_opts if a not in bck['raw_opts']]
    bck['raw_opts'].sort(key=lambda x: x)
    if srv['bind'] not in [a.get('bind') for a in bck['servers']]:
        bck['servers'].append(srv)
    _backends[backend_name] = bck
    return reversep


def _configure_http_reverses(reversep, domain, ip):
    # http
    http_proxy = reversep['http_proxy']
    https_proxy = reversep['https_proxy']
    dom_id = domain.replace('*', 'star')
    backend_name = 'bck_{0}'.format(dom_id)
    sbackend_name = 'securebck_{0}'.format(dom_id)
    if domain.startswith('*.'):
        rule = 'acl host_{0} hdr_end(host) -i {1}'.format(dom_id, domain[2:])
    else:
        rule = 'acl host_{0} hdr(host) -i {0}'.format(dom_id)
    if rule not in http_proxy['raw_opts']:
        http_proxy['raw_opts'].insert(0, rule)
        https_proxy['raw_opts'].insert(0, rule)
    rule = 'use_backend {1} if host_{0}'.format(dom_id, backend_name)
    if rule not in http_proxy['raw_opts']:
        http_proxy['raw_opts'].append(rule)
    # https
    sslr = 'http-request set-header X-SSL %[ssl_fc]'
    if sslr not in https_proxy['raw_opts']:
        https_proxy['raw_opts'].insert(0, sslr)
    rule = 'use_backend {1} if host_{0}'.format(dom_id, sbackend_name)
    if rule not in https_proxy['raw_opts']:
        https_proxy['raw_opts'].append(rule)
    _add_server_to_backends(reversep, http_proxy, backend_name, dom_id, ip)
    _add_server_to_backends(reversep, https_proxy, sbackend_name, dom_id, ip)
    return reversep


def default_http_proxy(target,
                       proxy_mode=None,
                       ssl=False,
                       port=None,
                       ssl_certs=None,
                       **kw):
    if proxy_mode is None:
        proxy_mode = 'xforwardedfor'
    name = target
    extra_bind = ''
    if ssl:
        scheme = 'https'
        extra_bind += ' ssl'
        if not port:
            port = 443
        if ssl_certs:
            wildcard = __salt__['mc_ssl.get_wildcard'](target)
            # We must serve the compute node SSL certificate as the default one
            # search a wildcard
            if wildcard and wildcard in [a[0] for a in ssl_certs]:
                first_cert = wildcard
            # else for the precise domain of the compute node
            elif target in [a[0] for a in ssl_certs]:
                first_cert = target
            # error if we couldnt get any case
            else:
                raise ValueError('No such cert for compute node'
                                 ' {0}'.format(target))
            extra_bind += (' crt /etc/ssl/cloud/certs/{0}.crt'
                           ' crt /etc/ssl/cloud/certs').format(first_cert)
    else:
        scheme = 'http'
        if not port:
            port = 80
    data = {'name': '{0}-{1}'.format(scheme, name),
            'mode': 'http',
            'http_proxy_mode': proxy_mode,
            'bind': '*:{0}{1}'.format(port, extra_bind),
            'raw_opts_pre': [],
            'raw_opts_post': [],
            'raw_rules_done': False,
            'raw_opts': []}
    return data


def default_https_proxy(*args, **kw):
    kw.setdefault('ssl', True)
    return default_http_proxy(*args, **kw)


def _init_http_proxies(data,
                       port=None,
                       ssl_port=None,
                       proxy_mode=None,
                       ssl_certs=None):
    for k in ['http', 'https']:
        port = {'http': port, 'https': ssl_port}[k]
        key = '{0}_proxy'.format(k)
        h = __salt__['mc_utils.dictupdate'](
            default_http_proxy(data['target'],
                               proxy_mode=proxy_mode,
                               ssl=k == 'https',
                               ssl_certs=ssl_certs,
                               port=port),
            data[key])
        data[key] = h
    return data


def feed_http_reverse_proxy_for_target(target_data):
    '''
    Get reverse proxy information mapping for a specicific target
    This return a useful mappings of infos to reverse proxy http
    and ssh services with haproxy
    '''
    _s = __salt__
    reversep = target_data['reverse_proxies']
    # dict init
    _init_http_proxies(reversep,
                       port=target_data.get('http_port', None),
                       ssl_port=target_data.get('https_port', None),
                       ssl_certs=target_data.get('ssl_certs', []),
                       proxy_mode=target_data.get('http_proxy_mode',
                                                  'xforwardedfor'))
    # http/https automatic rules
    for vmname in target_data['vms']:
        vm = target_data['vms'][vmname]
        for domain in vm['domains']:
            _configure_http_reverses(reversep, domain, vm['ip'])
    # http/https raw rules
    for http_proxy in [reversep['http_proxy'], reversep['https_proxy']]:
        if not http_proxy.get('raw_rules_done', False):
            for rule in reversed(http_proxy['raw_opts_pre']):
                http_proxy['raw_opts'].insert(0, rule)
            for rule in http_proxy['raw_opts_post']:
                http_proxy['raw_opts'].append(rule)
            http_proxy['raw_rules_done'] = False
    return target_data


def feed_sw_reverse_proxies_for_target(target_data):
    _s = __salt__
    t = target_data['target']
    vms_infos = target_data.get('vms', {})
    sw_proxies = target_data['reverse_proxies']['sw_proxies']
    for vm, data in vms_infos.items():
        snmp_port = _s['mc_cloud_compute_node.get_snmp_port'](vm, target=t)
        ssh_port = _s['mc_cloud_compute_node.get_ssh_port'](vm, target=t)
        vt = data['vt']
        sw_proxies.append({'comment': 'snmp for {0}'.format(vm)})
        sw_proxies.append({'action': 'DNAT',
                           'source': 'all',
                           'dest': '{1}:{0}:161'.format(data['ip'], vt),
                           'proto': 'udp', 'dport': snmp_port})
        sw_proxies.append({'comment': 'ssh {0}'.format(vm)})
        for i in ['tcp', 'udp']:
            sw_proxies.append({'action': 'DNAT',
                               'source': 'all',
                               'dest': '{1}:{0}:22'.format(data['ip'], vt),
                               'proto': i, 'dport': ssh_port})
    target_data['reverse_proxies']['sw_proxies'] = sw_proxies
    return target_data


def cn_extpillar_settings(id_=None, ttl=30):
    def _do(id_=None):
        _s = __salt__
        if id_ is None:
            id_ = _s['mc_pillar.mastersalt_minion_id']()
        conf = _s['mc_pillar.get_cloud_entry_for_cn'](id_)
        dconf = _s['mc_pillar.get_cloud_conf_for_cn']('default')
        data = _s['mc_utils.dictupdate'](
            _s['mc_utils.dictupdate'](
                _s['mc_utils.dictupdate'](default_settings(), dconf),
                conf.get('conf', {})), {'target': id_,
                                        'reverse_proxies': {'target': id_}})
        data['vts'] = conf.get('vts', [])
        return data
    cache_key = 'mc_cloud_cn.cn_extpillar_settings{0}'.format(id_)
    return copy.deepcopy(memoize_cache(_do, [id_], {}, cache_key, ttl))


def extpillar_settings(id_=None, ttl=30):
    def _do(id_=None):
        _s = __salt__
        data = cn_extpillar_settings(id_=id_)
        for _vm, _vm_data in get_vms_for_target(id_).items():
            data['vms'][_vm] = _s['mc_cloud_vm.vm_extpillar_settings'](_vm)
        # can only be done after some infos is loaded
        data['domains'] = domains_for(id_, data['domains'])
        data['ssl_certs'] = _s['mc_cloud.ssl_certs_for'](
            id_, data['domains'], data['ssl_certs'])
        _s['mc_cloud.add_ms_ssl_certs'](data)
        return data
    cache_key = 'mc_cloud_cn.extpillar_settings{0}'.format(id_)
    return memoize_cache(_do, [id_], {}, cache_key, ttl)


def ext_pillar(id_, prefixed=True, *args, **kw):
    '''
    compute node extpillar
    '''
    _s = __salt__
    expose = False
    if _s['mc_cloud.is_a_compute_node'](id_):
        expose = True
    if not expose:
        return {}
    data = extpillar_settings(id_)
    # can only be done after some infos is loaded -- part2
    data['reverse_proxies']['target'] = data['target'] = id_
    haproxy_pre = data.get('haproxy', {}).get('raw_opts_pre', [])
    haproxy_post = data.get('haproxy', {}).get('raw_opts_post', [])
    for suf, opts in [
        a for a in [
            ['pre', haproxy_pre],
            ['post', haproxy_post]
        ] if a[1]
    ]:
        for subsection in ['https_proxy', 'http_proxy']:
            proxy = data['reverse_proxies'].setdefault(
                subsection, OrderedDict())
            proxy['raw_opts_{0}'.format(suf)] = opts
    data = feed_http_reverse_proxy_for_target(data)
    data = feed_sw_reverse_proxies_for_target(data)
    haproxy_opts = OrderedDict()
    http_proxy = data['reverse_proxies']['http_proxy']
    https_proxy = data['reverse_proxies']['https_proxy']
    for typ, bdatadict in (
        ("frontends", {http_proxy['name']:  http_proxy}),
        ("frontends", {https_proxy['name']: https_proxy}),
        ("backends", data['reverse_proxies']['http_backends']),
        ("backends", data['reverse_proxies']['https_backends']),
    ):
        pref = 'makina-states.services.proxy.haproxy'
        for id_, bdata in bdatadict.items():
            haproxy_opts[pref + '.{0}.{1}'.format(typ, id_)] = bdata
    if prefixed:
        data = {PREFIX: data}
    data.update(haproxy_opts)
    return data


'''
Helper methods usable only after a full extpillar loading
on the controller node
'''


def cleanup_allocated_ips(target):
    '''
    Maintenance routine to cleanup ips when ip
    exhaution arrises
    '''
    allocated_ips = _construct_ips_dict(target)
    existing_vms = get_vms_for_target(target)
    # recycle old ips for unexisting vms
    sync = False
    done = []
    cur_ips = allocated_ips.setdefault('ips', {})
    for name in [n for n in cur_ips]:
        ip = cur_ips[name]
        # doublon ip
        if ip in done:
            remove_allocated_ip(target, ip, vm=name)
        else:
            done.append(ip)
        # ip not allocated to any vm
        if name not in existing_vms:
            sync = True
            del cur_ips[name]
    if sync:
        set_conf_for_target(target, 'allocated_ips', allocated_ips)
    return allocated_ips


def cleanup_ports_mapping(target, kind='ssh'):
    '''
    This is a maintenance routine which can be called to cleanup
    ports when range exhaustion is incoming
    '''
    _s = __salt__
    target_data = ext_pillar(target)
    vms_infos = target_data.get('vms', {})
    kind_map = get_conf_for_target(target, kind + '_map', {})
    # filter old vms grains
    need_sync = True
    for avm in [a for a in kind_map]:
        if avm not in vms_infos:
            del kind_map[avm]
            need_sync = True
    if need_sync:
        set_conf_for_target(target, kind + '_map', kind_map)
    return get_conf_for_target(target, kind + '_map', {})


def cleanup_ssh_ports(target):
    return cleanup_ports_mapping(target, kind='ssh')


def cleanup_snmp_ports(target):
    return cleanup_ports_mapping(target, kind='snmp')


def get_ports_mapping_for_target(target, kind='ssh'):
    _s = __salt__
    target_data = ext_pillar(target)
    mapping = {}
    vms_infos = target_data['vms']
    # generate or refresh ssh mappings
    fun = 'mc_cloud_compute_node.get_{0}_port'.format(kind)
    for vm in vms_infos:
        mapping[vm] = _s[fun](vm, target=target)
    return mapping


def get_snmp_mapping_for_target(target):
    return get_ports_mapping_for_target(target, kind='snmp')


def get_ssh_mapping_for_target(target):
    return get_ports_mapping_for_target(target, kind='ssh')


'''
Methods usable
After the pillar has loaded, on the compute node itself
'''


def settings(ttl=60):
    '''
    compute node related settings
    '''
    def _do():
        _s = __salt__
        data = _s['mc_utils.defaults'](PREFIX, default_settings())
        return data
    cache_key = '{0}.{1}'.format(__name, 'settings')
    return memoize_cache(_do, [], {}, cache_key, ttl)
# vim:set et sts=4 ts=4 tw=80: