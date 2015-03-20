from datetime import date, timedelta

import mock
from suds import WebFault
from ssl import SSLError
from unittest2 import TestCase

from authorize.apis.recurring import PROD_URL, RecurringAPI, TEST_URL
from authorize.data import CreditCard
from authorize.exceptions import AuthorizeConnectionError, \
    AuthorizeInvalidError, AuthorizeResponseError


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

SUCCESS = AttrDict({
    'resultCode': 'Ok',
    'subscriptionId': '123',
})
ERROR = AttrDict({
    'resultCode': 'Error',
    'messages': [[AttrDict({
        'code': 'E00016',
        'text': 'The field type is invalid.',
    })]],
})

class RecurringAPITests(TestCase):
    def setUp(self):
        self.patcher = mock.patch(
            'authorize.apis.recurring.Client')
        self.Client = self.patcher.start()
        self.api = RecurringAPI('123', '456')

        # Make the factory creator return mocks that know what kind they are
        def create(kind):
            created = mock.Mock()
            created._kind = kind
            return created
        self.api.client.factory.create.side_effect = create

    def tearDown(self):
        self.patcher.stop()

    def test_basic_api(self):
        api = RecurringAPI('123', '456')
        self.assertEqual(api.url, TEST_URL)
        api = RecurringAPI('123', '456', debug=False)
        self.assertEqual(api.url, PROD_URL)

    def test_client_and_auth(self):
        self.Client.reset_mock()
        api = RecurringAPI('123', '456')
        self.assertEqual(self.Client.call_args, None)
        client_ = api.client
        self.assertEqual(self.Client.call_args[0][0], TEST_URL)
        client_auth = api.client_auth
        self.assertEqual(client_auth.name, '123')
        self.assertEqual(client_auth.transactionKey, '456')

    def test_make_call(self):
        self.api.client.service.TestService.return_value = SUCCESS
        result = self.api._make_call('TestService', 'foo')
        self.assertEqual(result, SUCCESS)
        self.assertEqual(self.api.client.service.TestService.call_args[0],
            (self.api.client_auth, 'foo'))

    def test_make_call_connection_error(self):
        self.api.client.service.TestService.side_effect = WebFault('a', 'b')
        self.assertRaises(AuthorizeConnectionError, self.api._make_call,
            'TestService', 'foo')
        self.assertEqual(self.api.client.service.TestService.call_args[0],
            (self.api.client_auth, 'foo'))

    def test_make_call_ssl_error(self):
        self.api.client.service.TestService.side_effect = SSLError('a', 'b')
        self.assertRaises(AuthorizeConnectionError, self.api._make_call,
                          'TestService', 'foo')
        self.assertEqual(self.api.client.service.TestService.call_args[0],
                         (self.api.client_auth, 'foo'))

    def test_make_call_response_error(self):
        self.api.client.service.TestService.return_value = ERROR
        try:
            self.api._make_call('TestService', 'foo')
        except AuthorizeResponseError as e:
            self.assertEqual(str(e), 'E00016: The field type is invalid.')
        self.assertEqual(self.api.client.service.TestService.call_args[0],
            (self.api.client_auth, 'foo'))

    def test_create_subscription(self):
        service = self.api.client.service.ARBCreateSubscription
        service.return_value = SUCCESS
        year = date.today().year + 10
        credit_card = CreditCard('4111111111111111', year, 1, '911',
            'Jeff', 'Schenck')
        nameless_credit_card = CreditCard('4111111111111111', year, 1, '911')
        start = date.today() + timedelta(days=7)

        # Test missing credit card name
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            nameless_credit_card, 10, start, months=1, occurrences=10)

        # Test both or neither of days and months arguments
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, occurrences=10)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, days=30, months=1, occurrences=10)

        # Test validation of months and of days arguments
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, days=1, occurrences=10)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, days=400, occurrences=10)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, months=0, occurrences=10)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, months=13, occurrences=10)

        # Test start date in the past
        past_start = date.today() - timedelta(days=1)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, past_start, months=1, occurrences=10)

        # Test providing only one of trial_amount and trial_occurrences
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, months=1, occurrences=10,
            trial_amount=5)
        self.assertRaises(AuthorizeInvalidError, self.api.create_subscription,
            credit_card, 10, start, months=1, occurrences=10,
            trial_occurrences=3)

        # Test basic successful subscription
        subscription_id = self.api.create_subscription(credit_card, 10, start,
            months=1, occurrences=10)
        self.assertEqual(subscription_id, '123')
        subscription = service.call_args[0][1]
        self.assertEqual(subscription._kind, 'ARBSubscriptionType')
        self.assertEqual(subscription.amount, '10.00')
        self.assertEqual(subscription.payment._kind, 'PaymentType')
        self.assertEqual(subscription.payment.creditCard._kind,
            'CreditCardType')
        self.assertEqual(subscription.payment.creditCard.cardNumber,
            '4111111111111111')
        self.assertEqual(subscription.payment.creditCard.expirationDate,
            '{0}-01'.format(year))
        self.assertEqual(subscription.payment.creditCard.cardCode, '911')
        self.assertEqual(subscription.billTo.firstName, 'Jeff')
        self.assertEqual(subscription.billTo.lastName, 'Schenck')
        self.assertEqual(subscription.paymentSchedule.interval.length, 1)
        self.assertEqual(subscription.paymentSchedule.startDate,
            start.strftime('%Y-%m-%d'))
        self.assertEqual(subscription.paymentSchedule.totalOccurrences, 10)

        # Test with days interval
        self.api.create_subscription(credit_card, 10, start, days=14,
            occurrences=10)
        subscription = service.call_args[0][1]
        self.assertEqual(subscription.paymentSchedule.interval.length, 14)

        # Test with infinite occurrences
        self.api.create_subscription(credit_card, 10, start, months=1)
        subscription = service.call_args[0][1]
        self.assertEqual(subscription.paymentSchedule.totalOccurrences, 9999)

        # Test with trial period
        self.api.create_subscription(credit_card, 10, start, months=1,
            occurrences=10, trial_amount=5, trial_occurrences=3)
        subscription = service.call_args[0][1]
        self.assertEqual(subscription.paymentSchedule.trialOccurrences, 3)
        self.assertEqual(subscription.trialAmount, '5.00')

    def test_update_subscription(self):
        service = self.api.client.service.ARBUpdateSubscription
        service.return_value = SUCCESS
        start = date.today() + timedelta(days=7)

        # Test start date in the past
        past_start = date.today() - timedelta(days=1)
        self.assertRaises(AuthorizeInvalidError, self.api.update_subscription,
            '1', start=past_start)

        # Test successful update with one argument
        self.api.update_subscription('1', start=start)
        subscription_id, subscription = service.call_args[0][1:]
        self.assertEqual(subscription_id, '1')
        self.assertEqual(subscription._kind, 'ARBSubscriptionType')
        self.assertEqual(subscription.paymentSchedule.startDate,
            start.strftime('%Y-%m-%d'))
        self.assertTrue(isinstance(subscription.amount, mock.Mock))
        self.assertTrue(isinstance(
            subscription.paymentSchedule.totalOccurrences, mock.Mock))
        self.assertTrue(isinstance(subscription.trialAmount, mock.Mock))
        self.assertTrue(isinstance(
            subscription.paymentSchedule.trialOccurrences, mock.Mock))

        # Test successful update with all arguments
        self.api.update_subscription('1', amount=25, start=start,
            occurrences=21, trial_amount=24, trial_occurrences=1)
        subscription_id, subscription = service.call_args[0][1:]
        self.assertEqual(subscription_id, '1')
        self.assertEqual(subscription._kind, 'ARBSubscriptionType')
        self.assertTrue(subscription.amount, '25.00')
        self.assertEqual(subscription.paymentSchedule.startDate,
            start.strftime('%Y-%m-%d'))
        self.assertTrue(subscription.paymentSchedule.totalOccurrences, 21)
        self.assertTrue(subscription.trialAmount, '24.00')
        self.assertTrue(subscription.paymentSchedule.trialOccurrences, 1)

    def test_delete_subscription(self):
        service = self.api.client.service.ARBCancelSubscription
        service.return_value = SUCCESS
        self.api.delete_subscription('1')
        self.assertEqual(service.call_args[0][1], '1')
