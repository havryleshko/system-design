import { NextResponse } from "next/server";
import Stripe from "stripe";

import { createServerSupabase } from "@/utils/supabase/server";
import { createAdminSupabase } from "@/utils/supabase/admin";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

const PRICE_ID = process.env.STRIPE_PRICE_ID_PRO;
const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://app.systesign.com";

export async function POST() {
  if (!PRICE_ID) {
    return NextResponse.json({ error: "Pricing not configured" }, { status: 500 });
  }

  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const user = session?.user;

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const admin = createAdminSupabase();
  const { data: existing, error } = await admin
    .from("stripe_customers")
    .select("customer_id")
    .eq("user_id", user.id)
    .maybeSingle();

  if (error) {
    console.error("Failed to lookup stripe customer", error);
    return NextResponse.json({ error: "Billing lookup failed" }, { status: 500 });
  }

  let customerId = existing?.customer_id ?? null;

  if (!customerId) {
    const customer = await stripe.customers.create({
      email: user.email ?? undefined,
      metadata: { supabase_user_id: user.id },
    });
    customerId = customer.id;
    await admin
      .from("stripe_customers")
      .upsert({
        user_id: user.id,
        customer_id: customer.id,
        status: "active",
      });
  }

  const checkoutSession = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: "subscription",
    line_items: [{ price: PRICE_ID, quantity: 1 }],
    success_url: `${APP_URL}/billing?success=true`,
    cancel_url: `${APP_URL}/billing?cancel=true`,
    subscription_data: {
      metadata: { supabase_user_id: user.id },
    },
    metadata: { supabase_user_id: user.id },
  });

  return NextResponse.json({ url: checkoutSession.url }, { status: 200 });
}

