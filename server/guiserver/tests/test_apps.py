# This file is part of the Juju GUI, which lets users view and manage Juju
# environments within a graphical interface (https://launchpad.net/juju-gui).
# Copyright (C) 2013 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License version 3, as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the Juju GUI server applications."""

import unittest

import mock

from guiserver import (
    apps,
    auth,
    handlers,
    manage,
)
from guiserver.bundles import base


class AppsTestMixin(object):
    """Base tests and helper methods for applications.

    Subclasses must define a get_app method returning the application.
    """

    def get_url_spec(self, app, pattern):
        """Return the app URL specification with the given regex pattern.

        Return None if the URL specification is not found.
        See tornado.web.URLSpec.
        """
        for spec in app.handlers[0][1]:
            if spec.regex.pattern == pattern:
                return spec
        return None

    def assert_in_spec(self, spec, key, value=None):
        """Ensure the given key-value pair is present in the specification.

        Also return the value in the specification.
        """
        self.assertIsNotNone(spec)
        self.assertIn(key, spec.kwargs)
        obtained = spec.kwargs[key]
        if value is not None:
            self.assertEqual(value, obtained)
        return obtained

    def test_debug_enabled(self):
        # Debug mode is enabled if options.debug is True.
        app = self.get_app(debug=True)
        self.assertTrue(app.settings['debug'])

    def test_debug_disabled(self):
        # Debug mode is disabled if options.debug is False.
        app = self.get_app(debug=False)
        self.assertFalse(app.settings['debug'])


class TestServer(AppsTestMixin, unittest.TestCase):

    def get_app(self, **kwargs):
        """Create and return the server application.

        Use the options provided in kwargs.
        """
        options_dict = {
            'apiurl': 'wss://example.com:17070',
            'apiversion': 'go',
            'sandbox': False,
        }
        options_dict.update(kwargs)
        options = mock.Mock(**options_dict)
        with mock.patch('guiserver.apps.options', options):
            return apps.server()

    def test_auth_backend(self):
        # The authentication backend instance is correctly passed to the
        # WebSocket handler.
        app = self.get_app()
        spec = self.get_url_spec(app, r'^/ws(?:/.*)?$')
        auth_backend = self.assert_in_spec(spec, 'auth_backend')
        expected = auth.get_backend(manage.DEFAULT_API_VERSION)
        self.assertIsInstance(auth_backend, type(expected))

    def test_deployer(self):
        # The deployer instance is correctly passed to the WebSocket handler.
        app = self.get_app()
        spec = self.get_url_spec(app, r'^/ws(?:/.*)?$')
        deployer = self.assert_in_spec(spec, 'deployer')
        self.assertIsInstance(deployer, base.Deployer)

    def test_tokens(self):
        # The tokens instance is correctly passed to the WebSocket handler.
        app = self.get_app()
        spec = self.get_url_spec(app, r'^/ws(?:/.*)?$')
        tokens = self.assert_in_spec(spec, 'tokens')
        self.assertIsInstance(tokens, auth.AuthenticationTokenHandler)

    def test_websocket_in_sandbox_mode(self):
        # The sandbox WebSocket handler is used if sandbox mode is enabled.
        app = self.get_app(sandbox=True)
        spec = self.get_url_spec(app, r'^/ws(?:/.*)?$')
        self.assertIsNotNone(spec)
        self.assertEqual(handlers.SandboxHandler, spec.handler_class)

    def test_proxy_excluded_in_sandbox_mode(self):
        # The juju-core HTTPS proxy is excluded if sandbox mode is enabled.
        app = self.get_app(sandbox=True)
        spec = self.get_url_spec(app, r'^/juju-core/(.*)$')
        self.assertIsNone(spec)

    def test_core_http_proxy(self):
        # The juju-core HTTPS proxy handler is properly set up.
        app = self.get_app()
        spec = self.get_url_spec(app, r'^/juju-core/(.*)$')
        self.assert_in_spec(
            spec, 'target_url', value='https://example.com:17070')

    def test_serving_gui_tests(self):
        # The server can be configured to serve GUI unit tests.
        app = self.get_app(testsroot='/my/tests/')
        spec = self.get_url_spec(app, r'^/test/(.*)$')
        self.assert_in_spec(spec, 'path', value='/my/tests/')

    def test_not_serving_gui_tests(self):
        # The server can be configured to avoid serving GUI unit tests.
        app = self.get_app(testsroot=None)
        spec = self.get_url_spec(app, r'^/test/(.*)$')
        self.assertIsNone(spec)


class TestRedirector(AppsTestMixin, unittest.TestCase):

    def get_app(self, **kwargs):
        """Create and return the server application.

        Use the options provided in kwargs.
        """
        options = mock.Mock(**kwargs)
        with mock.patch('guiserver.apps.options', options):
            return apps.redirector()

    def test_redirect_all(self):
        # Ensure all paths are handled by HttpsRedirectHandler.
        app = self.get_app()
        spec = self.get_url_spec(app, r'.*$')
        self.assertIsNotNone(spec)
        self.assertEqual(handlers.HttpsRedirectHandler, spec.handler_class)
