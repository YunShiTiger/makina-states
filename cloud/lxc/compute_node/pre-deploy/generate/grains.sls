{% set compute_node_settings= salt['mc_cloud_controller.settings']() %}
{% set cloudSettings= salt['mc_cloud.settings']() %}
include:
  - makina-states.cloud.generic.hooks.generate
{% set cloudSettings = salt['mc_cloud.settings']() %}
{% set lxcSettings= salt['mc_cloud_lxc.settings']() %}
{% for target, vms in lxcSettings.vms.items() %}
{% set sname = '{0}'.format(target)%}
{% set cptslsname = '{1}/{0}/lxc/compute_node_lxc-grains'.format(
        target.replace('.', ''),
        cloudSettings.compute_node_sls_dir,
        target.replace('.', '')) %}
{% set cptsls = '{1}/{0}.sls'.format(cptslsname, cloudSettings.root) %}
{% set rcptslsname = '{1}/{0}/lxc/run-compute_node_lxc-grains'.format(
        target.replace('.', ''),
        cloudSettings.compute_node_sls_dir,) %}
{% set rcptsls = '{1}/{0}.sls'.format(rcptslsname, cloudSettings.root) %}
{{sname}}-lxc.compute_node-install-grains-gen-run:
  file.managed:
    - name: {{rcptsls}}
    - user: root
    - mode: 750
    - makedirs: true
    - watch:
      - mc_proxy: cloud-generic-generate
    - watch_in:
      - mc_proxy: cloud-generic-generate-end
    - contents: |
                {%raw%}{# WARNING THIS STATE FILE IS GENERATED #}{%endraw%}
                c{{sname}}-lxcgrains.computenode.sls-generator-for-hostnode-inst:
                  salt.state:
                    - tgt: [{{target}}]
                    - expr_form: list
                    - sls: {{cptslsname.replace('/', '.')}}
                    - concurrent: True
                    - watch:
                      - mc_proxy: cloud-generic-computenode-pre-grains-deploy
                    - watch_in:
                      - mc_proxy: cloud-generic-computenode-post-grains-deploy
{{sname}}-lxc.vm-install-grains-gen:
  file.managed:
    - name: {{cptsls}}
    - user: root
    - mode: 750
    - makedirs: true
    - watch:
      - mc_proxy: cloud-generic-generate
    - watch_in:
      - mc_proxy: cloud-generic-generate-end
    - contents: |
                {%raw%}{# WARNING THIS STATE FILE IS GENERATED #}{%endraw%}
                {{sname}}-run-grains:
                  grains.present:
                    - names:
                      - makina-states.services.virt.docker
                      - makina-states.services.virt.lxc
                    - value: true
                {{ sname }}-reload-grains:
                  cmd.script:
                    - source: salt://makina-states/_scripts/reload_grains.sh
                    - template: jinja
                    - watch:
                      - grains: {{sname}}-run-grains
{% endfor %}
