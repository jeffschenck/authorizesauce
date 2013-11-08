"""
This module provides the data structures for describing credit cards and
addresses for use in executing charges.
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
ACCOUNT_TYPES = ('checking', 'savings')


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
            num = map(int, self.card_number)
        except ValueError:
            raise AuthorizeInvalidError('Credit card number is not valid.')
        if sum(num[::-2] + map(lambda d: sum(divmod(d * 2, 10)), num[-2::-2])) % 10:
            raise AuthorizeInvalidError('Credit card number is not valid.')
        if datetime.now() > self.expiration:
            raise AuthorizeInvalidError('Credit card is expired.')
        if not re.match(r'^[\d+]{3,4}$', self.cvv):
            raise AuthorizeInvalidError('Credit card CVV is invalid format.')
        if not self.card_type:
            raise AuthorizeInvalidError('Credit card number is not valid.')

    @property
    def expiration(self):
        """
        The credit card expiration date as a ``datetime`` object.
        """
        return datetime(int(self.exp_year), int(self.exp_month),
            calendar.monthrange(int(self.exp_year), int(self.exp_month))[1],
            23, 59, 59)

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


class BankAccount(object):
    """
    Represents a bank account that can be charged.
    
    Pass in a US bank account number, expiration date, CVV code, and optionally
    a first name and last name. The account will be validated upon instantiation
    and will raise an
    :class:`AuthorizeInvalidError <authorize.exceptions.AuthorizeInvalidError>`
    for invalid bank account numbers, past expiration dates, etc.
    """
    def __init__(self, bank_name=None, account_type=None,
                 routing_number=None, account_number=None, name=None,
                 echeck_type='WEB', customer_type='individual'):
        self.account_type = account_type
        self.routing_number = re.sub(r'\D', '', str(routing_number))
        self.account_number = re.sub(r'\D', '', str(account_number))
        self.name = name
        self.first_name = name.split(' ')[0]
        self.last_name = name.split(' ')[-1]
        self.echeck_type = echeck_type
        self.customer_type = customer_type
        self.validate()

    def __repr__(self):
        return '<BankAccount {0.account_type} {0.safe_number}>'.format(self)

    def validate(self):
        """
        Validates the bank account data and raises an
        :class:`AuthorizeInvalidError <authorize.exceptions.AuthorizeInvalidError>`
        if anything doesn't check out. You shouldn't have to call this
        yourself.
        """
        self._validate_aba_micr(self.routing_number)
        if not self.bank_name:
            raise AuthorizeInvalidError('Bank name is not valid.')
        if not self.account_type:
            raise AuthorizeInvalidError('Bank account type is not valid.')
        try:
            num = map(int, self.account_number)
        except ValueError:
            raise AuthorizeInvalidError('Bank account number is not valid.')
        if not (len(num) >=4 and len(num) <= 17):
            raise AuthorizeInvalidError('Bank account number is not valid.')

    @staticmethod
    def _validate_aba_micr(routing_number):
        """
        Validates a US ABA standard MICR routing number and raises an
        :class:`AuthorizeInvalidError <authorize.exceptions.AuthorizeInvalidError>`
        if anything doesn't check out.
        """
        try:
            num = map(int, routing_number)
        except (ValueError, TypeError):
            raise AuthorizeInvalidError('Bank routing number is not valid.')
        if len(routing_number) != 9:
            raise AuthorizeInvalidError('Bank routing number is not valid.')
        checksum = (7 * (num[0] + num[3] + num[6]) +
                    3 * (num[1] + num[4] + num[7]) +
                    9 * (num[2] + num[5])) % 10
        if num[8] != checksum:
            raise AuthorizeInvalidError('Bank routing number is not valid.')

    @property
    def safe_number(self):
        """
        The bank account number with all but the last four digits masked. This
        is useful for storing a representation of the account without keeping
        sensitive data.
        """
        mask = '*' * (len(self.account_number) - 4)
        return '{0}{1}'.format(mask, self.account_number[-4:])

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
