from datetime import date
from decimal import Decimal

from suds import WebFault
from suds.client import Client

from authorize.exceptions import AuthorizeConnectionError, \
    AuthorizeInvalidError, AuthorizeResponseError


PROD_URL = 'https://api.authorize.net/soap/v1/Service.asmx?WSDL'
TEST_URL = 'https://apitest.authorize.net/soap/v1/Service.asmx?WSDL'

class RecurringAPI(object):
    def __init__(self, login_id, transaction_key, debug=True, test=False):
        self.url = TEST_URL if debug else PROD_URL
        self.login_id = login_id
        self.transaction_key = transaction_key

    @property
    def client(self):
        # Lazy instantiation of SOAP client, which hits the WSDL url
        if not hasattr(self, '_client'):
            self._client = Client(self.url)
        return self._client

    @property
    def client_auth(self):
        if not hasattr(self, '_client_auth'):
            self._client_auth = self.client.factory.create(
                'MerchantAuthenticationType')
            self._client_auth.name = self.login_id
            self._client_auth.transactionKey = self.transaction_key
        return self._client_auth

    def _make_call(self, service, *args):
        # Provides standard API call error handling
        method = getattr(self.client.service, service)
        try:
            response = method(self.client_auth, *args)
        except WebFault as e:
            raise AuthorizeConnectionError(e)
        if response.resultCode != 'Ok':
            error = response.messages[0][0]
            raise AuthorizeResponseError('%s: %s' % (error.code, error.text))
        return response

    def create_subscription(self, credit_card, amount, start,
            days=None, months=None, occurrences=None, trial_amount=None,
            trial_occurrences=None, invoice_number=None,
            description=None):
        """
        Creates a recurring subscription payment on the CreditCard provided.
        
        ``credit_card``
            The CreditCard instance to create the subscription for.
            Subscriptions require that you provide a first and last name with
            the credit card.
        
        ``amount``
            The amount to charge every occurrence, either as an int, float,
            or Decimal.
        
        ``start``
            The date to start the subscription, as a date object.
        
        ``days``
            Provide either the days or the months argument to indicate the
            interval at which the subscription should recur.

        ``months``
            Provide either the days or the months argument to indicate the
            interval at which the subscription should recur.
        
        ``occurrences``
            If provided, this is the number of times to charge the credit card
            before ending. If not provided, will last until canceled.
        
        ``trial_amount``
            If you want to have a trial period at a lower amount for this
            subscription, provide the amount. (Either both trial arguments
            should be provided, or neither.)
        
        ``trial_occurrences``
            If you want to have a trial period at a lower amount for this
            subscription, provide the number of occurences the trial period
            should last for. (Either both trial arguments should be provided,
            or neither.)
        """
        subscription = self.client.factory.create('ARBSubscriptionType')

        # Add the basic amount and payment fields
        amount = Decimal(str(amount)).quantize(Decimal('0.01'))
        subscription.amount = str(amount)
        payment_type = self.client.factory.create('PaymentType')
        credit_card_type = self.client.factory.create('CreditCardType')
        if invoice_number:
            order_type = self.client.factory.create('OrderType')
            order_type.invoiceNumber = str(invoice_number)
            order_type.description = description if description else ""
            subscription.order = order_type
        credit_card_type.cardNumber = credit_card.card_number
        credit_card_type.expirationDate = '{0}-{1:0>2}'.format(
            credit_card.exp_year, credit_card.exp_month)
        credit_card_type.cardCode = credit_card.cvv
        payment_type.creditCard = credit_card_type
        subscription.payment = payment_type
        if not (credit_card.first_name and credit_card.last_name):
            raise AuthorizeInvalidError('Subscriptions require first name '
                'and last name to be provided with the credit card.')
        subscription.billTo.firstName = credit_card.first_name
        subscription.billTo.lastName = credit_card.last_name

        # Add the fields for the payment schedule
        if (days and months) or not (days or months):
            raise AuthorizeInvalidError('Please provide either the months or '
                'days argument to define the subscription interval.')
        if days:
            try:
                days = int(days)
                assert days >= 7 and days <= 365
            except (AssertionError, ValueError):
                raise AuthorizeInvalidError('The interval days must be an '
                    'integer value between 7 and 365.')
            subscription.paymentSchedule.interval.unit = \
                self.client.factory.create('ARBSubscriptionUnitEnum').days
            subscription.paymentSchedule.interval.length = days
        elif months:
            try:
                months = int(months)
                assert months >= 1 and months <= 12
            except (AssertionError, ValueError):
                raise AuthorizeInvalidError('The interval months must be an '
                    'integer value between 1 and 12.')
            subscription.paymentSchedule.interval.unit = \
                self.client.factory.create('ARBSubscriptionUnitEnum').months
            subscription.paymentSchedule.interval.length = months
        if start < date.today():
            raise AuthorizeInvalidError('The start date for the subscription '
                'may not be in the past.')
        subscription.paymentSchedule.startDate = start.strftime('%Y-%m-%d')
        if occurrences is None:
            occurrences = 9999 # That's what they say to do in the docs
        subscription.paymentSchedule.totalOccurrences = occurrences

        # If a trial period has been specified, add those fields
        if trial_amount and trial_occurrences:
            subscription.paymentSchedule.trialOccurrences = trial_occurrences
            trial_amount = Decimal(str(trial_amount))
            trial_amount = trial_amount.quantize(Decimal('0.01'))
            subscription.trialAmount = str(trial_amount)
        elif trial_amount or trial_occurrences:
            raise AuthorizeInvalidError('To indicate a trial period, you '
                'must provide both a trial amount and occurrences.')

        # Make the API call to create the subscription
        response = self._make_call('ARBCreateSubscription', subscription)
        return response.subscriptionId

    def update_subscription(self, subscription_id, amount=None, start=None,
            occurrences=None, trial_amount=None, trial_occurrences=None,
            invoice_number=None, description=None):
        """
        Updates an existing recurring subscription payment. All fields to
        update are optional, and only the provided fields will be udpated.
        Many of the fields have particular restrictions that must be followed,
        as noted below.
        
        ``subscription_id``
            The subscription ID returned from the original create_subscription
            call for the subscription you want to update.
        
        ``amount``
            The updated amount to charge every occurrence, either as an int,
            float, or Decimal.
        
        ``start``
            The updated date to start the subscription, as a date object. This
            may only be udpated if no successful payments have been completed.
        
        ``occurrences``
            This updates the number of times to charge the credit card before
            ending.
        
        ``trial_amount``
            Updates the amount charged during the trial period. This may only
            be updated if you have not begun charging at the regular price.
        
        ``trial_occurrences``
            Updates the number of occurrences for the trial period. This may
            only be updated if you have not begun charging at the regular
            price.
        """
        subscription = self.client.factory.create('ARBSubscriptionType')

        # Add the basic subscription updates
        if amount:
            amount = Decimal(str(amount)).quantize(Decimal('0.01'))
            subscription.amount = str(amount)
        if start and start < date.today():
            raise AuthorizeInvalidError('The start date for the subscription '
                'may not be in the past.')
        if start:
            subscription.paymentSchedule.startDate = start.strftime('%Y-%m-%d')
        if occurrences:
            subscription.paymentSchedule.totalOccurrences = occurrences
        if trial_amount:
            trial_amount = Decimal(str(trial_amount))
            trial_amount = trial_amount.quantize(Decimal('0.01'))
            subscription.trialAmount = str(trial_amount)
        if trial_occurrences:
            subscription.paymentSchedule.trialOccurrences = trial_occurrences
        if invoice_number:
            order_type = self.client.factory.create('OrderType')
            order_type.invoiceNumber = str(invoice_number)
            order_type.description = description if description else ""
            subscription.order = order_type


    # Make the API call to update the subscription
        self._make_call('ARBUpdateSubscription', subscription_id,
            subscription)

    def delete_subscription(self, subscription_id):
        """
        Deletes an existing recurring subscription payment.
        
        ``subscription_id``
            The subscription ID returned from the original create_subscription
            call for the subscription you want to delete.
        """
        self._make_call('ARBCancelSubscription', subscription_id)
