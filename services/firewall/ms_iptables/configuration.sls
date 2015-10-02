{% import "makina-states/_macros/h.jinja" as h with context %}
{% set data = salt['mc_ms_iptables.settings']() %}
include:
  - makina-states.services.firewall.ms_iptables.hooks
{% if salt['mc_controllers.mastersalt_mode']() %}
  - makina-states.services.firewall.ms_iptables.service
  - makina-states.localsettings.network
{% macro rmacro() %}
    - watch:
      - mc_proxy: ms_iptables-preconf
    - watch_in:
      - mc_proxy: ms_iptables-postconf
{% endmacro %}
{{ h.deliver_config_files(
     data.get('extra_confs', {}), after_macro=rmacro, prefix='ms_iptables-')}}

ms_iptables-forward:
  sysctl.present:
    - name: net.ipv4.ip_forward
    - value: 1
    {{rmacro()}}
{% endif %}