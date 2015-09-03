from datetime import date

import mock
from unittest2 import TestCase

from authorize import Address, AuthorizeClient, CreditCard, ECheckAccount
from authorize.client import AuthorizeCreditCard, AuthorizeECheck, \
    AuthorizeRecurring, AuthorizeSavedCard, AuthorizeTransaction
from test_api_customer import PROFILE


TRANSACTION_RESULT = {
    'cvv_response': 'P',
    'authorization_code': 'IKRAGJ',
    'response_code': '1',
    'amount': '20.00',
    'transaction_type': 'auth_only',
    'avs_response': 'Y',
    'response_reason_code': '1',
    'response_reason_text': 'This transaction has been approved.',
    'transaction_id': '2171062816',
}

ECHECK_TRANSACTION_RESULT = {
    'avs_response': 'P',
    'amount': '10.00',
    'authorization_code': '',
    'response_code': '1',
    'cvv_response': '',
    'response_reason_text': 'This transaction has been approved.',
    'transaction_id': '2239207440',
    'transaction_type': 'auth_capture',
    'response_reason_code': '1'
}


class ClientTests(TestCase):
    def setUp(self):
        self.transaction_api_patcher = mock.patch(
            'authorize.client.TransactionAPI')
        self.transaction_api = self.transaction_api_patcher.start()
        self.customer_api_patcher = mock.patch(
            'authorize.client.CustomerAPI')
        self.customer_api = self.customer_api_patcher.start()
        self.recurring_api_patcher = mock.patch(
            'authorize.client.RecurringAPI')
        self.recurring_api = self.recurring_api_patcher.start()
        self.client = AuthorizeClient('123', '456')
        self.year = date.today().year + 10
        self.credit_card = CreditCard('4111111111111111', self.year, 1, '911',
            'Jeff', 'Schenck')
        self.address = Address('45 Rose Ave', 'Venice', 'CA', '90291')
        self.echeck_account = ECheckAccount('021000021', '1234567890',
            'checking', 'First Bank', 'John Doe')

    def tearDown(self):
        self.transaction_api_patcher.stop()
        self.customer_api_patcher.stop()
        self.recurring_api_patcher.stop()

    def test_basic_authorize_client(self):
        self.transaction_api.reset_mock()
        self.customer_api.reset_mock()
        self.recurring_api.reset_mock()
        self.assertEqual(self.transaction_api.call_args, None)
        self.assertEqual(self.customer_api.call_args, None)
        self.assertEqual(self.recurring_api.call_args, None)
        client = AuthorizeClient('123', '456', False, False)
        self.assertEqual(self.transaction_api.call_args,
            (('123', '456', False, False), {}))
        self.assertEqual(self.customer_api.call_args,
            (('123', '456', False, False), {}))
        self.assertEqual(self.recurring_api.call_args,
            (('123', '456', False, False), {}))

    def test_authorize_client_payment_creators(self):
        self.assertTrue(isinstance(
            self.client.card(self.credit_card), AuthorizeCreditCard))
        self.assertTrue(isinstance(
            self.client.card(self.credit_card, self.address),
            AuthorizeCreditCard))
        self.assertTrue(isinstance(
            self.client.transaction('123'), AuthorizeTransaction))
        self.assertTrue(isinstance(
            self.client.saved_card('123|456'), AuthorizeSavedCard))
        self.assertTrue(isinstance(
            self.client.recurring('123'), AuthorizeRecurring))

    def test_authorize_credit_card_basic(self):
        card = AuthorizeCreditCard(self.client, self.credit_card)
        card = AuthorizeCreditCard(self.client, self.credit_card,
            self.address)
        repr(card)

    def test_authorize_credit_card_auth(self):
        self.client._transaction.auth.return_value = TRANSACTION_RESULT
        card = AuthorizeCreditCard(self.client, self.credit_card)
        result = card.auth(10)
        self.assertEqual(self.client._transaction.auth.call_args,
            ((10, self.credit_card, None, None), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')
        self.assertEqual(result.full_response, TRANSACTION_RESULT)

    def test_authorize_credit_card_capture(self):
        self.client._transaction.capture.return_value = TRANSACTION_RESULT
        card = AuthorizeCreditCard(self.client, self.credit_card)
        result = card.capture(10)
        self.assertEqual(self.client._transaction.capture.call_args,
            ((10, self.credit_card, None, None), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')
        self.assertEqual(result.full_response, TRANSACTION_RESULT)

    def test_authorize_credit_card_save(self):
        self.client._customer.create_saved_profile.return_value = ('1', '2')
        card = AuthorizeCreditCard(self.client, self.credit_card)
        result = card.save()
        self.assertEqual(self.client._customer.create_saved_payment.call_args,
            ((self.credit_card,), {'address': None}))
        self.assertTrue(isinstance(
            self.client._customer.create_saved_profile.call_args[0][0], str))
        self.assertTrue(isinstance(
            self.client._customer.create_saved_profile.call_args[0][1], list))
        self.assertTrue(isinstance(result, AuthorizeSavedCard))
        self.assertEqual(result.uid, '1|2')

    def test_authorize_credit_card_recurring(self):
        self.client._recurring.create_subscription.return_value = '1'
        card = AuthorizeCreditCard(self.client, self.credit_card)
        today = date.today()
        result = card.recurring(10, today, months=1)
        self.assertEqual(self.client._recurring.create_subscription.call_args,
            ((self.credit_card, 10, today), {'days': None, 'months': 1,
            'occurrences': None, 'trial_amount': None,
            'trial_occurrences': None}))
        self.assertTrue(isinstance(result, AuthorizeRecurring))
        self.assertEqual(result.uid, '1')

    def test_authorize_transaction_basic(self):
        transaction = AuthorizeTransaction(self.client, '123')
        repr(transaction)

    def test_authorize_transaction_settle(self):
        self.client._transaction.settle.return_value = TRANSACTION_RESULT
        transaction = AuthorizeTransaction(self.client, '123')

        # Test without amount
        result = transaction.settle()
        self.assertEqual(self.client._transaction.settle.call_args,
            (('123',), {'amount': None}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

        # Test with amount
        result = transaction.settle(10)
        self.assertEqual(self.client._transaction.settle.call_args,
            (('123',), {'amount': 10}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

    def test_authorize_transaction_credit(self):
        self.client._transaction.credit.return_value = TRANSACTION_RESULT
        transaction = AuthorizeTransaction(self.client, '123')

        # Test with amount
        result = transaction.credit('1111', 10)
        self.assertEqual(self.client._transaction.credit.call_args,
            (('1111', '123', 10), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

    def test_authorize_transaction_void(self):
        self.client._transaction.void.return_value = TRANSACTION_RESULT
        transaction = AuthorizeTransaction(self.client, '123')
        result = transaction.void()
        self.assertEqual(self.client._transaction.void.call_args,
            (('123',), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

    def test_authorize_saved_card_basic(self):
        saved = AuthorizeSavedCard(self.client, '1|2')
        repr(saved)

    def test_authorize_saved_card_auth(self):
        self.client._customer.auth.return_value = TRANSACTION_RESULT
        saved = AuthorizeSavedCard(self.client, '1|2')
        result = saved.auth(10)
        self.assertEqual(self.client._customer.auth.call_args,
            (('1', '2', 10, None), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

    def test_authorize_saved_card_capture(self):
        self.client._customer.capture.return_value = TRANSACTION_RESULT
        saved = AuthorizeSavedCard(self.client, '1|2')
        result = saved.capture(10)
        self.assertEqual(self.client._customer.capture.call_args,
            (('1', '2', 10, None), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2171062816')

    def test_authorize_saved_card_get_payment_info(self):
        address = Address('45 Rose Ave', 'Venice', 'CA', '90291')
        result_dict = {
            'first_name': 'Jeff', 'last_name': 'Shenck', 'address': address,
            'payment': PROFILE}
        self.client._customer.retrieve_saved_payment.return_value = result_dict
        saved = AuthorizeSavedCard(self.client, '1|2')
        result = saved.get_payment_info()

        self.assertEqual(result['first_name'], result_dict['first_name'])
        self.assertEqual(result['last_name'], result_dict['last_name'])
        self.assertEqual(
            result['address'].street, result_dict['address'].street)

    def test_authorized_saved_card_update(self):
        address = Address('45 Rose Ave', 'Venice', 'CA', '90291')
        result_dict = {
            'first_name': 'Jeff', 'last_name': 'Shenck', 'address': address,
            'payment': PROFILE}
        self.client._customer.retrieve_saved_payment.return_value = result_dict
        self.client._customer.update_saved_payment.return_value = None
        saved = AuthorizeSavedCard(self.client, '1|2')
        saved.update(address=address)

    def test_authorize_saved_card_delete(self):
        saved = AuthorizeSavedCard(self.client, '1|2')
        result = saved.delete()
        self.assertEqual(self.client._customer.delete_saved_payment.call_args,
            (('1', '2'), {}))

    def test_authorize_recurring_basic(self):
        recurring = AuthorizeRecurring(self.client, '123')
        repr(recurring)

    def test_authorize_recurring_update(self):
        recurring = AuthorizeRecurring(self.client, '123')
        recurring.update(occurrences=20)
        self.assertEqual(self.client._recurring.update_subscription.call_args,
            (('123',), {'amount': None, 'start': None, 'occurrences': 20,
            'trial_amount': None, 'trial_occurrences': None}))

    def test_authorize_recurring_delete(self):
        recurring = AuthorizeRecurring(self.client, '123')
        recurring.delete()
        self.assertEqual(self.client._recurring.delete_subscription.call_args,
            (('123',), {}))

    def test_authorize_echeck_web(self):
        self.client._transaction.echeck_web.return_value = ECHECK_TRANSACTION_RESULT
        echeck = self.client.echeck(self.echeck_account)
        result = echeck.web(10)
        self.assertEqual(self.client._transaction.echeck_web.call_args,
            ((10, self.echeck_account, None, None, False), {}))
        self.assertTrue(isinstance(result, AuthorizeTransaction))
        self.assertEqual(result.uid, '2239207440')
        self.assertEqual(result.full_response, ECHECK_TRANSACTION_RESULT)
