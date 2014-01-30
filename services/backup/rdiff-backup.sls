{#-
# Integration of rdiff-backup to backup postgresql & mysql databases
# configured through makina-states
#
# The whole idea is not to try to install or deactivate a specific cron for
# each particular database server, but try to run on each version that we
# can detect
#
# For mysql, you certainly need the root password setting in yout pillar:
#  makina-states.services.db.mysql.root_passwd: <rootpw>
#}
{%- import "makina-states/_macros/services.jinja" as services with context %}
{%- set services = services %}
{%- set localsettings = services.localsettings %}
{%- set nodetypes = services.nodetypes %}
{%- set locs = localsettings.locations %}
{{ salt['mc_macros.register']('services', 'backup.rdiff-backup') }}
{%- set data=services.rdiffbackupSettings %}
{%- set settings=services.rdiffbackupSettings|yaml %}

rdiff-backup-pkgs:
  pkg.installed:
    - pkgs:
      - librsync-dev
      - librsync1
      - python-dev
      - libattr1
      - libattr1-dev
      - libacl1
      - libacl1-dev

rdiff-backup:
  file.directory:
    - name: {{locs.apps_dir}}/rdiff-backup
    - user: root
    - mode: 700
    - makedirs: true
  mc_git.latest:
    - require:
      - pkg: rdiff-backup-pkgs
      - file: rdiff-backup
    - name: https://github.com/makinacorpus/rdiff-backup.git
    - target: {{locs.apps_dir}}/rdiff-backup
    - user: root

rdiff-backup-venv:
  virtualenv.managed:
    - require:
      - mc_git: rdiff-backup
    - requirements: {{locs.apps_dir}}/rdiff-backup/requirements.txt
    - system_site_packages: False
    - python: /usr/bin/python
    - name: {{locs.apps_dir}}/rdiff-backup/venv

rdiff-backup-install:
  cmd.run:
    - name: {{locs.apps_dir}}/rdiff-backup/venv/bin/python dist/setup.py develop
    - cmd: {{locs.apps_dir}}
    - user: root
    - unless: test -e {{locs.apps_dir}}/rdiff-backup/venv/bin/rdiff-backup
    - require:
      - virtualenv: rdiff-backup-venv

{% for bin in ['rdiff-backup', 'rdiff-backup-statistics'] %}
rdiff-backup-{{bin}}-bin:
  file.symlink:
    - name: {{locs.bin_dir}}/{{bin}}
    - target: {{locs.apps_dir}}/rdiff-backup/venv/bin/{{bin}}
    - require:
      - cmd: rdiff-backup-install

rdiff-backup-{{bin}}-man:
  file.symlink:
    - name: {{locs.usr_dir}}/share/man/man1/{{bin}}.1
    - target: {{locs.apps_dir}}/rdiff-backup/{{bin}}.1
    - require:
      - cmd: rdiff-backup-install
{%endfor%}
