"""
Authorize.net payment gateway interface.

For original Authorize.net API docs:

AIM (basic transactions)
    http://www.authorize.net/support/AIM_guide.pdf

CIM (saved payment)
    http://www.authorize.net/support/CIM_SOAP_guide.pdf

ARB (recurring payments)
    http://www.authorize.net/support/ARB_SOAP_guide.pdf

The client init arguments are as follows:

login_id
    The login ID provided by Authorize.net for your account.

transaction_key
    The transaction key provided by Authorize.net for your account.

debug
    Set to True to run all API calls against the Authorize.net staging
    environment. You will receive normal responses but none of your
    transactions will actually be processed. Your login_id and transaction_key
    must belong to a developer account. Use this in development.

test
    Set to True to run all API calls in test mode against the Authorize.net
    production environment. This will use your real production login_id and
    transaction_key credentials and the real production API, but it will not
    actually send transactions for processing. Use this just before deploying
    to ensure your connection and credentials are valid. (Only affects the
    basic transactions API, not saved payments or subscriptions.)

"""

from authorize.client import AuthorizeClient
from authorize.data import Address, CreditCard, ECheckAccount
from authorize.exceptions import AuthorizeConnectionError, AuthorizeError, \
    AuthorizeInvalidError, AuthorizeResponseError
