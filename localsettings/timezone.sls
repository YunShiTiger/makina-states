{#- Install in full mode, see the standalone file !  #}
{% import  "makina-states/localsettings/timezone-standalone.sls" as base with context %}
{{base.do(full=True)}}