{%- set nt_reg = salt['mc_nodetypes.registry']() %}
{{ salt['mc_macros.register']('services', 'virt.lxc') }}
include:
  - makina-states.services.virt.lxc.hooks
{% if salt['mc_controllers.allow_lowlevel_states']() %}
  - makina-states.services.virt.lxc.prerequisites
  - makina-states.services.virt.lxc.configuration
{% endif %}
