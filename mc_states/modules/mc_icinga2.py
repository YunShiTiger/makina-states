# -*- coding: utf-8 -*-
'''
.. _module_mc_icinga2:

mc_icinga2 / icinga functions
============================

The first level of subdictionaries is for distinguish configuration
files. There is one subdictionary per configuration file.
The key used for subdictionary correspond
to the name of the file but the "." is replaced with a "_"

The subdictionary "modules" contains a subsubdictionary for each
module. In each module subdictionary, there is a subdictionary per
file.
The key "enabled" in each module dictionary is for enabling or
disabling the module.

The "nginx" and "uwsgi" sub-dictionaries are given to macros
in \*\*kwargs parameter.

The key "package" is for listing packages installed between pre-install
and post-install hooks

The keys "has_pgsql" and "has_mysql" determine if a local postgresql
or mysql instance must be installed.
The default value is computed from default database parameters
If the connection is made through a unix pipe or with the localhost
hostname, the booleans are set to True.

'''

__docformat__ = 'restructuredtext en'
# Import python libs

from salt.utils.odict import OrderedDict
import os
import logging
import traceback
import copy
import mc_states.utils
from mc_states.utils import memoize_cache

__name = 'icinga2'

log = logging.getLogger(__name__)


def svc_name(key):
    key = key.replace('/', 'SLASH')
    key = key.replace(':', '_')
    return key


def reencode_webstrings(str_list):
    # transform list of values in
    # string ['a', 'b'] becomes '"a" -s "b"'
    if isinstance(str_list, list):
        # to avoid quotes conflicts (doesn't avoid code injection)
        str_list = [value.replace('"', '\\\\"') for value in str_list]
        str_list = ('"' + '" -s "'.join(str_list) + '"')
    return str_list


def load_objects(core=True, ttl=120):
    '''
    function to load extra icinga settings from pillar

    they contains the objects definitions to add in icinga2

    Idea is to use them differently not to use all the RAM
    in cache for the states construction.

    the autoconfigured_hosts_definitions dictionary contains the
    definitions of hosts created with the configuration_add_auto_host
    macro

    the objects_definitions dictionary contains the defintinions of
    objects created with the configuration_add_object_macro

    the purges list contains the files to delete

    the "notification" and "parents" are under "attrs"
    but in fact it creates other objects like HostDependency
    or Notification

    example::

      icinga2_definitions:
         autoconfigured_hosts:
          localhost:
            hostname: "localhost"
            attrs:
              address: 127.0.0.1
              display_name: "localhost"
            ssh: true
            services_attrs:
              web:
                www.foo.com: bar
         objects:
           mycommand:
             attrs:
              parents:
                - parent1
                - parent2
              notification:
                command: "notify-by-email"
                users = ["user1"]
              command: /usr/bin/mycommand
              arguments:
                - arg: value
           name: mycommand
           file: command.conf
           type: CheckCommand
           template: false
         purges:
           - commands.conf
    '''

    def _do(core):
        core_objects = {}
        if core:
            core_objects = __salt__['mc_utils.cyaml_load'](
                '/srv/mastersalt/makina-states/'
                'files/icinga2_core_objects.conf')
        data = __salt__['mc_utils.defaults'](
            'icinga2_definitions', {
                'objects': core_objects,
                'purges': [],
                # where the icinga2 objects configuration
                # will be written
                'autoconfigured_hosts': {}
            })
        return data
    cache_key = 'mc_icinga2.load_objects___cache__'
    return memoize_cache(_do, [core], {}, cache_key, ttl)


