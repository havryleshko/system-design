"use server";

import { createServerSupabase } from "@/utils/supabase/server";
import { createAdminSupabase } from "@/utils/supabase/admin";
import { redirect } from "next/navigation";

export type ProfileData = {
  user_id: string;
  email: string | null;
  full_name: string | null;
  phone_number: string | null;
  phone_country_code: string | null;
  plan: string | null;
};

export type UpdateProfileInput = {
  full_name: string;
  phone_number: string;
  phone_country_code: string;
};

export type ProfileResult = {
  success: boolean;
  error?: string;
  data?: ProfileData;
};

// Validate US/Canadian phone number (10 digits)
function validatePhoneNumber(phone: string): { valid: boolean; error?: string } {
  if (!phone || phone.trim() === "") {
    return { valid: true }; // Phone is optional
  }

  // Remove all non-digit characters
  const digitsOnly = phone.replace(/\D/g, "");

  if (digitsOnly.length !== 10) {
    return {
      valid: false,
      error: "Phone number must be exactly 10 digits for US/Canada",
    };
  }

  // Basic validation: first digit shouldn't be 0 or 1 for US/Canada
  if (digitsOnly[0] === "0" || digitsOnly[0] === "1") {
    return {
      valid: false,
      error: "Invalid phone number format for US/Canada",
    };
  }

  return { valid: true };
}

export async function getProfile(): Promise<ProfileResult> {
  const supabase = await createServerSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    redirect("/login");
  }

  const userId = session.user.id;
  const userEmail = session.user.email ?? null;

  // Use admin client for database operations (RLS blocks writes on users_profile)
  const admin = createAdminSupabase();

  // Try to get existing profile - only select columns that definitely exist
  const { data: profile, error } = await admin
    .from("users_profile")
    .select("user_id, email, plan")
    .eq("user_id", userId)
    .maybeSingle();

  if (error) {
    console.error("Error fetching profile:", error);
    return { success: false, error: "Failed to fetch profile" };
  }

  // If no profile exists, create one
  if (!profile) {
    const { data: newProfile, error: insertError } = await admin
      .from("users_profile")
      .insert({
        user_id: userId,
        email: userEmail,
        plan: "free",
      })
      .select("user_id, email, plan")
      .single();

    if (insertError) {
      console.error("Error creating profile:", insertError);
      return { success: false, error: "Failed to create profile" };
    }

    // Return with nullable new columns (migration may not be applied yet)
    return {
      success: true,
      data: {
        ...newProfile,
        full_name: null,
        phone_number: null,
        phone_country_code: "+1",
      },
    };
  }

  // Update email if it changed (from auth)
  if (profile.email !== userEmail) {
    await admin
      .from("users_profile")
      .update({ email: userEmail })
      .eq("user_id", userId);
  }

  // Try to get the new columns if they exist
  const { data: fullProfile } = await admin
    .from("users_profile")
    .select("full_name, phone_number, phone_country_code")
    .eq("user_id", userId)
    .maybeSingle();

  return {
    success: true,
    data: {
      user_id: profile.user_id,
      email: userEmail,
      plan: profile.plan,
      full_name: fullProfile?.full_name ?? null,
      phone_number: fullProfile?.phone_number ?? null,
      phone_country_code: fullProfile?.phone_country_code ?? "+1",
    },
  };
}

export async function updateProfile(input: UpdateProfileInput): Promise<ProfileResult> {
  const supabase = await createServerSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return { success: false, error: "Not authenticated" };
  }

  const userId = session.user.id;

  // Validate phone number if provided
  const phoneValidation = validatePhoneNumber(input.phone_number);
  if (!phoneValidation.valid) {
    return { success: false, error: phoneValidation.error };
  }

  // Clean phone number (keep only digits)
  const cleanPhone = input.phone_number
    ? input.phone_number.replace(/\D/g, "")
    : null;

  // Use admin client for database operations (RLS blocks writes on users_profile)
  const admin = createAdminSupabase();

  // Update profile - only update fields that exist
  const updateData: Record<string, unknown> = {
    updated_at: new Date().toISOString(),
  };

  // Try to update new columns (they may not exist if migration not applied)
  try {
    const { error } = await admin
      .from("users_profile")
      .update({
        ...updateData,
        full_name: input.full_name.trim() || null,
        phone_number: cleanPhone,
        phone_country_code: input.phone_country_code || "+1",
      })
      .eq("user_id", userId);

    if (error) {
      console.error("Error updating profile:", error);
      return { success: false, error: "Failed to update profile. Please ensure the database migration has been applied." };
    }
  } catch (err) {
    console.error("Error updating profile:", err);
    return { success: false, error: "Failed to update profile" };
  }

  // Fetch the updated profile
  const { data: profile } = await admin
    .from("users_profile")
    .select("user_id, email, plan")
    .eq("user_id", userId)
    .single();

  const { data: extraFields } = await admin
    .from("users_profile")
    .select("full_name, phone_number, phone_country_code")
    .eq("user_id", userId)
    .maybeSingle();

  return {
    success: true,
    data: {
      user_id: profile?.user_id ?? userId,
      email: profile?.email ?? session.user.email ?? null,
      plan: profile?.plan ?? "free",
      full_name: extraFields?.full_name ?? (input.full_name.trim() || null),
      phone_number: extraFields?.phone_number ?? cleanPhone,
      phone_country_code: extraFields?.phone_country_code ?? (input.phone_country_code || "+1"),
    },
  };
}

