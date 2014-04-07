{# to reverse proxy a host, by default we redirect only and only:
 #  - http
 #  - https
 #  - ssh
 #
 # we can reverse proxy http & https but not ssh
 # for ssh, we are on a /16 by default (10.5/16)
 # so we have 256*254 maximum ports to redirect
 # We start by default at 40000   e
 # eg ip: 10.5.0.1 will have its ssh port mapped to 40001 on host
 # eg ip: 10.5.0.2 will have its ssh port mapped to 40002 on host
 # eg ip: 10.5.1.2 will have its ssh port mapped to 40258 on host
 #}
{% load_json as data %}{{pillar.scnSettings}}{%endload%}
include:
  - makina-states.services.proxy.haproxy
cpt-cloud-haproxy-cfg:
  file.managed:
    - name: {{salt['mc_haproxy.settings']().config_dir}}/extra/cloudcontroller.cfg
    - source: salt://makina-states/files/etc/haproxy/cloudcontroller.cfg
    - user: root
    - group: root
    - mode: 644
    - makedirs: true
    - template: jinja
    - defaults:
      cdata: '{{salt['mc_utils.json_dump'](data.rp.reverse_proxies)}}'
    - watch_in:
      - mc_proxy: haproxy-post-conf-hook