def objects(core=True, ttl=120):
    def _do(core):
        rdata = OrderedDict()
        data = __salt__['mc_icinga2.load_objects'](core=core)
        rdata['raw_objects'] = data['objects']
        rdata['objects'] = OrderedDict()
        rdata['objects_by_file'] = OrderedDict()
        for obj, data in data['objects'].items():
            # automatic name from ID
            if not data.get('name', ''):
                data['name'] = obj
            name = data['name']
            # by default, we are not a template
            tp = data.setdefault('template', False)
            typ_ = data.get('type', None)
            # try to guess template status from name
            if not tp:
                for test in [
                    lambda x: x.startswith('HT_'),
                    lambda x: x.startswith('ST_')
                ]:
                    if test(name):
                        tp = data['template'] = True
                        break
            # automatic hostname from ID
            if not data.get('hostname', ''):
                data['hostname'] = obj
            # try to get type from name
            if not typ_:
                for final_typ, tests in {
                    'TimePeriod': [lambda x: x.startswith('TP_'),
                                   lambda x: x.startswith('T_')],
                    'NotificationCommand': [lambda x: x.startswith('NC_'),
                                            lambda x: x.startswith('N_')],
                    'Host': [lambda x: x.startswith('HT_'),
                             lambda x: x.startswith('H_'),],
                    'Service': [lambda x: x.startswith('ST_'),
                                lambda x: x.startswith('S_')],
                    'User': [lambda x: x.startswith('U_')],
                    'UserGroup': [lambda x: x.startswith('G_')],
                    'HostGroup': [lambda x: x.startswith('HG_')],
                    'ServiceGroup': [lambda x: x.startswith('GS_'),
                                     lambda x: x.startswith('SG_')],
                    'HostGroup': [lambda x: x.startswith('HG_')],
                    'CheckCommand': [lambda x: x.startswith('check_'),
                                     lambda x: x.startswith('C_'),
                                     lambda x: x.startswith('EV_'),
                                     lambda x: x.startswith('CSSH_')],
                }.items():
                    for test in tests:
                        if test(name):
                            typ_ = final_typ
                            break
                    if typ_:
                        break
            file_ = {'NotificationCommand': 'misccommands.conf',
                     'TimePeriod': 'timeperiods.conf',
                     'CheckCommand': 'checkcommands.conf',
                     'User': 'contacts.conf',
                     'UserGroup': 'contactgroups.conf',
                     'HostGroup': 'hostgroups.conf',
                     'Service': 'services.conf',
                     'ServiceGroup': 'servicegroups.conf',
                     'Host': 'contacts.conf'}
            # guess configuration file from type
            ft = data.setdefault('file', file_.get(typ_, None))
            data['file'] = ft
            data['type'] = typ_
            data.setdefault('attrs', {})
            rdata['objects'][obj] = data
            fdata = rdata['objects_by_file'].setdefault(
                data['file'], OrderedDict())
            fdata[obj] = data
        return rdata
    cache_key = 'mc_icinga2.objects___cache__'
    return memoize_cache(_do, [core], {}, cache_key, ttl)


def format(dictionary, quote_keys=False, quote_values=True, init=True):
    '''
    function to transform all values in a dictionary in string
    and adding quotes.
    The main goal is to print values with quotes like "value"
    but we don't want print list with quotes like "[v1, v2]".
    This should be ["v1", "v2"] this can be done in jinja
    template but the template is already complex
    '''
    def quotev(v):
        if not v.startswith('"'):
            v = '"' + str(v.replace('"', '\\"')) + '"'
        return v
    res = {}
    for key, value in copy.deepcopy(dictionary).items():
        if quote_keys:
            res_key = quotev(key)
        else:
            res_key = key

        # ugly hack
        if key in ['template',
                   'types', 'states', 'import']:
            quote_value = False
        elif key in ['command']:
            quote_value = True
        else:
            quote_value = quote_values

        if isinstance(value, dict):  # recurse
            # in theses subdictionaries, the keys are also quoted
            if key in ['arguments', 'ranges']:
                res[res_key] = format(value, True, True, False)
            # theses dictionaries contains booleans
            elif key in ['services_enabled']:
                res[res_key] = format(value, False, False, False)
            else:
                res[res_key] = format(value, quote_keys, quote_value, False)
        elif isinstance(value, list):
            # theses lists are managed in the template,
            # we only quote each string in the list
            if key in ['import', 'parents']:
                res[res_key] = map(quotev, value)
            else:

                res[res_key] = '['
                # suppose that all values in list are strings
                # escape '"' char and quote each strings
                if quote_value:
                    res[res_key] += ', '.join(map(quotev, value))
                else:
                    res[res_key] += ', '.join(value)
                res[res_key] += ']'
        elif key.startswith('enable_'):
            if (
                '"1"' == value
                or '1' == value
                or 1 == value
                or 'true' == value
                or True == value
            ):
                res[res_key] = "true"
            else:
                res[res_key] = "false"
        elif key in ['template']:
            res[res_key] = value
        elif key.endswith('_interval'):  # a bad method to find a time
            res[res_key] = value
        elif isinstance(value, bool):
            res[res_key] = (value is True) and 'true' or 'false'
        elif isinstance(value, int):
            res[res_key] = str(value)
        elif isinstance(value, unicode):
            if quote_value:
                res[res_key] = quotev(value)
            else:
                res[res_key] = value
        else:
            if quote_value:
                res[res_key] = quotev(str(value).decode('utf-8'))
            else:
                res[res_key] = value
    return res


