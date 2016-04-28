from six import BytesIO, u
from datetime import date

import mock
from unittest2 import TestCase
from six.moves.urllib.parse import urlparse, parse_qsl, unquote_plus

from authorize.apis.transaction import PROD_URL, TEST_URL, TransactionAPI
from authorize.data import Address, CreditCard
from authorize.exceptions import AuthorizeConnectionError, \
    AuthorizeResponseError


class MockResponse(BytesIO):
    class Headers(dict):
        def getparam(self, *args, **kwargs):
            """Python 2 version"""
            return None

        def get_content_charset(self, failobj=None, *args, **kwargs):
            """Python 3 version"""
            return failobj

    def __init__(self, *args, **kwargs):
        BytesIO.__init__(self, *args, **kwargs)
        self.headers = self.Headers()

SUCCESS = MockResponse(
    b'1;1;1;This transaction has been approved.;IKRAGJ;Y;2171062816;;;20.00;CC'
    b';auth_only;;Jeffrey;Schenck;;45 Rose Ave;Venice;CA;90291;USA;;;;;;;;;;;;'
    b';;;;;375DD9293D7605E20DF0B437EE2A7B92;P;2;;;;;;;;;;;XXXX1111;Visa;;;;;;;'
    b';;;;;;;;;;Y')
