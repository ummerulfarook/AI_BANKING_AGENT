def detect_intent(query):

    query = query.lower()

    intents = {

        "Loan Inquiry": [
            "loan",
            "emi",
            "interest rate",
            "home loan",
            "personal loan"
        ],

        "ATM Card Issue": [
            "atm",
            "debit card",
            "blocked card",
            "card not working",
            "pin"
        ],

        "Credit Card Issue": [
            "credit card",
            "credit limit",
            "billing",
            "statement"
        ],

        "UPI Issue": [
            "upi",
            "gpay",
            "phonepe",
            "paytm",
            "transaction failed"
        ],

        "Account Opening": [
            "open account",
            "savings account",
            "current account",
            "new account"
        ],

        "Balance Inquiry": [
            "balance",
            "account balance",
            "check balance"
        ]

    }

    for intent, keywords in intents.items():

        for keyword in keywords:

            if keyword in query:
                return intent

    return "General Banking Query"