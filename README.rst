Authorize Sauce
===============

.. image:: https://img.shields.io/travis/jeffschenck/authorizesauce.svg
   :target: https://travis-ci.org/jeffschenck/authorizesauce
.. image:: https://img.shields.io/codecov/c/github/jeffschenck/authorizesauce.svg
   :target: https://codecov.io/github/jeffschenck/authorizesauce
.. image:: https://img.shields.io/pypi/pyversions/AuthorizeSauce.svg
   :target: https://pypi.python.org/pypi/AuthorizeSauce
.. image:: https://img.shields.io/pypi/l/AuthorizeSauce.svg
   :target: https://pypi.python.org/pypi/AuthorizeSauce

The secret sauce for accessing the Authorize.net API. The Authorize APIs for
transactions, recurring payments, and saved payments are all different and
awkward to use directly. Instead, you can use Authorize Sauce, which unifies
all three Authorize.net APIs into one coherent Pythonic interface. Charge
credit cards, easily!

::

  >>> # Init the authorize client and a credit card
  >>> from authorize import AuthorizeClient, CreditCard
  >>> client = AuthorizeClient('285tUPuS', '58JKJ4T95uee75wd')
  >>> cc = CreditCard('4111111111111111', '2018', '01', '911', 'Joe', 'Blow')
  >>> card = client.card(cc)

  >>> # Charge a card
  >>> card.capture(100)
  <AuthorizeTransaction 2171829470>

  >>> # Save the card on Authorize servers for later
  >>> saved_card = card.save()
  >>> saved_card.uid
  '7713982|6743206'

  >>> # Use a saved card to auth a transaction, and settle later
  >>> saved_card = client.saved_card('7713982|6743206')
  >>> transaction = saved_card.auth(200)
  >>> transaction.settle()

Saucy Features
--------------

* Charge a credit card
* Authorize a credit card charge, and settle it or release it later
* Credit or refund to a card
* Save a credit card securely on Authorize.net's servers
* Use saved cards to charge, auth and credit
* Create recurring charges, with billing cycles, trial periods, etc.
* Process an eCheck

For the full documentation, please visit us at `Read the Docs`_. Thanks to
Chewse_ for supporting the development and open-sourcing of this library.
Authorize Sauce is released under the `MIT License`_.

.. _Read the Docs: http://authorize-sauce.readthedocs.org/
.. _Chewse: https://www.chewse.com/
.. _MIT License: http://www.opensource.org/licenses/mit-license
