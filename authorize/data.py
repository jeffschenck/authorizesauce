"""
This module provides the data structures for describing credit cards,
addresses, and checking accounts for use in executing charges.
"""

import calendar
from datetime import datetime
import re

from authorize.exceptions import AuthorizeInvalidError


CARD_TYPES = {
    'visa': r'4\d{12}(\d{3})?$',
    'amex': r'37\d{13}$',
    'mc': r'5[1-5]\d{14}$',
    'discover': r'6011\d{12}',
    'diners': r'(30[0-5]\d{11}|(36|38)\d{12})$'
}

class CreditCard(object):
    """
    Represents a credit card that can be charged.
    
    Pass in the credit card number, expiration date, CVV code, and optionally
    a first name and last name. The card will be validated upon instatiation
    and will raise an
    :class:`AuthorizeInvalidError <authorize.exceptions.AuthorizeInvalidError>`
    for invalid credit card numbers, past expiration dates, etc.
    """
    def __init__(self, card_number=None, exp_year=None, exp_month=None,
            cvv=None, first_name=None, last_name=None):
        self.card_number = re.sub(r'\D', '', str(card_number))
        self.exp_year = str(exp_year)
        self.exp_month = str(exp_month)
        self.cvv = str(cvv)
        self.first_name = first_name
        self.last_name = last_name
        self.validate()

    def __repr__(self):
        return '<CreditCard {0.card_type} {0.safe_number}>'.format(self)

    def validate(self):
        """
        Validates the credit card data and raises an
        :class:`AuthorizeInvalidError <authorize.exceptions.AuthorizeInvalidError>`
        if anything doesn't check out. You shouldn't have to call this
        yourself.
        """
        try:
            num = [int(n) for n in self.card_number]
        except ValueError:
            raise AuthorizeInvalidError('Credit card number is not valid.')
        if sum(num[::-2] + [sum(divmod(d * 2, 10)) for d in num[-2::-2]]) % 10:
            raise AuthorizeInvalidError('Credit card number is not valid.')
        if datetime.now() > self.expiration:
            raise AuthorizeInvalidError('Credit card is expired.')
        if not re.match(r'^\d{3,4}$', self.cvv):
            raise AuthorizeInvalidError('Credit card CVV is invalid format.')
        if not self.card_type:
            raise AuthorizeInvalidError('Credit card number is not valid.')

    @staticmethod
    def exp_time(exp_month, exp_year):
        exp_year, exp_month = int(exp_year), int(exp_month)
        return datetime(exp_year, exp_month,
            calendar.monthrange(exp_year, exp_month)[1],
            23, 59, 59)

    @property
    def expiration(self):
        """
        The credit card expiration date as a ``datetime`` object.
        """
        return self.exp_time(self.exp_month, self.exp_year)

    @property
    def safe_number(self):
        """
        The credit card number with all but the last four digits masked. This
        is useful for storing a representation of the card without keeping
        sensitive data.
        """
        mask = '*' * (len(self.card_number) - 4)
        return '{0}{1}'.format(mask, self.card_number[-4:])

    @property
    def card_type(self):
        """
        The credit card issuer, such as Visa or American Express, which is
        determined from the credit card number. Recognizes Visa, American
        Express, MasterCard, Discover, and Diners Club.
        """
        for card_type, card_type_re in CARD_TYPES.items():
            if re.match(card_type_re, self.card_number):
                return card_type

    def transaction_params(self):
        """
        Gets the Authorize.net API parameters to use to represent this
        credit card.
        """
        return {
            'x_card_num': self.card_number,
            'x_exp_date': self.expiration.strftime('%m-%Y'),
            'x_card_code': self.cvv,
            'x_first_name': self.first_name,
            'x_last_name': self.last_name,
        }


class Address(object):
    """
    Represents a billing address for a charge. Pass in the street, city, state
    and zip code, and optionally country for the address.
    """
    def __init__(self, street=None, city=None, state=None, zip_code=None,
            country='US'):
        self.street = street
        self.city = city
        self.state = state
        self.zip_code = zip_code
        self.country = country

    def __repr__(self):
        return '<Address {0.street}, {0.city}, {0.state} {0.zip_code}>' \
            .format(self)


class ECheckAccount(object):
    """
    Represents an eCheck account that can be charged.

    Note that eCheck.Net is a separate service through Authorize.net; you must
    sign up for it separately.

    ``routing_number``
        9-digit ABA routing number for the back

    ``account_number``
        Account number

    ``account_type``
        ``'checking'``, ``'businesschecking'``, or ``'savings'``

    ``bank_name``
        Name of the bank

    ``account_name``
        The name on the account
    """
    ACCOUNT_TYPES = ('checking', 'businesschecking', 'savings')

    def __init__(self, routing_number=None, account_number=None,
            account_type=None, bank_name=None, account_name=None):
        self.routing_number = str(routing_number)
        self.account_number = str(account_number)
        self.account_type = account_type
        self.bank_name = bank_name
        self.account_name = account_name

    def validate(self):
        """
        See :func:`CreditCard.validate`.
        """
        if not re.match(r'^\d9$', self.routing_number):
            raise AuthorizeInvalidError('Routing number should be a 9 digit number.')
        if not re.match(r'^\d{1,20}$', self.account_number):
            raise AuthorizeInvalidError('Account number should be a number between 1 and 20 digits.')
        if self.account_type.lower() not in self.ACCOUNT_TYPES:
            raise AuthorizeInvalidError('Invalid account type.')

    def transaction_params(self):
        """
        Gets the Authorize.net API parameters to use to represent this
        eCheck account.
        """
        return {
            'x_bank_aba_code': self.routing_number,
            'x_bank_acct_num': self.account_number,
            'x_bank_acct_type': self.account_type.upper(),
            'x_bank_name': self.bank_name,
            'x_bank_acct_name': self.account_name,
        }

    @property
    def safe_account_number(self):
        """
        The account number with all but the last four digits masked. This
        is useful for storing a representation of the account without keeping
        sensitive data.

        This matches the format used by Authorize.Net in its administrative
        interface: "XXXX" followed by the last four digits, regardless of the
        length of the account number.
        """
        return 'XXXX' + self.account_number[-4:]

    @property
    def safe_routing_number(self):
        """
        The routing number with all but the last four digits masked.
        Authorize.Net uses this format in its administrative interface.
        Routing numbers are generally public knowledge (see, for example, the
        American Banking Association's `search page`_), but which bank a
        particular person uses is still sensitive data.

        The format matches Authorize.Net: "XXXX" followed by the last four
        digits, even though routing numbers are nine digits long.

        .. _search page: http://routingnumber.aba.com/
        """
        return 'XXXX' + self.routing_number[-4:]
