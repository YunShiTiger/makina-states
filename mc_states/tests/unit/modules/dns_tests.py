#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import division
from __future__ import absolute_import
from __future__ import division
import unittest
import mc_states.api
from .. import base


class TestCase(base.ModuleCase):

    def test_dns(self):
        with self.patch(pillar={
            'makina-states.localsettings.dns.no_default_dnses': True
        }):
            ret1 = self._('mc_dns.settings')()
            self.assertEqual(ret1['default_dnses'], [])
        mc_states.api.invalidate_memoize_cache('mc_dns.settings')
        with self.patch(pillar={
            'makina-states.localsettings.dns.no_default_dnses': False,
            'makina-states.localsettings.dns.default_dnses': []
        }):
            ret1 = self._('mc_dns.settings')()
            self.assertEqual(ret1['default_dnses'], ['127.0.0.1',
                                                     '127.0.1.1',
                                                     '8.8.8.8',
                                                     '4.4.4.4'])


if __name__ == '__main__':
    unittest.main()
# vim:set et sts=4 ts=4 tw=80:
