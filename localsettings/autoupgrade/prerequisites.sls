include:
  makina-states.localsettings.pkgs-hooks

{% if grains['os'] in ['Ubuntu'] %}

{{ salt['mc_macros.register']('localsettings', 'pkgs') }}
{% if salt['mc_controllers.mastersalt_mode']() %}
{%- set data = salt['mc_autoupgrade.settings']() %}
unattended-pkgs:
  pkg.{{salt['mc_pkgs.settings']()['installmode']}}:
    - pkgs:
      - unattended-upgrades

{%endif %}
{%endif %}