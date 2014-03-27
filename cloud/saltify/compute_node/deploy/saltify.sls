{% set cloudSettings = salt['mc_cloud.settings']() %}
{% set cloudsaltSettings = salt['mc_cloud_saltify.settings']() %}
include:
  - makina-states.cloud.saltify.hooks

{% for target, data in cloudsaltSettings.targets.items() %}
{% set name = data['name'] %}
{{target}}-{{name}}-saltify-deploy:
  cloud.profile:
    - require:
      - mc_proxy: cloud-saltify-pre-deploy
    - require_in:
      - mc_proxy: cloud-saltify-post-deploy
    - unless: test -e {{cloudSettings.prefix}}/pki/master/minions/{{name}}
    - name: {{name}}
    - minion: {master: "{{data.master}}",
               master_port: {{data.master_port}}}
    - profile: {{data.profile}}
{%    for var in ["ssh_username",
                  "ssh_keyfile",
                  "keep_tmp",
                  "gateway",
                  "password",
                  "script_args",
                  "ssh_host",
                  "sudo_password",
                  "sudo"] %}
{%      if data.get(var) %}
    - {{var}}: {{data[var]}}
{%      endif%}
{%    endfor%}
{% endfor %}