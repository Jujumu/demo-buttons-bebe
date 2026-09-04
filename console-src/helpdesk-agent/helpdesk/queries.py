"""Read-only Admin GraphQL 2026-07 documents. Query only — no mutations."""

from __future__ import annotations

CUSTOMER_QUERY = """
query HelpdeskCustomer($id: ID!) {
  customer(id: $id) {
    id
    displayName
    defaultEmailAddress { emailAddress }
    createdAt
    numberOfOrders
    amountSpent { amount currencyCode }
    tags
  }
}
"""

ORDER_QUERY = """
query HelpdeskOrder($id: ID!) {
  order(id: $id) {
    id
    name
    createdAt
    displayFinancialStatus
    displayFulfillmentStatus
    returnStatus
    discountCodes
    currentTotalPriceSet {
      shopMoney { amount currencyCode }
      presentmentMoney { amount currencyCode }
    }
    billingAddress { name address1 address2 city province zip country }
    shippingAddress { name address1 address2 city province zip country }
    lineItems(first: 50) {
      nodes {
        title
        sku
        quantity
        unfulfilledQuantity
        originalUnitPriceSet { shopMoney { amount currencyCode } }
        image { url altText }
      }
    }
    fulfillments {
      displayStatus
      trackingInfo { number url company }
      fulfillmentLineItems(first: 50) {
        nodes { quantity lineItem { title } }
      }
    }
    returns(first: 20) { nodes { id name status totalQuantity } }
  }
}
"""

ORDER_BY_NAME_QUERY = """
query HelpdeskOrderByName($query: String!) {
  orders(first: 1, query: $query) {
    nodes {
      id
      name
      customer { id }
    }
  }
}
"""

CUSTOMER_BY_EMAIL_QUERY = """
query HelpdeskCustomerByEmail($query: String!) {
  customers(first: 1, query: $query) {
    nodes {
      id
      defaultEmailAddress { emailAddress }
    }
  }
}
"""

PAST_ORDERS_QUERY = """
query HelpdeskPastOrders($id: ID!) {
  customer(id: $id) {
    orders(first: 50, sortKey: CREATED_AT, reverse: true) {
      nodes {
        id
        name
        createdAt
        displayFulfillmentStatus
        currentTotalPriceSet { shopMoney { amount currencyCode } }
      }
    }
  }
}
"""
