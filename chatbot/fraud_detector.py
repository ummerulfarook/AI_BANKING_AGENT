import re

def detect_fraud(query):
    query = query.lower()

    # OTP / PIN Scam Rules
    otp_patterns = [r"\botp\b", r"one-time password", r"verification code", r"passcode", r"security code", r"\bpin\b", r"\bcvv\b"]
    for pattern in otp_patterns:
        if re.search(pattern, query):
            return {
                "is_fraud": True,
                "warning": "⚠️ SECURITY WARNING: Never share your OTP, PIN, CVV, or passwords with anyone. Our bank representatives will NEVER ask you for these sensitive details. If someone asks for them, it is a scam."
            }

    # Fake KYC Scam Rules
    kyc_patterns = [r"kyc update", r"verify kyc", r"kyc link", r"kyc verification", r"kyc pending", r"kyc blocked", r"update kyc"]
    for pattern in kyc_patterns:
        if re.search(pattern, query):
            return {
                "is_fraud": True,
                "warning": "⚠️ SECURITY WARNING: Scammers often send fake KYC update requests to suspend your account. Always perform KYC updates through our official secure portal or by visiting a bank branch. Never click untrusted links."
            }

    # Phishing / Fake Links Rules
    phishing_patterns = [r"\blink\b", r"\burl\b", r"sms message", r"whatsapp message", r"website to login", r"unusual link", r"verify link", r"click here to login", r"login page"]
    for pattern in phishing_patterns:
        if re.search(pattern, query):
            return {
                "is_fraud": True,
                "warning": "⚠️ SECURITY WARNING: The bank will never send SMS or messages containing direct login links. Always verify the domain name (make sure it ends with bank's official domain) before entering your login credentials."
            }

    # UPI Scam Rules
    upi_patterns = [r"upi scam", r"receive money pin", r"gpay cashback", r"phonepe request", r"collect request", r"scan qr to receive", r"receive payment pin"]
    for pattern in upi_patterns:
        if re.search(pattern, query):
            return {
                "is_fraud": True,
                "warning": "⚠️ SECURITY WARNING: You NEVER need to enter your UPI PIN or scan a QR code to receive money. PINs are only used to send money or check balance. Scanning a QR code or entering a PIN to receive a refund is a fraud attempt."
            }

    # Card Skimming / Security Rules
    skimming_patterns = [r"card blocked", r"skimming", r"lost card", r"stolen card", r"card lost", r"lost credit card", r"lost debit card"]
    for pattern in skimming_patterns:
        if re.search(pattern, query):
            return {
                "is_fraud": True,
                "warning": "⚠️ SECURITY WARNING: If your card is lost, stolen, or compromised, block it immediately in the app, netbanking, or by calling our official support line. Never write your PIN on your card."
            }

    return {
        "is_fraud": False,
        "warning": None
    }
