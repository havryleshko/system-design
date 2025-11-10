import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

import { createAdminSupabase } from "@/utils/supabase/admin";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

export async function POST(req: NextRequest) {
  if (!webhookSecret) {
    return NextResponse.json({ error: "Webhook secret not configured" }, { status: 500 });
  }

  const rawBody = await req.text();
  const signature = req.headers.get("stripe-signature");

  if (!signature) {
    return NextResponse.json({ error: "Missing stripe-signature header" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  } catch (error) {
    console.error("Stripe webhook signature verification failed", error);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const supabase = createAdminSupabase();

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        const customerId = session.customer as string | null;
        const subscriptionId = session.subscription as string | null;
        const userId = session.metadata?.supabase_user_id ?? null;
        if (customerId && userId) {
          await supabase
            .from("stripe_customers")
            .upsert({
              user_id: userId,
              customer_id: customerId,
              subscription_id: subscriptionId,
              status: "active",
            });
          await supabase
            .from("users_profile")
            .upsert({
              user_id: userId,
              plan: "pro",
              plan_since: new Date().toISOString(),
            });
        }
        break;
      }

      case "customer.subscription.created":
      case "customer.subscription.updated": {
        const subscription = event.data.object as Stripe.Subscription;
        const customerId = subscription.customer as string | null;
        const userId = subscription.metadata?.supabase_user_id ?? null;
        await supabase
          .from("stripe_customers")
          .update({
            subscription_id: subscription.id,
            status: subscription.status,
          })
          .eq("customer_id", customerId);
        if (userId && subscription.status === "active") {
          // Stripe types may not expose current_period_start depending on version; read safely
          const s = subscription as unknown as Record<string, unknown>;
          const start = typeof s["current_period_start"] === "number" ? (s["current_period_start"] as number) : undefined;
          const planSinceIso = start ? new Date(start * 1000).toISOString() : new Date().toISOString();
          await supabase
            .from("users_profile")
            .update({
              plan: "pro",
              plan_since: planSinceIso,
            })
            .eq("user_id", userId);
        }
        break;
      }

      case "customer.subscription.deleted":
      case "invoice.payment_failed": {
        const subscription = event.data.object as Stripe.Subscription | Stripe.Invoice;
        const customerId = subscription.customer as string | null;
        const userId = "metadata" in subscription ? subscription.metadata?.supabase_user_id ?? null : null;
        if (customerId) {
          await supabase
            .from("stripe_customers")
            .update({ status: "canceled" })
            .eq("customer_id", customerId);
        }
        if (userId) {
          await supabase
            .from("users_profile")
            .update({ plan: "free" })
            .eq("user_id", userId);
        }
        break;
      }

      default:
        break;
    }
  } catch (error) {
    console.error("Stripe webhook processing error", error);
    return NextResponse.json({ error: "Webhook handling error" }, { status: 500 });
  }

  return NextResponse.json({ received: true }, { status: 200 });
}

export const config = {
  api: {
    bodyParser: false,
  },
};

