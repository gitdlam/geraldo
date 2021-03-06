from os import path
import gettext

from django.conf import settings
from django.test import TestCase
from django.utils.translation import activate

from regressiontests.views.urls import locale_dir

class I18NTests(TestCase):
    """ Tests django views in django/views/i18n.py """

    def test_setlang(self):
        """The set_language view can be used to change the session language"""
        for lang_code, lang_name in settings.LANGUAGES:
            post_data = dict(language=lang_code, next='/views/')
            response = self.client.post('/views/i18n/setlang/', data=post_data)
            self.assertRedirects(response, 'http://testserver/views/')
            self.assertEqual(self.client.session['django_language'], lang_code)

    def test_jsi18n(self):
        """The javascript_catalog can be deployed with language settings"""
        for lang_code in ['es', 'fr', 'en']:
            activate(lang_code)
            catalog = gettext.translation('djangojs', locale_dir, [lang_code])
            trans_txt = catalog.ugettext('this is to be translated')
            response = self.client.get('/views/jsi18n/')
            # in response content must to be a line like that:
            # catalog['this is to be translated'] = 'same_that_trans_txt'
            self.assertContains(response, trans_txt, 1)
