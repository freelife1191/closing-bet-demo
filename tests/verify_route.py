
import sys
import os
from flask import Flask

# Add project root to path
sys.path.append(os.getcwd())

from app.routes import kr_bp

def verify_route():
    app = Flask(__name__)
    app.register_blueprint(kr_bp, url_prefix='/api/kr')
    
    found = False
    for rule in app.url_map.iter_rules():
        if rule.rule == '/api/kr/market-gate/update' and 'POST' in rule.methods:
            print(f"✅ Route Found: {rule}")
            found = True
            break
            
    if not found:
        print("❌ Route /api/kr/market-gate/update [POST] NOT FOUND")
        sys.exit(1)
    else:
        print("Verification Successful")

if __name__ == "__main__":
    verify_route()
