"""
This is your main interface to the Authorize.net API, where you feed in your
credentials and then interact to create transactions and so forth. You will
need to sign up for your own developer account and credentials at
Authorize.net_.

.. warning::

    To use the saved card and recurring billing functionality, you must have
    either or both set up in your Authorize.net account. You must sign up your
    account for the CIM (Customer Information Manager) service and/or the ARB
    (Automated Recurring Billing) service, each of which is an additional
    monthly charge. See the :ref:`authorize-net-documentation` for additional
    information.

.. _Authorize.net: http://developer.authorize.net/

"""
from uuid import uuid4

from authorize.apis.customer import CustomerAPI
from authorize.apis.recurring import RecurringAPI
from authorize.apis.transaction import TransactionAPI

class AuthorizeClient(object):
    """
    Instantiate the client with your login ID and transaction key from
    Authorize.net.
    
    The ``debug`` option determines whether to use debug mode
    for the APIs. This should be ``True`` in development and staging, and
    should be ``False`` in production when you want to actually process credit
    cards. You will need to pass in the appropriate login credentials
    depending on debug mode. The ``test`` option determines whether to run
    the standard API in test mode, which should generally be left ``False``,
    even in development and staging environments.
    """
    def __init__(self, login_id, transaction_key, debug=True, test=False):
        self.login_id = login_id
        self.transaction_key = transaction_key
        self.debug = debug
        self.test = test
        self._transaction = TransactionAPI(login_id, transaction_key,
            debug, test)
        self._recurring = RecurringAPI(login_id, transaction_key, debug, test)
        self._customer = CustomerAPI(login_id, transaction_key, debug, test)

    def card(self, credit_card, address=None, email=None):
        """
        To work with a credit card, pass in a
        :class:`CreditCard <authorize.data.CreditCard>` instance, and
        optionally an :class:`Address <authorize.data.Address>` instance. This
        will return an
        :class:`AuthorizeCreditCard <authorize.client.AuthorizeCreditCard>`
        instance you can then use to execute transactions.
        ``email`` is only required for those using European payment processors.
        """
        return AuthorizeCreditCard(self, credit_card, address=address,
                                   email=email)

    def transaction(self, uid):
        """
        To perform an action on a previous transaction, pass in the ``uid`` of
        that transaction as a string. This will return an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance you can then use to settle, credit or void that transaction.
        """
        return AuthorizeTransaction(self, uid)

    def saved_card(self, uid):
        """
        To create a new transaction from a saved card, pass in the ``uid`` of
        the saved card as a string. This will return an
        :class:`AuthorizeSavedCard <authorize.client.AuthorizeSavedCard>`
        instance you can then use to auth, capture, or create a credit.
        """
        return AuthorizeSavedCard(self, uid)

    def recurring(self, uid):
        """
        To update or cancel an existing recurring payment, pass in the ``uid``
        of the recurring payment as a string. This will return an
        :class:`AuthorizeRecurring <authorize.client.AuthorizeRecurring>`
        instance you can then use to udpate or cancel the payments.
        """
        return AuthorizeRecurring(self, uid)


class AuthorizeCreditCard(object):
    """
    This is the interface for working with a credit card. You use this to
    authorize or charge a credit card, as well as saving the credit card and
    creating recurring payments.
    
    Any operation performed on this instance returns another instance you can
    work with, such as a transaction, saved card, or recurring payment.
    """
    def __init__(self, client, credit_card, address=None, email=None):
        self._client = client
        self.credit_card = credit_card
        self.address = address
        self.email = email

    def __repr__(self):
        return '<AuthorizeCreditCard {0.credit_card.card_type} ' \
            '{0.credit_card.safe_number}>'.format(self)

    def auth(self, amount, order=None):
        """
        Authorize a transaction against this card for the specified amount.
        This verifies the amount is available on the card and reserves it.
        Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the transaction.
        """
        response = self._client._transaction.auth(
            amount, self.credit_card, self.address, order, self.email)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def capture(self, amount, order=None):
        """
        Capture a transaction immediately on this card for the specified
        amount. Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the transaction.
        """
        response = self._client._transaction.capture(
            amount, self.credit_card, self.address, order, self.email)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def save(self):
        """
        Saves the credit card on Authorize.net's servers so you can create
        transactions at a later date. Returns an
        :class:`AuthorizeSavedCard <authorize.client.AuthorizeSavedCard>`
        instance that you can save or use.
        """
        unique_id = uuid4().hex[:20]
        payment = self._client._customer.create_saved_payment(
            self.credit_card, address=self.address)
        profile_id, payment_ids = self._client._customer \
            .create_saved_profile(unique_id, [payment], email=self.email)
        uid = '{0}|{1}'.format(profile_id, payment_ids[0])
        return self._client.saved_card(uid)

    def recurring(self, amount, start, days=None, months=None,
            occurrences=None, trial_amount=None, trial_occurrences=None):
        """
        Creates a recurring payment with this credit card. Pass in the
        following arguments to set it up:
        
        ``amount``
            The amount to charge at each interval.
        
        ``start``
            The ``date`` or ``datetime`` at which to begin the recurring
            charges.
        
        ``days``
            The number of days in the billing cycle. You must provide either
            the ``days`` argument or the ``months`` argument.
        
        ``months``
            The number of months in the billing cycle. You must provide either
            the ``days`` argument or the ``months`` argument.
        
        ``occurrences`` *(optional)*
            The number of times the card should be billed before stopping. If
            not specified, it will continue indefinitely.
        
        ``trial_amount`` *(optional)*
            If you want to charge a lower amount for an introductory period,
            specify the amount.
        
        ``trial_occurrences`` *(optional)*
            If you want to charge a lower amount for an introductory period,
            specify the number of occurrences that period should last.

        Returns an
        :class:`AuthorizeRecurring <authorize.client.AuthorizeRecurring>`
        instance that you can save, update or delete.
        """
        uid = self._client._recurring.create_subscription(
            self.credit_card, amount, start, days=days, months=months,
            occurrences=occurrences, trial_amount=trial_amount,
            trial_occurrences=trial_occurrences)
        return self._client.recurring(uid)