def get_settings_for_object(target=None, obj=None, attr=None):
    '''
    expand the subdictionaries which are not cached
    in mc_icinga2.settings.objects
    '''
    res = objects()[target][obj]
    if attr:
        res = res[attr]
    return res


def settings():
    '''
    icinga2 settings

    location
        installation directory

    package
        list of packages to install icinga
    has_pgsql
        install and configure a postgresql service in order to be used
        with ido2db module
    has_mysql
        install and configure a mysql service in order to be used with
        ido2db module
    user
        icinga user
    group
        icinga group
    cmdgroup
        group for the command file
    pidfile
        file to store icinga2 pid
    niceness
        priority of icinga process
    configuration_directory
        directory to store configuration
    objects
       dictionary to configure objects
    directory
       directory in which objects will be stored. The
       directory should be listed in "include_recursive"
       values
    icinga_conf
        include
            list of configuration files
            quotes have to be added for real directories
        include_recursive
            list of directory containing files configuration
    constants_conf
        values for constants conf
    zones_conf
        values for zones conf
    modules
        perfdata
            enabled
                enable the perfdata module
        livestatus
            enabled
                enable the livestatus module
        ido2db
            enabled
                enable the ido2db module

    '''
    @mc_states.utils.lazy_subregistry_get(__salt__, __name)
    def _settings():
        grains = __grains__
        pillar = __pillar__
        icinga2_reg = __salt__[
            'mc_macros.get_local_registry'](
                'icinga2', registry_format='pack')
        locs = __salt__['mc_locations.settings']()

        # do not store in cache
        # registry the whole conf, memory would explode
        # keep only the list of keys for each subdictionary
        # get_settings_for_object is the function to retrieve
        # generate default password
        icinga2_reg = __salt__[
            'mc_macros.get_local_registry'](
                'icinga2', registry_format='pack')

        password_ido = icinga2_reg.setdefault('ido.db_password', __salt__[
            'mc_utils.generate_password']())
        data = __salt__['mc_utils.defaults'](
            'makina-states.services.monitoring.icinga2', {
                'package': ['icinga2-bin',
                            'nagios-plugins',
                            'icinga2-common',
                            'icinga2-doc'],
                'has_pgsql': False,
                'create_pgsql': True,
                'has_mysql': False,
                'user': "nagios",
                'gen_directory': (
                    "/etc/icinga2/conf.d/salt_generated"),
                'group': "nagios",
                'cmdgroup': "www-data",
                'pidfile': "/var/run/icinga2/icinga2.pid",
                'configuration_directory': (
                    locs['conf_dir'] + "/icinga2"),
                'niceness': 5,
                'icinga_conf': {
                    'include': ['"constants.conf"',
                                '"zones.conf"',
                                '<itl>',
                                '<plugins>',
                                '"features-enabled/*.conf"'],
                    'include_recursive': ['"conf.d"'],
                },
                'constants_conf': {
                    'PluginDir': "\"/usr/lib/nagios/plugins\"",
                    'USER1': "\"/usr/lib/nagios/plugins\"",
                    'ZoneName': "NodeName",
                },
                'zones_conf': {
                    'object Endpoint NodeName': {
                        'host': "NodeName"},
                    'object Zone ZoneName': {
                        'endpoints': "[ NodeName ]"},
                },
                'modules': {
                    'perfdata': {'enabled': True},
                    'livestatus': {
                        'enabled': True,
                        'bind_host': "127.0.0.1",
                        'bind_port': 6558,
                        'socket_path': (
                            "/var/run/icinga2/cmd/livestatus"
                        )
                    },
                    'ido2db': {
                        'enabled': True,
                        'user': "nagios",
                        'group': "nagios",
                        'pidfile': "/var/run/icinga2/ido2db.pid",
                        'database': {
                            'type': "pgsql",
                            'host': "localhost",
                            'port': 5432,
                            'user': "icinga2_ido",
                            'password': password_ido,
                            'name': "icinga2_ido",
                        }
                    },
                },
            }
        )
        ido2db = data['modules']['ido2db']
        data['has_pgsql'] = 'pgsql' == ido2db['database']['type']
        data['has_mysql'] = 'mysql' == ido2db['database']['type']
        if data['has_pgsql']:
            ido2db['package'] = [
                'icinga2-ido-{0}'.format(
                    ido2db['database']['type'])]
        if data['has_pgsql'] and data['has_mysql']:
            raise ValueError('choose only one sgbd')
        if not (data['has_pgsql'] or data['has_mysql']):
            raise ValueError('choose at least one sgbd')
        __salt__['mc_macros.update_local_registry'](
            'icinga2', icinga2_reg,
            registry_format='pack')
        return data
    return _settings()


