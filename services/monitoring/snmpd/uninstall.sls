snmpd-dead:
  service.dead:
    - name: snmpd

snmpd-off:
  service.disabled:
    - name: snmpd
    - enable: false

snmp-uninstall:
  pkg.purged:
    - pkgs:
      - snmp
      - snmp-mibs-downloader
      - snmpd
    - require:
      - service: snmpd-dead
      - service: snmpd-off
{% for f in [
  '/etc/default/snmpd',
  '/etc/snmp/snmpd.conf',
  '/etc/snmp/snmp.conf',
  ] %}
snmpd-{{f}}:
  file.absent:
    - name: {{f}}
    - require:
      - pkg: snmp-uninstall
{% endfor %}