class AuthorizeTransaction(object):
    """
    This is the interface for working with a previous transaction. It is
    returned by many other operations, or you can save the transaction's
    ``uid`` and reinstantiate it later.
    
    You can then use this transaction to settle a previous authorization,
    credit back a previous transaction, or void a previous authorization. Any
    such operation returns another transaction instance you can work with.
    
    Additionally, if you need to access the full raw result of the transaction
    it is stored in the ``full_response`` attribute on the class.
    """
    def __init__(self, client, uid):
        self._client = client
        self.uid = uid

    def __repr__(self):
        return '<AuthorizeTransaction {0.uid}>'.format(self)

    def settle(self, amount=None):
        """
        Settles this transaction if it is a previous authorization. If no
        ``amount`` is specified, the full amount will be settled; if a lower
        ``amount`` is provided, the lower amount will be settled; if a higher
        ``amount`` is given, it will result in an error. Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the settlement transaction.
        """
        response = self._client._transaction.settle(self.uid, amount=amount)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def credit(self, card_number, amount):
        """
        Creates a credit (refund) back on the original transaction. The
        ``card_number`` should be the last four digits of the credit card
        and the ``amount`` is the amount to credit the card. Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the credit transaction.
        
        Credit transactions are bound by a number of restrictions:
        
        * The original transaction must be an existing, settled charge. (Note
          that this is different than merely calling the
          :meth:`AuthorizeTransaction.settle <authorize.client.AuthorizeTransaction.settle>`
          method, which submits a payment for settlement. In production,
          Authorize.net actually settles charges once daily. Until a charge is
          settled, you should use
          :meth:`AuthorizeTransaction.void <authorize.client.AuthorizeTransaction.void>`
          instead.)
        * The amount of the credit (as well as the sum of all credits against
          this original transaction) must be less than or equal to the
          original amount charged.
        * The credit transaction must be submitted within 120 days of the date
          the original transaction was settled.
        """
        response = self._client._transaction.credit(
            card_number, self.uid, amount)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def void(self):
        """
        Voids a previous authorization that has not yet been settled. Returns
        an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the void transaction.
        """
        response = self._client._transaction.void(self.uid)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction


class AuthorizeSavedCard(object):
    """
    This is the interface for working with a saved credit card. It is returned
    by the
    :meth:`AuthorizeCreditCard.save <authorize.client.AuthorizeCreditCard.save>`
    method, or you can save a saved card's ``uid`` and reinstantiate it later.
    
    You can then use this saved card to create new authorizations, captures,
    and credits. Or you can delete this card from the Authorize.net database.
    The first three operations will all return a transaction instance to work
    with.

    You can also retrieve payment information with the
    :meth:`AuthorizeSavedCard.get_payment_info <authorize.client.AuthorizeSavedCard.get_payment_info`
    method.

    You can update this information by setting it and running the
    :meth:`AuthorizeSavedCard.update <authorize.client.AuthorizeSavedCard.update>`
    method.
    """

    def __init__(self, client, uid):
        self._client = client
        self.uid = uid
        self._profile_id, self._payment_id = uid.split('|')

    def __repr__(self):
        return '<AuthorizeSavedCard {0.uid}>'.format(self)

    def auth(self, amount):
        """
        Authorize a transaction against this card for the specified amount.
        This verifies the amount is available on the card and reserves it.
        Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the transaction.
        """
        response = self._client._customer.auth(
            self._profile_id, self._payment_id, amount)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def capture(self, amount):
        """
        Capture a transaction immediately on this card for the specified
        amount. Returns an
        :class:`AuthorizeTransaction <authorize.client.AuthorizeTransaction>`
        instance representing the transaction.
        """
        response = self._client._customer.capture(
            self._profile_id, self._payment_id, amount)
        transaction = self._client.transaction(response['transaction_id'])
        transaction.full_response = response
        return transaction

    def update(self, **kwargs):
        """
        Updates information about a saved card. You can use this to change the
        address associated with the card, or the name, or the user's email
        address. You may even update the expiration date.

        ``number`` *(optional)*
            An updated number for the card. In most cases, you should create a
            new card instead of using this.

        ``first_name`` *(optional)*
            The first name on the card.

        ``last_name`` *(optional)*
            The last name on the card

        ``address`` *(optional)*
            An :class:`Address <authorize.data.Address>` object that holds new
            billing address information for the card.

        ``email`` *(optional)*
            Updates the email associated with the card. Note that emails are
            actually stored on the customer profile. If you have multiple cards
            (payments) with the same profile, this will update the email for
            all of them.

        ``exp_month`` *(conditional)*
            If this option is specified, ``exp_year`` must also be specified,
            or it will be ignored.

            An integer representing the month of the card's expiration date.

        ``exp_year`` *(conditional)*
            If this option is specified, ``exp_month`` must also be specified,
            or it will be ignored.

            An integer representing the year of the card's expiration date.
        """
        settings = {'exp_month': None, 'exp_year': None}
        old_settings = self.get_payment_info()
        settings.update(old_settings)
        settings.update(**kwargs)
        self._client._customer.update_saved_payment(
            self._profile_id, self._payment_id, **settings)

    def get_payment_info(self):
        """
        Retrieves information about a card. It will return a dictionary
        containing the ``first_name`` and ``last_name`` on the card, as well
        as an ``address`` (a :class:`Address <authorize.data.Address>`
        instance), and the user's ``email``. These can be used, for instance,
        to populate a form which the user can fill to update their payment
        information.

        Note that the expiration date fields are masked by Authorize.net, and
        so are not returned by this function. Neither is the card number
        itself.
        """
        return self._client._customer.retrieve_saved_payment(
            self._profile_id, self._payment_id)

    def delete(self):
        """
        Removes this saved card from the Authorize.net database.
        """
        self._client._customer.delete_saved_payment(
            self._profile_id, self._payment_id)


class AuthorizeRecurring(object):
    """
    This is the interface for working with a recurring charge. It is returned
    by the
    :meth:`AuthorizeCreditCard.recurring <authorize.client.AuthorizeCreditCard.recurring>`
    method, or you can save a recurring payment's ``uid`` and reinstantiate it
    later.
    
    The recurring payment will continue charging automatically, but if you
    want to make changes to an existing recurring payment or to cancel a
    recurring payment, this provides the interface.
    """
    def __init__(self, client, uid):
        self._client = client
        self.uid = uid

    def __repr__(self):
        return '<AuthorizeRecurring {0.uid}>'.format(self)

    def update(self, amount=None, start=None, occurrences=None,
            trial_amount=None, trial_occurrences=None):
        """
        Updates the amount or status of the recurring payment. You may provide
        any or all fields and they will be updated appropriately, so long as
        none conflict. Fields work as described under the

        ``amount`` *(optional)*
            The amount to charge at each interval. Will only be applied to
            future charges.
        
        ``start`` *(optional)*
            The ``date`` or ``datetime`` at which to begin the recurring
            charges. You may only specify this option if the recurring charge
            has not yet begun.
        
        ``occurrences`` *(optional)*
            The number of times the card should be billed before stopping. If
            not specified, it will continue indefinitely.
        
        ``trial_amount`` *(optional)*
            If you want to charge a lower amount for an introductory period,
            specify the amount. You may specify this option only if there have
            not yet been any non-trial payments.
        
        ``trial_occurrences`` *(optional)*
            If you want to charge a lower amount for an introductory period,
            specify the number of occurrences that period should last. You may
            specify this option only if there have not yet been any non-trial
            payments.
        """
        self._client._recurring.update_subscription(self.uid,
            amount=amount, start=start, occurrences=occurrences,
            trial_amount=trial_amount, trial_occurrences=trial_occurrences)

    def delete(self):
        """
        Cancels any future charges from this recurring payment.
        """
        self._client._recurring.delete_subscription(self.uid)
