-- Add profile fields for user settings
ALTER TABLE public.users_profile
  ADD COLUMN IF NOT EXISTS full_name text,
  ADD COLUMN IF NOT EXISTS phone_number text,
  ADD COLUMN IF NOT EXISTS phone_country_code text DEFAULT '+1';

