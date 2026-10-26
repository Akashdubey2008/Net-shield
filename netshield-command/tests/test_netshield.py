import unittest
import os
import json
import tempfile
from app import app
import database


class NetShieldTestCase(unittest.TestCase):
    def setUp(self):
        # Create a fresh temporary database for each test
        self.db_fd, self.db_path = tempfile.mkstemp()
        database.DB_PATH = self.db_path
        database.init_db(self.db_path)

        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-12345'
        self.client = app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    # ---------------- Auth Tests ---------------- #

    def test_unauthenticated_access_blocked(self):
        """Protected endpoints should return 401 Unauthorized for unauthenticated callers."""
        endpoints = [
            ('GET', '/api/state'),
            ('POST', '/api/message'),
            ('POST', '/api/link'),
            ('POST', '/api/reset'),
            ('POST', '/api/summary'),
            ('POST', '/api/broadcast'),
            ('GET', '/api/messages/export'),
        ]
        for method, ep in endpoints:
            if method == 'GET':
                resp = self.client.get(ep)
            else:
                resp = self.client.post(ep, json={})
            self.assertEqual(resp.status_code, 401, f"{ep} did not enforce authentication")

    def test_auth_me_unauthenticated(self):
        """GET /api/auth/me returns authenticated: False when not logged in."""
        resp = self.client.get('/api/auth/me')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data.get('authenticated'))

    def test_login_success(self):
        """Valid credentials authenticate user and establish session."""
        resp = self.client.post('/api/auth/login', json={
            'username': 'commander',
            'password': 'password123'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'commander')
        self.assertEqual(data['user']['callsign'], 'VANGUARD-1')

        # Check /api/auth/me now returns authenticated user
        me_resp = self.client.get('/api/auth/me')
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.get_json()
        self.assertTrue(me_data['authenticated'])
        self.assertEqual(me_data['user']['username'], 'commander')

    def test_login_invalid_credentials(self):
        """Invalid passwords should be rejected with 401."""
        resp = self.client.post('/api/auth/login', json={
            'username': 'commander',
            'password': 'wrongpassword'
        })
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertIn('error', data)

    def test_user_registration(self):
        """New operator registration should succeed and allow immediate authentication."""
        resp = self.client.post('/api/auth/register', json={
            'username': 'echo_sentinel',
            'password': 'securepassword',
            'full_name': 'Sgt. Jack Cooper',
            'callsign': 'BT-7274',
            'role': 'Communications Officer',
            'unit_id': 'E'
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data['user']['username'], 'echo_sentinel')
        self.assertEqual(data['user']['callsign'], 'BT-7274')
        self.assertEqual(data['user']['unit_id'], 'E')

        # Verify state endpoint is accessible now
        state_resp = self.client.get('/api/state')
        self.assertEqual(state_resp.status_code, 200)

    def test_registration_validation(self):
        """Short passwords or invalid usernames should be rejected with 400."""
        # Short password
        resp = self.client.post('/api/auth/register', json={
            'username': 'validuser',
            'password': '123',
            'full_name': 'Test User',
            'callsign': 'TEST-1'
        })
        self.assertEqual(resp.status_code, 400)

        # Duplicate username
        resp2 = self.client.post('/api/auth/register', json={
            'username': 'commander',
            'password': 'password123',
            'full_name': 'Duplicate User',
            'callsign': 'DUP-1'
        })
        self.assertEqual(resp2.status_code, 409)

    def test_logout(self):
        """Logging out should terminate the authenticated session."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})
        resp = self.client.post('/api/auth/logout')
        self.assertEqual(resp.status_code, 200)

        # Subsequent protected call should fail with 401
        state_resp = self.client.get('/api/state')
        self.assertEqual(state_resp.status_code, 401)

    # ---------------- Messaging & Identity Tests ---------------- #

    def test_authenticated_message_dispatch_with_identity(self):
        """Messages sent by an operator must include their verified identity and SHA-256 signature."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})

        resp = self.client.post('/api/message', json={
            'source': 'CC',
            'target': 'A',
            'priority': 'High',
            'message': 'Command Center to Alpha Unit: Acknowledge tactical telemetry feed.'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        msg = data['message']

        # Verify identity fields
        self.assertEqual(msg['source'], 'CC')
        self.assertEqual(msg['target'], 'A')
        self.assertEqual(msg['status'], 'Delivered')
        self.assertEqual(msg['path'], ['CC', 'A'])
        self.assertEqual(msg['sender']['username'], 'commander')
        self.assertEqual(msg['sender']['callsign'], 'VANGUARD-1')
        self.assertEqual(msg['sender']['name'], 'Capt. Sarah Vance')
        self.assertTrue(msg['signature'].startswith('SIG-'))
        self.assertTrue(msg['verified'])

    def test_field_specialist_identity_restriction(self):
        """Field Specialists should only transmit directly from their assigned unit."""
        self.client.post('/api/auth/login', json={'username': 'bravo_tech', 'password': 'password123'})
        # bravo_tech is assigned to unit B, so attempting to dispatch from CC should be restricted
        resp = self.client.post('/api/message', json={
            'source': 'CC',
            'target': 'A',
            'priority': 'Normal',
            'message': 'Unauthorized spoof attempt.'
        })
        self.assertEqual(resp.status_code, 403)

        # But sending from assigned unit B should succeed!
        valid_resp = self.client.post('/api/message', json={
            'source': 'B',
            'target': 'CC',
            'priority': 'Normal',
            'message': 'Bravo Unit telemetry check nominal.'
        })
        self.assertEqual(valid_resp.status_code, 200)

    def test_dijkstra_rerouting_on_link_failure(self):
        """Dijkstra pathfinding must compute alternative routes when intermediate links fail."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})

        # Toggle direct CC-A link to failed
        resp_toggle = self.client.post('/api/link', json={'a': 'CC', 'b': 'A'})
        self.assertEqual(resp_toggle.status_code, 200)

        # Send message from CC to A: direct link CC-A is failed, but CC-B-A should be found!
        resp_msg = self.client.post('/api/message', json={
            'source': 'CC',
            'target': 'A',
            'priority': 'Normal',
            'message': 'Rerouted packet test.'
        })
        self.assertEqual(resp_msg.status_code, 200)
        msg = resp_msg.get_json()['message']
        self.assertEqual(msg['status'], 'Delivered')
        self.assertNotIn(['CC', 'A'], [msg['path']])
        self.assertEqual(msg['path'][0], 'CC')
        self.assertEqual(msg['path'][-1], 'A')
        self.assertIn('B', msg['path'])

    def test_broadcast_alert(self):
        """Command Officers can dispatch priority broadcast to all units simultaneously."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})
        resp = self.client.post('/api/broadcast', json={'message': 'Urgent perimeter alert!'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('broadcast', data)
        self.assertEqual(len(data['broadcast']), 5)  # Nodes A, B, C, D, E

    def test_ai_situation_summary(self):
        """Situation summary returns operational metrics and active watch officer."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})
        resp = self.client.post('/api/summary', json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('summary', data)
        self.assertIn('VANGUARD-1', data['summary'])

    def test_field_specialist_strict_restrictions(self):
        """Field Specialists (Level 1) have strictly restricted communication and management powers."""
        self.client.post('/api/auth/login', json={'username': 'bravo_tech', 'password': 'password123'})

        # 1. Cannot toggle links
        resp = self.client.post('/api/link', json={'a': 'CC', 'b': 'A'})
        self.assertEqual(resp.status_code, 403)

        # 2. Cannot broadcast
        resp = self.client.post('/api/broadcast', json={'message': 'Unauthorized broadcast'})
        self.assertEqual(resp.status_code, 403)

        # 3. Cannot generate AI summary
        resp = self.client.post('/api/summary', json={})
        self.assertEqual(resp.status_code, 403)

        # 4. Cannot export logs
        resp = self.client.get('/api/messages/export?format=csv')
        self.assertEqual(resp.status_code, 403)

        # 5. Cannot transmit Urgent priority
        resp = self.client.post('/api/message', json={'source': 'B', 'target': 'CC', 'priority': 'Urgent', 'message': 'Urgent test'})
        self.assertEqual(resp.status_code, 403)

        # 6. Cannot transmit High priority
        resp = self.client.post('/api/message', json={'source': 'B', 'target': 'CC', 'priority': 'High', 'message': 'High test'})
        self.assertEqual(resp.status_code, 403)

        # 7. Cannot transmit to non-adjacent unit (Unit B to Unit D is non-adjacent in mesh)
        resp = self.client.post('/api/message', json={'source': 'B', 'target': 'D', 'priority': 'Normal', 'message': 'Non-adjacent hop test'})
        self.assertEqual(resp.status_code, 403)

        # 8. Legitimate transmission from B to adjacent A or CC with Normal/Low priority succeeds!
        resp_valid = self.client.post('/api/message', json={'source': 'B', 'target': 'A', 'priority': 'Normal', 'message': 'Adjacent patrol check.'})
        self.assertEqual(resp_valid.status_code, 200)
        self.assertEqual(resp_valid.get_json()['message']['status'], 'Delivered')

    def test_comms_officer_tiered_powers(self):
        """Communications Officers (Level 2) have tactical comms powers but cannot toggle links or fleet broadcast."""
        self.client.post('/api/auth/login', json={'username': 'alpha_lead', 'password': 'password123'})

        # 1. Cannot toggle links or restore
        resp = self.client.post('/api/link', json={'a': 'CC', 'b': 'A'})
        self.assertEqual(resp.status_code, 403)
        resp_reset = self.client.post('/api/reset', json={})
        self.assertEqual(resp_reset.status_code, 403)

        # 2. Cannot broadcast
        resp_bc = self.client.post('/api/broadcast', json={'message': 'Unauthorized broadcast'})
        self.assertEqual(resp_bc.status_code, 403)

        # 3. Cannot send Urgent priority (reserved for Commander)
        resp_urg = self.client.post('/api/message', json={'source': 'A', 'target': 'E', 'priority': 'Urgent', 'message': 'Urgent test'})
        self.assertEqual(resp_urg.status_code, 403)

        # 4. CAN send High priority across full mesh (e.g. A to non-adjacent E)
        resp_high = self.client.post('/api/message', json={'source': 'A', 'target': 'E', 'priority': 'High', 'message': 'Tactical comms relay.'})
        self.assertEqual(resp_high.status_code, 200)
        self.assertEqual(resp_high.get_json()['message']['status'], 'Delivered')

        # 5. CAN dispatch from Command Center (CC)
        resp_cc = self.client.post('/api/message', json={'source': 'CC', 'target': 'D', 'priority': 'Normal', 'message': 'Dispatch from CC.'})
        self.assertEqual(resp_cc.status_code, 200)

        # 6. CAN generate AI summary
        resp_sum = self.client.post('/api/summary', json={})
        self.assertEqual(resp_sum.status_code, 200)

        # 7. CAN export logs
        resp_exp = self.client.get('/api/messages/export?format=json')
        self.assertEqual(resp_exp.status_code, 200)

    def test_simulate_incoming_transmission(self):
        """Simulate incoming transmission sends a message targeted to the operator's assigned station."""
        self.client.post('/api/auth/login', json={'username': 'bravo_tech', 'password': 'password123'})

        resp = self.client.post('/api/message/simulate-incoming', json={})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('message', data)
        msg = data['message']

        # Destination must be the operator's unit (Bravo Unit: B)
        self.assertEqual(msg['target'], 'B')
        self.assertNotEqual(msg['source'], 'B')
        self.assertEqual(msg['status'], 'Delivered')
        self.assertTrue(msg['signature'].startswith('SIG-'))

    def test_export_messages(self):
        """Messages can be exported in CSV and JSON formats."""
        self.client.post('/api/auth/login', json={'username': 'commander', 'password': 'password123'})
        self.client.post('/api/message', json={'source': 'CC', 'target': 'B', 'message': 'Log export check'})

        # JSON Export
        resp_json = self.client.get('/api/messages/export?format=json')
        self.assertEqual(resp_json.status_code, 200)
        data = resp_json.get_json()
        self.assertGreaterEqual(data['count'], 1)

        # CSV Export
        resp_csv = self.client.get('/api/messages/export?format=csv')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.mimetype, 'text/csv')
        self.assertIn(b'Sender Callsign', resp_csv.data)


if __name__ == '__main__':
    unittest.main()
