import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        # Try to import database module
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -------------- Stripe Checkout -----------------
class CheckoutRequest(BaseModel):
    plan: str  # 'monthly' | 'six_month' | 'lifetime'
    success_url: HttpUrl
    cancel_url: HttpUrl


@app.post("/api/stripe/checkout")
def create_checkout_session(payload: CheckoutRequest):
    """Create a Stripe Checkout Session for the selected plan.
    Requires STRIPE_SECRET_KEY in environment (use Stripe test key starting with sk_test_...).
    """
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(status_code=500, detail="Stripe Secret Key not configured on server.")

    try:
        import stripe
        stripe.api_key = stripe_secret

        # Map plans to pricing details
        if payload.plan == "monthly":
            # $1/month subscription
            price_data = {
                "currency": "usd",
                "unit_amount": 100,  # cents
                "product_data": {"name": "Monthly Plan", "description": "$1 / month"},
                "recurring": {"interval": "month", "interval_count": 1},
            }
            mode = "subscription"
        elif payload.plan == "six_month":
            # $6 per 6 months subscription
            price_data = {
                "currency": "usd",
                "unit_amount": 600,  # cents
                "product_data": {"name": "6-Month Plan", "description": "$6 / 6 months"},
                "recurring": {"interval": "month", "interval_count": 6},
            }
            mode = "subscription"
        elif payload.plan == "lifetime":
            # $39.99 one-time payment
            price_data = {
                "currency": "usd",
                "unit_amount": 3999,  # cents
                "product_data": {"name": "Lifetime Access", "description": "One-time payment"},
            }
            mode = "payment"
        else:
            raise HTTPException(status_code=400, detail="Invalid plan selected.")

        session = stripe.checkout.Session.create(
            mode=mode,
            line_items=[{"price_data": price_data, "quantity": 1}],
            success_url=str(payload.success_url),
            cancel_url=str(payload.cancel_url),
            allow_promotion_codes=True,
            billing_address_collection="auto",
            payment_method_types=["card"],
        )
        return {"id": session.id, "url": session.url}

    except stripe.error.StripeError as e:  # type: ignore
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
