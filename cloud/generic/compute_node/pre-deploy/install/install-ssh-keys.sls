{% set cloudSettings = salt['mc_cloud.settings']() %}
{% set compute_node_settings = salt['mc_cloud_compute_node.settings']() %}
{% set lxcSettings = salt['mc_cloud_lxc.settings']() %}
include:
  - makina-states.cloud.generic.hooks.compute_node
  - makina-states.cloud.generic.genssh
{% for target, vm in lxcSettings.vms.items() %}
{# authorize root from cloudcontroller to connect via ssh on targets #}
{% set cptslsname = '{1}/{0}/run-compute_node_ssh_key'.format(target.replace('.', ''),
                                                           cloudSettings.compute_node_sls_dir) %}
{% set cptsls = '{1}/{0}.sls'.format(cptslsname, cloudSettings.root) %}
  - {{cptslsname.replace('/', '.')}}
{% endfor %}