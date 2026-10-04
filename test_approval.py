import unittest

from app import app, load_app_items, save_app_items


class PhoneApprovalFlowTests(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_begin_phone_approval_creates_pending_request(self):
        response = self.client.get('/begin_phone_approval')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('token', payload)
        self.assertIn('qr_code', payload)
        self.assertIn('verify_url', payload)

    def test_approve_path_marks_request_as_approved(self):
        start = self.client.get('/begin_phone_approval')
        token = start.get_json()['token']

        approval = self.client.post(f'/approve/{token}')
        self.assertEqual(approval.status_code, 200)
        self.assertIn('approved', approval.get_data(as_text=True).lower())

        status = self.client.get(f'/approval-status/{token}')
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()['status'], 'approved')

    def test_laptop_unlock_can_complete_after_phone_approval(self):
        start = self.client.get('/begin_phone_approval')
        token = start.get_json()['token']

        self.client.post(f'/approve/{token}')
        self.client.get('/approval-status/{token}')

        unlock = self.client.get('/unlock')
        self.assertIn('Approve on phone', unlock.get_data(as_text=True))

    def test_app_launch_request_starts_phone_approval(self):
        response = self.client.get('/begin_app_launch',
                                   query_string={'app': 'legal-docs'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['app_name'], 'Legal Docs')
        self.assertEqual(payload['target_url'], '/vault-app/legal-docs')
        self.assertIn('token', payload)

    def test_vault_app_item_is_saved_and_visible(self):
        with self.client.session_transaction() as session:
            session['vault_unlocked'] = True

        save = self.client.post('/vault-app/legal-docs/items',
                                data={
                                    'title': 'Test document',
                                    'content': 'Private note',
                                })
        self.assertEqual(save.status_code, 302)

        page = self.client.get('/vault-app/legal-docs')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Test document', page.get_data(as_text=True))
        self.assertIn('Private note', page.get_data(as_text=True))

        items = load_app_items()
        items['legal-docs'] = [
            item for item in items['legal-docs']
            if item['title'] != 'Test document'
        ]
        save_app_items(items)


if __name__ == '__main__':
    unittest.main()
