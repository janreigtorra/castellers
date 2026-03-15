# Stripe Subscription Setup Guide

This guide explains how to set up the Stripe subscription system for Xiquet.cat.

## Overview

The subscription system has been implemented with the following features:
- **Basic Plan**: Free, limited to 7 questions per hour
- **Premium Plan**: €1.99/month, unlimited questions
- Rate limiting for basic users
- Stripe checkout integration
- Webhook handling for subscription events

## Step-by-Step Setup

### 1. Install Dependencies

Install the Stripe Python SDK:
```bash
cd backend
pip install -r requirements.txt
```

This will install `stripe>=7.0.0` along with other dependencies.

### 2. Stripe Dashboard Setup

#### A. Create a Stripe Account
1. Go to https://stripe.com and create an account (or log in)
2. Complete the account setup process

#### B. Create a Product and Price
1. In Stripe Dashboard, go to **Products** → **Add Product**
2. Product name: "Xiquet Premium"
3. Description: "Premium subscription for unlimited questions"
4. Pricing:
   - **Price**: €1.99
   - **Billing period**: Monthly (recurring)
   - **Currency**: EUR
5. Click **Save product**
6. **IMPORTANT**: Copy the **Price ID** (starts with `price_...`) - you'll need this for the environment variable

#### C. Get API Keys
1. Go to **Developers** → **API keys**
2. Copy your **Publishable key** (starts with `pk_...`)
3. Copy your **Secret key** (starts with `sk_...`) - click "Reveal test key" if needed

#### D. Set Up Webhook Endpoint
1. Go to **Developers** → **Webhooks**
2. Click **Add endpoint**
3. Endpoint URL: `https://your-backend-url.com/api/subscription/webhook`
   - Replace `your-backend-url.com` with your actual backend URL
   - Example: `https://xiquet-backend.fly.dev/api/subscription/webhook`
4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Click **Add endpoint**
6. **IMPORTANT**: Copy the **Signing secret** (starts with `whsec_...`) - you'll need this for the environment variable

### 3. Database Migration

Run the migration to add the `stripe_customer_id` column to the profiles table:

```sql
-- Run this in your Supabase SQL Editor
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_profiles_stripe_customer_id 
ON public.profiles(stripe_customer_id) 
WHERE stripe_customer_id IS NOT NULL;
```

Or use the migration file:
```bash
# The migration file is at:
backend/migrations/add_stripe_customer_id.sql
```

### 4. Environment Variables

Add the following environment variables to your backend `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key
STRIPE_PUBLISHABLE_KEY=pk_test_...  # Your Stripe publishable key (optional, for frontend if needed)
STRIPE_WEBHOOK_SECRET=whsec_...  # Your webhook signing secret
STRIPE_PREMIUM_PRICE_ID=price_...  # The Price ID from step 2.B
FRONTEND_URL=https://xiquet.vercel.app  # Your frontend URL for redirects
```

**Important Notes:**
- Use `sk_test_...` and `pk_test_...` for development/testing
- Use `sk_live_...` and `pk_live_...` for production
- The webhook secret is different for test and live modes
- Make sure to set the correct `FRONTEND_URL` for your environment

### 5. Deploy and Test

1. **Deploy your backend** with the new environment variables
2. **Test the checkout flow**:
   - Log in to your app
   - Go to Profile
   - Click "Actualitzar a Premium"
   - Complete the Stripe checkout (use test card: `4242 4242 4242 4242`)
   - Verify the webhook updates the subscription in your database

3. **Test rate limiting**:
   - Create a basic user account
   - Send 7 questions within 1 hour
   - The 8th question should show the rate limit message with upgrade link

### 6. Rate Limiting Configuration

The rate limiting is configured in `backend/xiquet/agent.py`:

```python
MAX_QUESTIONS_BASIC = 7  # Maximum questions per time window
TIME_BASIC = 3600  # Time window in seconds (1 hour = 3600 seconds)
```

You can adjust these values as needed.

## How It Works

### User Flow

1. **New User Registration**:
   - User creates account → automatically set to `basic` subscription
   - Can ask up to 7 questions per hour

2. **Upgrade to Premium**:
   - User clicks "Actualitzar a Premium" in Profile
   - Backend creates Stripe checkout session
   - User redirected to Stripe checkout page
   - After payment, Stripe sends webhook to backend
   - Backend updates user subscription to `premium`
   - User redirected back to profile with success message

3. **Rate Limiting**:
   - Before processing each chat message, backend checks:
     - User's subscription status
     - If `basic`: Counts messages in last hour
     - If count >= 7: Returns rate limit message with upgrade link
     - If `premium`: No rate limiting

### Webhook Events Handled

- `checkout.session.completed`: When user completes payment, upgrade to premium
- `customer.subscription.updated`: When subscription status changes (active/canceled)
- `customer.subscription.deleted`: When subscription is canceled, downgrade to basic

## API Endpoints

### Backend Endpoints

- `POST /api/subscription/create-checkout`: Create Stripe checkout session
- `POST /api/subscription/webhook`: Handle Stripe webhook events
- `GET /api/subscription/status`: Get current subscription status

### Frontend Integration

The frontend uses:
- `apiService.getSubscriptionStatus()`: Get subscription info
- `apiService.createCheckoutSession()`: Start checkout process

## Troubleshooting

### Webhook Not Working

1. Check webhook URL is correct in Stripe Dashboard
2. Verify `STRIPE_WEBHOOK_SECRET` matches the signing secret
3. Check backend logs for webhook errors
4. Use Stripe CLI for local testing: `stripe listen --forward-to localhost:8000/api/subscription/webhook`

### Subscription Not Updating

1. Check database migration was run
2. Verify webhook events are being received (check Stripe Dashboard → Webhooks → Events)
3. Check backend logs for webhook processing errors
4. Verify `STRIPE_SECRET_KEY` is correct

### Rate Limiting Not Working

1. Check `MAX_QUESTIONS_BASIC` and `TIME_BASIC` values in `agent.py`
2. Verify user subscription is being checked correctly
3. Check database query in `check_rate_limit()` function

## Production Checklist

- [ ] Switch to live Stripe keys (`sk_live_...`, `pk_live_...`)
- [ ] Update webhook endpoint to production URL
- [ ] Get new webhook signing secret for live mode
- [ ] Test complete checkout flow with real payment
- [ ] Verify webhook events are being received
- [ ] Monitor subscription status updates
- [ ] Set up error alerts for webhook failures

## Support

If you encounter issues:
1. Check Stripe Dashboard → Logs for API errors
2. Check backend logs for webhook processing
3. Verify all environment variables are set correctly
4. Test with Stripe test mode first before going live

