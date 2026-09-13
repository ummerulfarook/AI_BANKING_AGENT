def get_recommendation(intent, query):
    query = query.lower()
    intent = intent.lower() if intent else ""

    # Credit Card recommendations
    if "credit card" in intent or "credit card" in query or "card" in query and "limit" in query:
        return {
            "title": "💳 Recommended: Elite Cashback Credit Card",
            "details": "Enjoy 5% unlimited cashback on online shopping, 4 complimentary airport lounge visits per year, and fuel surcharge waivers. Annual Fee: Rs. 499.",
            "link": "/apply/credit-card"
        }

    # Home Loan / Loan recommendations
    if "loan" in intent or "loan" in query or "emi" in query or "interest rate" in query and "home" in query:
        return {
            "title": "🏠 Recommended: Dream Home Loan",
            "details": "Get home loan financing starting from 8.5% per annum, flexible repayment tenures up to 30 years, and instant digital approval with minimal documentation.",
            "link": "/apply/home-loan"
        }

    # Savings Account recommendations
    if "account opening" in intent or "savings account" in query or "open account" in query or "current account" in query:
        return {
            "title": "📈 Recommended: High-Yield Savings Account",
            "details": "Earn up to 4.5% p.a. interest, get a complimentary Platinum Debit Card, and enjoy unlimited free withdrawals at any domestic ATM.",
            "link": "/apply/savings-account"
        }

    # Fixed Deposit recommendations
    if "deposit" in query or "fixed deposit" in query or "invest" in query or "fd" in query:
        return {
            "title": "💰 Recommended: Golden Fixed Deposit Scheme",
            "details": "Secure your savings with guaranteed returns up to 7.5% per annum (8.0% for Senior Citizens) for a 1-year tenure. Easy online liquidation.",
            "link": "/apply/fixed-deposit"
        }

    return None