PARSED_SUCCESS = {
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
ERROR = MockResponse(
    b'2;1;2;This transaction has been declined.;000000;N;2171062816;;;20.00;CC'
    b';auth_only;;Jeffrey;Schenck;;45 Rose Ave;Venice;CA;90291;USA;;;;;;;;;;;;'
    b';;;;;375DD9293D7605E20DF0B437EE2A7B92;N;1;;;;;;;;;;;XXXX1111;Visa;;;;;;;'
    b';;;;;;;;;;Y')
PARSED_ERROR = {
    'cvv_response': 'N',
    'authorization_code': '000000',
    'response_code': '2',
    'amount': '20.00',
    'transaction_type': 'auth_only',
    'avs_response': 'N',
    'response_reason_code': '2',
    'response_reason_text': 'This transaction has been declined.',
    'transaction_id': '2171062816',
}


class URL(object):
    """
    a class to enable comparing of two urls regardless of order of parameters
    see http://stackoverflow.com/questions/5371992/comparing-two-urls-in-python
    """
    def __init__(self, url):
        parts = urlparse(url)
        _query = frozenset(parse_qsl(parts.query))
        _path = unquote_plus(parts.path)
        parts = parts._replace(query=_query, path=_path)
        self.parts = parts

    def __eq__(self, other):
        return self.parts == other.parts

    def __hash__(self, other):
        return hash(self.parts)


class TransactionAPITests(TestCase):
    def setUp(self):
        self.api = TransactionAPI('123', '456')
        self.success = lambda *args, **kwargs: SUCCESS.seek(0) or SUCCESS
        self.error = lambda *args, **kwargs: ERROR.seek(0) or ERROR
        self.year = date.today().year + 10
        self.credit_card = CreditCard('4111111111111111', self.year, 1, '911')
        self.address = Address('45 Rose Ave', 'Venice', 'CA', '90291')

    def test_basic_api(self):
        api = TransactionAPI('123', '456')
        self.assertEqual(api.url, TEST_URL)
        api = TransactionAPI('123', '456', debug=False)
        self.assertEqual(api.url, PROD_URL)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_make_call(self, urlopen):
        urlopen.side_effect = self.success
        result = self.api._make_call({'a': '1', 'b': '2'})
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data']
            )),
            URL('{0}?a=1&b=2'.format(TEST_URL))
        )
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_make_call_with_unicode(self, urlopen):
        urlopen.side_effect = self.success
        result = self.api._make_call({u('\xe3'): '1', 'b': u('\xe3')})
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('{0}?%C3%A3=1&b=%C3%A3'.format(TEST_URL))
        )
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_make_call_connection_error(self, urlopen):
        urlopen.side_effect = IOError('Borked')
        self.assertRaises(AuthorizeConnectionError, self.api._make_call,
                          {'a': '1', 'b': '2'})

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_make_call_response_error(self, urlopen):
        urlopen.side_effect = self.error
        try:
            self.api._make_call({'a': '1', 'b': '2'})
        except AuthorizeResponseError as e:
            self.assertTrue(str(e).startswith(
                'This transaction has been declined.'
            ))
            self.assertEqual(e.full_response, PARSED_ERROR)

    def test_add_params(self):
        self.assertEqual(self.api._add_params({}), {})
        params = self.api._add_params({}, credit_card=self.credit_card)
        self.assertEqual(params, {
            'x_card_num': '4111111111111111',
            'x_exp_date': '01-{0}'.format(self.year),
            'x_card_code': '911',
        })
        params = self.api._add_params({}, address=self.address)
        self.assertEqual(params, {
            'x_address': '45 Rose Ave',
            'x_city': 'Venice',
            'x_state': 'CA',
            'x_zip': '90291',
            'x_country': 'US',
        })
        params = self.api._add_params(
            {}, credit_card=self.credit_card, address=self.address
        )
        self.assertEqual(params, {
            'x_card_num': '4111111111111111',
            'x_exp_date': '01-{0}'.format(self.year),
            'x_card_code': '911',
            'x_address': '45 Rose Ave',
            'x_city': 'Venice',
            'x_state': 'CA',
            'x_zip': '90291',
            'x_country': 'US',
        })

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_auth(self, urlopen):
        urlopen.side_effect = self.success
        result = self.api.auth(20, self.credit_card, self.address)
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_zip=90291&x_card_num=4111111111111111&x_amount=20.00'
                '&x_tran_key=456&x_city=Venice&x_country=US&x_version=3.1'
                '&x_state=CA&x_delim_char=%3B&x_address=45+Rose+Ave'
                '&x_exp_date=01-{0}&x_test_request=FALSE&x_card_code=911'
                '&x_type=AUTH_ONLY&x_delim_data=TRUE'.format(str(self.year)))
        )
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_capture(self, urlopen):
        urlopen.side_effect = self.success
        result = self.api.capture(20, self.credit_card, self.address)
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_zip=90291&x_card_num=4111111111111111&x_amount=20.00'
                '&x_tran_key=456&x_city=Venice&x_country=US&x_version=3.1'
                '&x_state=CA&x_delim_char=%3B&x_address=45+Rose+Ave'
                '&x_exp_date=01-{0}&x_test_request=FALSE&x_card_code=911'
                '&x_type=AUTH_CAPTURE&x_delim_data=TRUE'.format(
                    str(self.year))
                )
        )
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_settle(self, urlopen):
        urlopen.side_effect = self.success

        # Test without specified amount
        result = self.api.settle('123456')
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_trans_id=123456&x_version=3.1&x_delim_char=%3B'
                '&x_type=PRIOR_AUTH_CAPTURE&x_delim_data=TRUE&x_tran_key=456'
                '&x_test_request=FALSE')
        )
        self.assertEqual(result, PARSED_SUCCESS)

        # Test with specified amount
        result = self.api.settle('123456', amount=10)
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_trans_id=123456&x_version=3.1&x_delim_char=%3B'
                '&x_type=PRIOR_AUTH_CAPTURE&x_amount=10.00&x_delim_data=TRUE'
                '&x_tran_key=456&x_test_request=FALSE'))
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_credit(self, urlopen):
        urlopen.side_effect = self.success

        # Test with transaction_id, amount
        result = self.api.credit('1111', '123456', 10)
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_trans_id=123456&x_version=3.1&x_amount=10.00'
                '&x_delim_char=%3B&x_type=CREDIT&x_card_num=1111'
                '&x_delim_data=TRUE&x_tran_key=456&x_test_request=FALSE')
        )
        self.assertEqual(result, PARSED_SUCCESS)

    @mock.patch('authorize.apis.transaction.urlopen')
    def test_void(self, urlopen):
        urlopen.side_effect = self.success
        result = self.api.void('123456')
        self.assertEqual(
            URL("{0}?{1}".format(
                urlopen.call_args[0][0], urlopen.call_args[1]['data'])),
            URL('https://test.authorize.net/gateway/transact.dll?x_login=123'
                '&x_trans_id=123456&x_version=3.1&x_delim_char=%3B&x_type=VOID'
                '&x_delim_data=TRUE&x_tran_key=456&x_test_request=FALSE'))
        self.assertEqual(result, PARSED_SUCCESS)
