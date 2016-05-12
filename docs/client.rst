Authorize interface
===================

.. automodule:: authorize.client

Authorize client
----------------

.. autoclass:: authorize.client.AuthorizeClient
    :members: card, transaction, saved_card, recurring, echeck

Credit card
-----------

.. autoclass:: authorize.client.AuthorizeCreditCard
    :members: auth, capture, save, recurring

Transaction
-----------

.. autoclass:: authorize.client.AuthorizeTransaction
    :members: settle, credit, void

Saved card
----------

.. autoclass:: authorize.client.AuthorizeSavedCard
    :members: auth, capture, delete

Recurring charge
----------------

.. autoclass:: authorize.client.AuthorizeRecurring
    :members: update, delete

eCheck
------

.. autoclass:: authorize.client.AuthorizeECheck
    :members: web
