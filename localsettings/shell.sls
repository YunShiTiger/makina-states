{#-
# basic shell configuration
# see:
#   - makina-states/doc/ref/formulaes/localsettings/shell.rst
#}
{{ salt['mc_macros.register']('localsettings', 'shell') }}
{% if salt['mc_controllers.mastersalt_mode']() %}
{%- set locs = salt['mc_locations.settings']() %}
etc-profile-d:
  file.directory:
    - name: {{ locs.conf_dir }}/profile.d
    - user: root
    - group: root
    - dir_mode: 0755
    - file_mode: 0755
    - makedirs: true

makina-etc-profile-acc:
  file.accumulated:
    - filename: {{ locs.conf_dir }}/profile
    - text: |
            if [ -d {{ locs.conf_dir }}/profile.d ]; then
              # only apply if we have no inclusion yet
              if [ "x${ETC_PROFILED_LOADED}" = "x" ];then
                for i in {{ locs.conf_dir }}/profile.d/*.sh; do
                  if [ -r $i ]; then
                    . $i;
                  fi;
                done;
                unset i;
                ETC_PROFILED_LOADED="1"
              fi
            fi
    - require_in:
      - file: makina-etc-profile-block

makina-etc-profile-block:
  file.blockreplace:
    - name: {{ locs.conf_dir }}/profile
    - marker_start: "# START managed zone profile__d -DO-NOT-EDIT-"
    - marker_end: "# END managed zone profile__d"
    - content: ''
    - append_if_not_found: True
    - backup: '.bak'
    - show_changes: True
{% endif %}
# vim: set nofoldenable:
