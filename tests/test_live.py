# coding: utf-8
"""
Tests against the sandbox Authorize.net API. Slow, requires internet.
"""

from datetime import date, timedelta
import os
import random

from unittest2 import skipUnless, TestCase

from authorize import Address, AuthorizeClient, CreditCard
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
        # thinks the transactions are duplicates and rejects them
        self.amount1 = random.randrange(100, 100000) / 100.0
        self.amount2 = random.randrange(100, 100000) / 100.0
        self.client = AuthorizeClient(TEST_LOGIN_ID, TEST_TRANSACTION_KEY)
        self.year = date.today().year + 10
        self.credit_card = CreditCard('4111111111111111', self.year, 1, '911',
            u"jåff", u'Sch∂nck')
        self.address = Address('45 Rose Ave', 'Venice', 'CA', '90291')

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

    def test_recurring(self):
        card = self.client.card(self.credit_card, self.address)
        start = date.today() + timedelta(days=7)
        recurring = card.recurring(self.amount1, start, months=1, occurrences=10)
        recurring.update(amount=self.amount2, trial_amount=self.amount2 - 0.5, trial_occurrences=3)
        recurring_from_id = self.client.recurring(recurring.uid)
        recurring_from_id.delete()
