from decimal import Decimal
from six import PY2, b, text_type
from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import urlopen

from authorize.exceptions import AuthorizeConnectionError, \
    AuthorizeResponseError


PROD_URL = 'https://secure.authorize.net/gateway/transact.dll'
TEST_URL = 'https://test.authorize.net/gateway/transact.dll'
RESPONSE_FIELDS = {
    0: 'response_code',
    2: 'response_reason_code',
    3: 'response_reason_text',
    4: 'authorization_code',
    5: 'avs_response',
    6: 'transaction_id',
    9: 'amount',
    11: 'transaction_type',
    38: 'cvv_response',
}

DEFAULT_CHARSET = 'iso-8859-1'


def get_content_charset(resource):
    """Gets the charset encoding used in the given urlopen response."""
    if PY2:
        # Python 2 doesn't support get_content_charset, provides getparam
        # instead of get_param, and doesn't support the failobj option.
        charset = resource.headers.getparam('charset')
        return charset and charset.lower() or DEFAULT_CHARSET
    else:
        return resource.headers.get_content_charset(failobj=DEFAULT_CHARSET)


def parse_response(response):
    response = response.split(';')
    fields = {}
    for index, name in RESPONSE_FIELDS.items():
        fields[name] = response[index]
    return fields


def safe_unicode_to_str(string):
    try:
        return str(string)
    except UnicodeEncodeError:
        return string.encode('utf-8')


def convert_params_to_byte_str(params):
    converted_params = {}
    for key, value in params.items():
        if isinstance(key, text_type):
            key = safe_unicode_to_str(key)
        if isinstance(value, text_type):
            value = safe_unicode_to_str(value)
        converted_params[key] = value
    return converted_params


class TransactionAPI(object):
    def __init__(self, login_id, transaction_key, debug=True, test=False):
        self.url = TEST_URL if debug else PROD_URL
        self.base_params = {
            'x_login': login_id,
            'x_tran_key': transaction_key,
            'x_version': '3.1',
            'x_test_request': 'TRUE' if test else 'FALSE',
            'x_delim_data': 'TRUE',
            'x_delim_char': ';',
        }

    def _make_call(self, params):
        params = convert_params_to_byte_str(params)
        params = urlencode(params)
        try:
            resource = urlopen(self.url, data=b(params))
            response = resource.read().decode(
                get_content_charset(resource) or DEFAULT_CHARSET)
        except IOError as e:
            raise AuthorizeConnectionError(e)
        fields = parse_response(response)
        if fields['response_code'] != '1':
            e = AuthorizeResponseError(
                '{0} full_response={1!r}'.format(
                    fields['response_reason_text'], fields
                )
            )
            e.full_response = fields
            raise e
        return fields

    def _add_params(self, params, credit_card=None, address=None, email=None):
        if credit_card:
            params.update({
                'x_card_num': credit_card.card_number,
                'x_exp_date': credit_card.expiration.strftime('%m-%Y'),
                'x_card_code': credit_card.cvv,
                'x_first_name': credit_card.first_name,
                'x_last_name': credit_card.last_name,
            })

        if email:
            params['x_email'] = email

        if address:
            params.update({
                'x_address': address.street,
                'x_city': address.city,
                'x_state': address.state,
                'x_zip': address.zip_code,
                'x_country': address.country,
            })
        for key, value in list(params.items()):
            if value is None:
                del params[key]
        return params

    def auth(self, amount, credit_card, address=None, email=None):
        amount = Decimal(str(amount)).quantize(Decimal('0.01'))
        params = self.base_params.copy()
        params = self._add_params(params, credit_card, address, email)
        params['x_type'] = 'AUTH_ONLY'
        params['x_amount'] = str(amount)
        return self._make_call(params)

    def capture(self, amount, credit_card, address=None, email=None):
        amount = Decimal(str(amount)).quantize(Decimal('0.01'))
        params = self.base_params.copy()
        params = self._add_params(params, credit_card, address, email)
        params['x_type'] = 'AUTH_CAPTURE'
        params['x_amount'] = str(amount)
        return self._make_call(params)

    def settle(self, transaction_id, amount=None):
        # Amount is not required -- if provided, settles for a lower amount
        # than the original auth; if not, settles the full amount authed.
        params = self.base_params.copy()
        params['x_type'] = 'PRIOR_AUTH_CAPTURE'
        params['x_trans_id'] = transaction_id
        if amount:
            amount = Decimal(str(amount)).quantize(Decimal('0.01'))
            params['x_amount'] = str(amount)
        return self._make_call(params)

    def credit(self, card_num, transaction_id, amount):
        # Authorize.net can do unlinked credits (not tied to a previous
        # transaction) but we do not (at least for now).
        # Provide the last four digits for the card number, as well as the
        # transaction id and the amount to credit back.
        # The following restrictions apply:
        # - The transaction id must reference an existing, settled charge.
        #   (Note that in production, settlement happens once daily.)
        # - The amount of the credit (and the sum of all credits against this
        #   original transaction) must be less than or equal to the original
        #   charge amount.
        # - The credit must be submitted within 120 days of the original
        #   transaction being settled.
        params = self.base_params.copy()
        params['x_type'] = 'CREDIT'
        params['x_trans_id'] = transaction_id
        params['x_card_num'] = str(card_num)
        amount = Decimal(str(amount)).quantize(Decimal('0.01'))
        params['x_amount'] = str(amount)
        return self._make_call(params)

    def void(self, transaction_id):
        params = self.base_params.copy()
        params['x_type'] = 'VOID'
        params['x_trans_id'] = transaction_id
        return self._make_call(params)
