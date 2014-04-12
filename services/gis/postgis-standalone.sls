{#!
# Install a postgis enabled database usable as a teamplate for postgis projects
#}
{% import "makina-states/services/db/postgresql/init.sls" as pgsql with context %}
{%- set locs = salt['mc_locations.settings']() %}
{{ salt['mc_macros.register']('services', 'gis.postgis') }}
{% macro do(full=True) %}
{% set pgSettings = salt['mc_pgsql.settings']() %}
{%- set dbname = pgSettings.postgis_db %}
include:
  - makina-states.services.db.postgresql.hooks
  {% if full -%}
  - makina-states.services.db.postgresql
  {%- endif %}

{% for postgisVer, pgvers in pgSettings.postgis.items() -%}
{%  for pgVer in pgvers -%}
{%    if pgVer in pgSettings.versions -%}
{%      if full -%}
prereq-postgis-{{pgVer}}-{{postgisVer}}:
  pkg.{{salt['mc_pkgs.settings']()['installmode']}}:
    - require_in:
      - mc_proxy: {{pgsql.orchestrate[pgVer]['pregroup']}}
      - mc_proxy: {{pgsql.orchestrate[pgVer]['predb']}}
    {%  if full -%}
    - require:
      - pkg: postgresql-pkgs
    {%- endif %}
    - pkgs:
      - python-virtualenv {# noop #}
      {% if grains['os_family'] in ['Debian'] %}
      - postgresql-{{pgVer}}-postgis-{{postgisVer}}
      - liblwgeom-dev
      - postgresql-{{pgVer}}-postgis-scripts
      {% endif %}
{%-     endif %}

{{ pgsql.postgresql_db(dbname, full=full) }}

{{ pgsql.install_pg_exts(
    ["postgis",
     "postgis_topology",
     "fuzzystrmatch",
     "postgis_tiger_geocoder"],
    db=dbname,
    full=full) }}
{%-    endif %}
{%-  endfor %}
{%- endfor %}
{%- endmacro %}
{{ do(full=False) }}
