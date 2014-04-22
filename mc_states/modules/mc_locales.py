#!/usr/bin/env python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''

.. _module_mc_locales:

mc_locales / locales registry
============================================

If you alter this module and want to test it, do not forget
to deploy it on minion using::

  salt '*' saltutil.sync_modules

Documentation of this module is available with::

  salt '*' sys.doc mc_locales

'''
# Import python libs
import logging
import mc_states.utils

__name = 'locales'

log = logging.getLogger(__name__)


def is_reverse_proxied():
    return __salt__['mc_cloud.is_vm']()


def settings():
    '''
    locales registry

    locales
        locales to use
    default_locale
        Default locale
    '''
    @mc_states.utils.lazy_subregistry_get(__salt__, __name)
    def _settings():
        saltmods = __salt__
        grains = __grains__
        # locales
        default_locale = 'fr_FR.UTF-8'
        default_locales = [
            'de_DE.UTF-8',
            'fr_BE.UTF-8',
            'fr_FR.UTF-8',
        ]
        data = __salt__['mc_utils.defaults'](
            'makina-states.localsettings.locales', {
                'locales': default_locales,
                'locale': default_locale,
            }
        )
        # retro compat
        data['default_locale'] = data["locale"]
        return data
    return _settings()


def dump():
    return mc_states.utils.dump(__salt__,__name)

#
# -*- coding: utf-8 -*-
__docformat__ = 'restructuredtext en'

# vim:set et sts=4 ts=4 tw=80:
# -*- coding: utf-8 -*-
__docformat__ = 'restructuredtext en'

# vim:set et sts=4 ts=4 tw=80:
