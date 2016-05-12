"""
Tests against the sandbox Authorize.net API. Slow, requires internet.
"""

from datetime import date, timedelta
import os
import random

from unittest2 import skipUnless, TestCase

from authorize import Address, AuthorizeClient, CreditCard, ECheckAccount
from authorize.exceptions import AuthorizeResponseError


# Authorize.net developer login for test (https://test.authorize.net)
# user: authorizepy0
# pass: LZ5MMGpr
# gateway id: 355553

SKIP_MESSAGE = 'Live tests only run if the AUTHORIZE_LIVE_TESTS ' \
    'environment variable is true.'
TEST_LOGIN_ID = '285tUPuS'
TEST_TRANSACTION_KEY = '58JKJ4T95uee75wd'

@skipUnless(os.environ.get('AUTHORIZE_LIVE_TESTS'), SKIP_MESSAGE)
class AuthorizeLiveTests(TestCase):
    def setUp(self):
        # Random in testing feels gross, otherwise running the same test
        # suite in quick succession produces failures because Authorize.net
        # thinks the transactions are duplicates and rejects them.
        #
        # Sandbox accounts have a default eCheck.Net Maximum Transaction Size
        # of $100.00, so use that as our maximum.
        self.amount1 = random.randrange(100, 10000) / 100.0
        self.amount2 = random.randrange(100, 10000) / 100.0
        self.client = AuthorizeClient(TEST_LOGIN_ID, TEST_TRANSACTION_KEY)
        self.year = date.today().year + 10
        self.credit_card = CreditCard('4111111111111111', self.year, 1, '911',
            'Jeff', 'Schenck')
        self.address = Address('45 Rose Ave', 'Venice', 'CA', '90291')
        self.echeck_account = ECheckAccount('021000021', '1234567890',
            'checking', 'First Bank', 'John Doe')

    def test_credit_card(self):
        card = self.client.card(self.credit_card, self.address)
        transaction = card.auth(self.amount1)
        transaction.void()
        self.assertRaises(AuthorizeResponseError, transaction.settle)

    def test_saved_card(self):
        card = self.client.card(self.credit_card, self.address)
        saved = card.save()
        saved.auth(self.amount1).settle()
        saved.capture(self.amount1)
        saved_from_id = self.client.saved_card(saved.uid)
        saved_from_id.delete()

    def test_get_saved_card_info(self):
        card = self.client.card(self.credit_card, self.address)
        saved = card.save()
        results = saved.get_payment_info()
        self.assertEqual(results['address'].street, self.address.street)
        self.assertEqual(results['first_name'], self.credit_card.first_name)
        saved.delete()

    def test_update_card_info(self):
        card = self.client.card(self.credit_card, self.address)
        saved = card.save()
        saved.update(first_name='NotJeff')
        info = saved.get_payment_info()
        self.assertEqual(info['first_name'], 'NotJeff')
        self.assertEqual(info['last_name'], 'Schenck')
        saved.delete()

    def test_recurring(self):
        card = self.client.card(self.credit_card, self.address)
        start = date.today() + timedelta(days=7)
        recurring = card.recurring(self.amount1, start, months=1, occurrences=10)
        recurring.update(amount=self.amount2, trial_amount=self.amount2 - 0.5, trial_occurrences=3)
        recurring_from_id = self.client.recurring(recurring.uid)
        recurring_from_id.delete()

    def test_echeck(self):
        echeck = self.client.echeck(self.echeck_account)
        transaction = echeck.web(self.amount1)
        transaction.void()
        self.assertRaises(AuthorizeResponseError, transaction.settle)
