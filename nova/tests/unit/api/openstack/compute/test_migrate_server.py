# Copyright 2011 OpenStack Foundation
# Copyright 2013 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_utils import uuidutils
import six
import webob

from nova.api.openstack.compute.legacy_v2.contrib import admin_actions as \
    migrate_server_v2
from nova.api.openstack.compute import migrate_server as \
    migrate_server_v21
from nova import exception
from nova import test
from nova.tests.unit.api.openstack.compute import admin_only_action_common
from nova.tests.unit.api.openstack import fakes


class MigrateServerTestsV21(admin_only_action_common.CommonTests):
    migrate_server = migrate_server_v21
    controller_name = 'MigrateServerController'
    validation_error = exception.ValidationError
    _api_version = '2.1'

    def setUp(self):
        super(MigrateServerTestsV21, self).setUp()
        self.controller = getattr(self.migrate_server, self.controller_name)()
        self.compute_api = self.controller.compute_api

        def _fake_controller(*args, **kwargs):
            return self.controller

        self.stubs.Set(self.migrate_server, self.controller_name,
                       _fake_controller)
        self.mox.StubOutWithMock(self.compute_api, 'get')

    def test_migrate(self):
        method_translations = {'_migrate': 'resize',
                               '_migrate_live': 'live_migrate'}
        body_map = {'_migrate_live': {'os-migrateLive': {'host': 'hostname',
                                       'block_migration': False,
                                       'disk_over_commit': False}}}
        args_map = {'_migrate_live': ((False, False, 'hostname'), {})}
        self._test_actions(['_migrate', '_migrate_live'], body_map=body_map,
                           method_translations=method_translations,
                           args_map=args_map)

    def test_migrate_none_hostname(self):
        method_translations = {'_migrate': 'resize',
                               '_migrate_live': 'live_migrate'}
        body_map = {'_migrate_live': {'os-migrateLive': {'host': None,
                                       'block_migration': False,
                                       'disk_over_commit': False}}}
        args_map = {'_migrate_live': ((False, False, None), {})}
        self._test_actions(['_migrate', '_migrate_live'], body_map=body_map,
                           method_translations=method_translations,
                           args_map=args_map)

    def test_migrate_with_non_existed_instance(self):
        body_map = {'os-migrateLive': {'host': 'hostname',
                                     'block_migration': False,
                                     'disk_over_commit': False}}
        self._test_actions_with_non_existed_instance(
            ['_migrate', '_migrate_live'], body_map=body_map)

    def test_migrate_raise_conflict_on_invalid_state(self):
        method_translations = {'_migrate': 'resize',
                               '_migrate_live': 'live_migrate'}
        body_map = {'os-migrateLive': {'host': 'hostname',
                                       'block_migration': False,
                                       'disk_over_commit': False}}
        args_map = {'_migrate_live': ((False, False, 'hostname'), {})}
        exception_arg = {'_migrate': 'migrate',
                         '_migrate_live': 'os-migrateLive'}
        self._test_actions_raise_conflict_on_invalid_state(
            ['_migrate', '_migrate_live'], body_map=body_map,
            args_map=args_map, method_translations=method_translations,
            exception_args=exception_arg)

    def test_actions_with_locked_instance(self):
        method_translations = {'_migrate': 'resize',
                               '_migrate_live': 'live_migrate'}
        body_map = {'_migrate_live': {'os-migrateLive': {'host': 'hostname',
                                       'block_migration': False,
                                       'disk_over_commit': False}}}
        args_map = {'_migrate_live': ((False, False, 'hostname'), {})}
        self._test_actions_with_locked_instance(
            ['_migrate', '_migrate_live'], body_map=body_map,
            args_map=args_map, method_translations=method_translations)

    def _test_migrate_exception(self, exc_info, expected_result):
        self.mox.StubOutWithMock(self.compute_api, 'resize')
        instance = self._stub_instance_get()
        self.compute_api.resize(self.context, instance).AndRaise(exc_info)

        self.mox.ReplayAll()
        self.assertRaises(expected_result,
                          self.controller._migrate,
                          self.req, instance['uuid'], {'migrate': None})

    def test_migrate_too_many_instances(self):
        exc_info = exception.TooManyInstances(overs='', req='', used=0,
                                              allowed=0, resource='')
        self._test_migrate_exception(exc_info, webob.exc.HTTPForbidden)

    def _test_migrate_live_succeeded(self, param):
        self.mox.StubOutWithMock(self.compute_api, 'live_migrate')
        instance = self._stub_instance_get()
        self.compute_api.live_migrate(self.context, instance, False,
                                      False, 'hostname')

        self.mox.ReplayAll()

        res = self.controller._migrate_live(self.req, instance.uuid,
                                            body={'os-migrateLive': param})
        # NOTE: on v2.1, http status code is set as wsgi_code of API
        # method instead of status_int in a response object.
        if self._api_version == '2.1':
            status_int = self.controller._migrate_live.wsgi_code
        else:
            status_int = res.status_int
        self.assertEqual(202, status_int)

    def test_migrate_live_enabled(self):
        param = {'host': 'hostname',
                 'block_migration': False,
                 'disk_over_commit': False}
        self._test_migrate_live_succeeded(param)

    def test_migrate_live_enabled_with_string_param(self):
        param = {'host': 'hostname',
                 'block_migration': "False",
                 'disk_over_commit': "False"}
        self._test_migrate_live_succeeded(param)

    def test_migrate_live_without_host(self):
        body = {'os-migrateLive':
                {'block_migration': False,
                 'disk_over_commit': False}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_migrate_live_without_block_migration(self):
        body = {'os-migrateLive':
                {'host': 'hostname',
                 'disk_over_commit': False}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_migrate_live_without_disk_over_commit(self):
        body = {'os-migrateLive':
                {'host': 'hostname',
                 'block_migration': False}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_migrate_live_with_invalid_block_migration(self):
        body = {'os-migrateLive':
                {'host': 'hostname',
                 'block_migration': "foo",
                 'disk_over_commit': False}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_migrate_live_with_invalid_disk_over_commit(self):
        body = {'os-migrateLive':
                {'host': 'hostname',
                 'block_migration': False,
                 'disk_over_commit': "foo"}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_migrate_live_missing_dict_param(self):
        body = {'os-migrateLive': {'dummy': 'hostname',
                                   'block_migration': False,
                                   'disk_over_commit': False}}
        self.assertRaises(self.validation_error,
                          self.controller._migrate_live,
                          self.req, fakes.FAKE_UUID, body=body)

    def _test_migrate_live_failed_with_exception(
                                         self, fake_exc,
                                         uuid=None,
                                         expected_exc=webob.exc.HTTPBadRequest,
                                         check_response=True):
        self.mox.StubOutWithMock(self.compute_api, 'live_migrate')

        instance = self._stub_instance_get(uuid=uuid)
        self.compute_api.live_migrate(self.context, instance, False,
                                      False, 'hostname').AndRaise(fake_exc)

        self.mox.ReplayAll()

        body = {'os-migrateLive':
                {'host': 'hostname',
                 'block_migration': False,
                 'disk_over_commit': False}}
        ex = self.assertRaises(expected_exc,
                               self.controller._migrate_live,
                               self.req, instance.uuid, body=body)
        if check_response:
            self.assertIn(six.text_type(fake_exc), ex.explanation)

    def test_migrate_live_compute_service_unavailable(self):
        self._test_migrate_live_failed_with_exception(
            exception.ComputeServiceUnavailable(host='host'))

    def test_migrate_live_invalid_hypervisor_type(self):
        self._test_migrate_live_failed_with_exception(
            exception.InvalidHypervisorType())

    def test_migrate_live_invalid_cpu_info(self):
        self._test_migrate_live_failed_with_exception(
            exception.InvalidCPUInfo(reason=""))

    def test_migrate_live_unable_to_migrate_to_self(self):
        uuid = uuidutils.generate_uuid()
        self._test_migrate_live_failed_with_exception(
                exception.UnableToMigrateToSelf(instance_id=uuid,
                                                host='host'),
                                                uuid=uuid)

    def test_migrate_live_destination_hypervisor_too_old(self):
        self._test_migrate_live_failed_with_exception(
            exception.DestinationHypervisorTooOld())

    def test_migrate_live_no_valid_host(self):
        self._test_migrate_live_failed_with_exception(
            exception.NoValidHost(reason=''))

    def test_migrate_live_invalid_local_storage(self):
        self._test_migrate_live_failed_with_exception(
            exception.InvalidLocalStorage(path='', reason=''))

    def test_migrate_live_invalid_shared_storage(self):
        self._test_migrate_live_failed_with_exception(
            exception.InvalidSharedStorage(path='', reason=''))

    def test_migrate_live_hypervisor_unavailable(self):
        self._test_migrate_live_failed_with_exception(
            exception.HypervisorUnavailable(host=""))

    def test_migrate_live_instance_not_active(self):
        self._test_migrate_live_failed_with_exception(
            exception.InstanceInvalidState(
                instance_uuid='', state='', attr='', method=''),
            expected_exc=webob.exc.HTTPConflict,
            check_response=False)

    def test_migrate_live_pre_check_error(self):
        self._test_migrate_live_failed_with_exception(
            exception.MigrationPreCheckError(reason=''))

    def test_migrate_live_migration_with_old_nova_not_safe(self):
        self._test_migrate_live_failed_with_exception(
            exception.LiveMigrationWithOldNovaNotSafe(server=''))

    def test_migrate_live_migration_with_unexpected_error(self):
        self._test_migrate_live_failed_with_exception(
            exception.MigrationError(reason=''),
            expected_exc=webob.exc.HTTPInternalServerError,
            check_response=False)


class MigrateServerTestsV2(MigrateServerTestsV21):
    migrate_server = migrate_server_v2
    controller_name = 'AdminActionsController'
    validation_error = webob.exc.HTTPBadRequest
    _api_version = '2'


class MigrateServerPolicyEnforcementV21(test.NoDBTestCase):

    def setUp(self):
        super(MigrateServerPolicyEnforcementV21, self).setUp()
        self.controller = migrate_server_v21.MigrateServerController()
        self.req = fakes.HTTPRequest.blank('')

    def test_migrate_policy_failed(self):
        rule_name = "os_compute_api:os-migrate-server:migrate"
        self.policy.set_rules({rule_name: "project:non_fake"})
        exc = self.assertRaises(
                                exception.PolicyNotAuthorized,
                                self.controller._migrate, self.req,
                                fakes.FAKE_UUID,
                                body={'migrate': {}})
        self.assertEqual(
                      "Policy doesn't allow %s to be performed." % rule_name,
                      exc.format_message())

    def test_migrate_live_policy_failed(self):
        rule_name = "os_compute_api:os-migrate-server:migrate_live"
        self.policy.set_rules({rule_name: "project:non_fake"})
        body_args = {'os-migrateLive': {'host': 'hostname',
                'block_migration': False,
                'disk_over_commit': False}}
        exc = self.assertRaises(
                                exception.PolicyNotAuthorized,
                                self.controller._migrate_live, self.req,
                                fakes.FAKE_UUID,
                                body=body_args)
        self.assertEqual(
                      "Policy doesn't allow %s to be performed." % rule_name,
                      exc.format_message())