def replace_chars(s):
    res = s
    for char in list('/.:_'):
        res = res.replace(char, '-')
    return res


def remove_configuration_objects():
    '''Add the file in the file's list to be removed'''
    icingaSettings_complete = __salt__['mc_icinga2.settings']()
    files = __salt__['mc_icinga2.load_objects']()['purges']
    todel = []
    prefix = icingaSettings_complete['gen_directory']
    for f in files:
        pretendants = [os.path.join(prefix, f),
                       f]
        for p in pretendants:
            if os.path.exists(p):
                todel.append(p)
    return todel


def autoconfigured_hosts(ttl=60):
    def _do():
        rdata = OrderedDict()
        objs = __salt__['mc_icinga2.load_objects']()[ 'autoconfigured_hosts']
        for host, data in objs.items():
            rdata[host] = __salt__['mc_icinga2.autoconfigured_host'](
                host, data=data)
        return rdata
    cache_key = 'mc_icinga2.autoconfigured_hosts__cache__'
    return memoize_cache(_do, [], {}, cache_key, ttl)


def autoconfigured_host(host, data=None, ttl=60):
    def _do(host, data):
        if data is None:
            data = __salt__['mc_icinga2.load_objects']()[
                'autoconfigured_hosts'][host]
        data = copy.deepcopy(data)
        # automatic name from ID
        if not data.get('name', ''):
            data['name'] = host
        # automatic hostname from ID
        if not data.get('hostname', ''):
            data['hostname'] = host
        try:
            rdata = __salt__['mc_icinga2.autoconfigure_host'](
                data['hostname'], **data)
            for k in ['name', 'hostname']:
                rdata[k] = data[k]
        except Exception, exc:
            trace = traceback.format_exc()
            log.error('Supervision autoconfiguration '
                      'routine failed for {0}'.format(host))
            log.error(trace)
            log.error('{0}'.format(data))
            raise exc
        return rdata
    cache_key = 'mc_icinga2.autoconfigured_host__cache__{0}'.format(host)
    return memoize_cache(_do, [host, data], {}, cache_key, ttl)


def autoconfigure_host(host,
                       attrs=None,
                       services_attrs=None,
                       ssh_user='root',
                       ssh_addr='',
                       ssh_port=22,
                       ssh_timeout=30,
                       apt=True,
                       backup_burp_age=True,
                       cron=False,
                       ddos=False,
                       disk_space_mode=None,
                       disk_space=None,
                       dns_association=False,
                       dns_association_hostname=True,
                       drbd=False,
                       fail2ban=False,
                       haproxy=False,
                       load_avg=True,
                       mail_cyrus_imap_connections=False,
                       mail_imap=False,
                       mail_imap_ssl=False,
                       mail_pop=False,
                       mail_pop_ssl=False,
                       mail_pop_test_account=False,
                       mail_server_queues=False,
                       mail_smtp=False,
                       megaraid_sas=False,
                       memory_mode=None,
                       memory=True,
                       nic_card=None,
                       ntp_peers=False,
                       ntp_time=False,
                       postgres_port=False,
                       process_beam=False,
                       process_epmd=False,
                       process_gunicorn_django=False,
                       process_gunicorn=False,
                       process_ircbot=False,
                       process_mysql=False,
                       process_postgres=False,
                       process_python=False,
                       raid=False,
                       sas=False,
                       snmpd_memory_control=False,
                       solr=False,
                       ssh=True,
                       swap=True,
                       ware_raid=False,
                       web_apache_status=False,
                       web=False,
                       web_openid=False,
                       **kwargs):
    disk_space_mode_maps = {
        'large': 'ST_LARGE_DISK_SPACE',
        'ularge': 'ST_ULARGE_DISK_SPACE',
        None: 'ST_DISK_SPACE'}
    memory_mode_maps = {
        'large': 'ST_MEMORY_LARGE',
        None: 'ST_MEMORY'}
    st_mem = memory_mode_maps.get(memory_mode, None)
    st_disk = disk_space_mode_maps.get(disk_space_mode, None)
    services = ['backup_burp_age',
                'cron',
                'ddos',
                'apt',
                'disk_space',
                'memory',
                'dns_association',
                'dns_association_hostname',
                'drbd',
                'fail2ban',
                'haproxy',
                'load_avg',
                'mail_cyrus_imap_connections',
                'mail_imap',
                'mail_imap_ssl',
                'mail_pop',
                'mail_pop_ssl',
                'mail_pop_test_account',
                'mail_server_queues',
                'mail_smtp',
                'megaraid_sas',
                'nic_card',
                'ntp_peers',
                'ntp_time',
                'postgres_port',
                'process_epmd',
                'process_gunicorn',
                'process_gunicorn_django',
                'process_ircbot',
                'process_beam',
                'process_python',
                'process_mysql',
                'process_postgres',
                'raid',
                'sas',
                'snmpd_memory_control',
                'ssh',
                'solr',
                'web',
                'web_openid',
                'swap',
                'ware_raid',
                'web_apache_status']
    services_multiple = ['dns_association', 'solr', 'web_openid', 'web']
    rdata = {"host.name": host}
    icingaSettings = __salt__['mc_icinga2.settings']()
    if attrs is None:
        attrs = {}
    if services_attrs is None:
        services_attrs = {}
    if solr is None:
        solr = []
    if web_openid is None:
        web_openid = []
    if web is None:
        web = []
    filen = '/'.join(['hosts', host+'.conf'])
    if disk_space is None:
        disk_space = ['/']
    if nic_card is None:
        nic_card = ['eth0']
    if not disk_space:
        disk_space = []
    if not nic_card:
        nic_card = []
    if not ssh_addr:
        ssh_addr = host
    rdata.update({'type': 'Host',
                  'directory': icingaSettings['gen_directory'],
                  'attrs': attrs,
                  'file': filen,
                  'state_name_salt': replace_chars(filen)})
    services_enabled = rdata.setdefault('services_enabled', OrderedDict())
    services_enabled_types = rdata.setdefault('services_enabled_types', [])
    attrs.setdefault('type',  'Host')
    attrs.setdefault('hostname',  host)
    attrs.setdefault('vars.ssh_user', ssh_user)
    attrs.setdefault('vars.ssh_addr', ssh_addr)
    attrs.setdefault('vars.ssh_port', ssh_port)
    attrs.setdefault('vars.ssh_timeout', ssh_timeout)
    # services for which a loop is used in the macro
    if (
        dns_association_hostname
        or dns_association
        and 'address' in attrs
        and 'host_name' in attrs
    ):
        if 'host_name' in attrs:
            dns_hostname = attrs['host_name']
        else:
            dns_hostname = host
        if not dns_hostname.endswith('.'):
            dns_hostname += '.'
        dns_address = attrs['address']
    # give the default values for commands parameters values
    # the keys are the services names,
    # not the commands names (use the service filename)
    services_default_attrs = {
        'backup_burp_age': {
            'import': ["ST_BACKUP_BURP_AGE"]},
        'process_beam': {
            'import': ["ST_PROCESS_BEAM"]},
        'process_python': {
            'import': ["ST_BEAM_PYTHON"]},
        'cron': {
            'import': ["ST_SSH_PROC_CRON"]},
        'ddos': {
            'import': ["ST_SSH_DDOS"]},
        'apt': {
            'import': ["ST_APT"]},
        'dns_association_hostname': {
            'import': ["ST_DNS_ASSOCIATION_hostname"],
            'vars.hostname': dns_hostname,
            'vars.dns_address': dns_address},
        'dns_association': {
            'import': ["ST_DNS_ASSOCIATION"],
            'vars.hostname': dns_hostname,
            'vars.dns_address': dns_address},
        'disk_space': {
            'import': [st_disk]},
        'drbd': {
            'import': ["ST_DRBD"]},
        'process_epmd': {
            'import': ["ST_PROCESS_EPMD"]},
        'fail2ban': {
            'import': ["ST_PROCESS_FAIL2BAN"]},
        'process_gunicorn': {
            'import': ["ST_PROCESS_GUNICORN"]},
        'process_gunicorn_django': {
            'import': ["ST_PROCESS_GUNICORN_DJANGO"]},
        'haproxy': {
            'import': ["ST_HAPROXY_STATS"]},
        'process_ircbot': {
            'import': ["ST_PROCESS_IRCBOT"]},
        'load_avg': {
            'import': ["ST_LOAD_AVG"]},
        'mail_cyrus_imap_connections': {
            'import': ["ST_MAIL_CYRUS_IMAP_CONNECTIONS"]},
        'mail_imap': {
            'import': ["ST_MAIL_IMAP"]},
        'mail_imap_ssl': {
            'import': ["ST_MAIL_IMAP_SSL"]},
        'mail_pop': {
            'import': ["ST_MAIL_POP"]},
        'mail_pop_ssl': {
            'import': ["ST_MAIL_POP_SSL"]},
        'mail_pop_test_account': {
            'import': ["ST_MAIL_POP3_TEST_ACCOUNT"]},
        'mail_server_queues': {
            'import': ["ST_MAIL_SERVER_QUEUES"]},
        'mail_smtp': {
            'import': ["ST_MAIL_SMTP"]},
        'memory': {
            'import': [st_mem]},
        'process_mysql': {
            'import': ["ST_PROCESS_MYSQL"]},
        'nic_card': {
            'import': ["ST_NETWORK"]},
        'ntp_peers': {
            'import': ["ST_NTP_PEERS"]},
        'ntp_time': {
            'import': ["ST_NTP_TIME"]},
        'postgres_port': {
            'import': ["ST_POSTGRESQL_PORT"]},
        'process_postgres': {
            'import': ["ST_PROCESS_POSTGRESQL"]},
        'snmpd_memory_control': {
            'import': ["ST_SNMPD_MEMORY_CONTROL"]},
        'solr': {
            'import': ["ST_SOLR"]},
        'ssh': {
            'import': ["ST_SSH"]},
        'swap': {
            'import': ["ST_SWAP"]},
        'ware_raid': {
            'import': ["ST_WARE_RAID"]},
        'web_apache_status': {
            'import': ["ST_APACHE_STATUS"]},
        'web_openid': {
            'import': ["ST_WEB_OPENID"]},
        'web': {
            'import': ["ST_WEB"]},
        'megaraid_sas': {
            'import': ["ST_MEGARAID_SAS"]},
        'raid': {
            'import': ["ST_RAID"]},
        'sas': {
            'import': ["ST_SAS"]}}
    # if we defined extra properties on a service, enable it automatically
    for s in services:
        if (
            s not in services_enabled_types
            and (s in services_attrs or bool(eval(s)))
        ):
            services_enabled_types.append(s)
    for svc in services_enabled_types:
        if svc in ['disk_space', 'nic_card'] + services_multiple:
            if svc in ['disk_space', 'nic_card']:
                values = eval(svc)
            else:
                values = services_attrs.get(svc, {})
            keys = [a for a in values]
            for v in keys:
                vdata = services_attrs.get(svc, {}).get(v, {})
                skey = svc_name('{0}_{1}_{2}'.format(host, svc, v).upper())
                ss = add_check(host,
                               services_enabled,
                               svc,
                               skey,
                               services_default_attrs.get(svc, {}),
                               vdata)[skey]
                if svc in ['disk_space', 'nic_card']:
                    ss[{'disk_space': 'vars.path',
                        'nic_card': 'vars.interface'}[svc]] = v
                # transform value in string: ['a', 'b'] => '"a" -s "b"'
                if svc in ['solr', 'web'] and 'vars.strings' in ss:
                    ss['vars.strings'] = reencode_webstrings(
                        services_attrs[svc][v]['vars.strings'])
        else:
            skey = svc_name('{0}_{1}'.format(host, svc).upper())
            ss = add_check(host,
                           services_enabled,
                           svc,
                           skey,
                           services_default_attrs[svc],
                           services_attrs.get(svc, {}))[skey]
    return rdata


def add_check(host, services_enabled, svc, skey, default_value, vdata):
    ss = __salt__['mc_utils.dictupdate'](copy.deepcopy(default_value), vdata)
    ss['host.name'] = host
    ss['service_description'] = skey
    ss['makinastates_service_type'] = svc
    services_enabled[skey] = ss
    return services_enabled


def dump():
    return mc_states.utils.dump(__salt__,__name)

#
