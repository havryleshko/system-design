"use client";

import { useState, useTransition } from "react";
import { updateProfile, type ProfileData } from "./actions";

type ProfileFormProps = {
  initialData: ProfileData;
};

export default function ProfileForm({ initialData }: ProfileFormProps) {
  const [fullName, setFullName] = useState(initialData.full_name ?? "");
  const [phoneNumber, setPhoneNumber] = useState(initialData.phone_number ?? "");
  const [countryCode, setCountryCode] = useState(initialData.phone_country_code ?? "+1");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();

  // Format phone number as user types (XXX) XXX-XXXX
  const formatPhoneDisplay = (value: string) => {
    const digits = value.replace(/\D/g, "").slice(0, 10);
    if (digits.length === 0) return "";
    if (digits.length <= 3) return `(${digits}`;
    if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  };

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatPhoneDisplay(e.target.value);
    setPhoneNumber(formatted);
    setError(null);
    setSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    startTransition(async () => {
      const result = await updateProfile({
        full_name: fullName,
        phone_number: phoneNumber,
        phone_country_code: countryCode,
      });

      if (result.success) {
        setSuccess(true);
      } else {
        setError(result.error ?? "Failed to save changes");
      }
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Full Name */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <label
          htmlFor="fullName"
          className="w-full text-sm font-medium text-[var(--foreground-muted)] sm:w-40"
        >
          Full Name
        </label>
        <input
          id="fullName"
          type="text"
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            setError(null);
            setSuccess(false);
          }}
          placeholder="Enter your full name"
          className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--foreground)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_35%,transparent)]"
        />
      </div>

      {/* Phone Number */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
        <label
          htmlFor="phoneNumber"
          className="w-full text-sm font-medium text-[var(--foreground-muted)] sm:w-40 sm:pt-2.5"
        >
          Phone Number
        </label>
        <div className="flex-1 space-y-2">
          <p className="text-xs text-[var(--foreground-muted)]">
            At this time, we only accept US and Canadian phone numbers, we apologize for any
            inconvenience.
          </p>
          <div className="flex gap-2">
            <select
              value={countryCode}
              onChange={(e) => {
                setCountryCode(e.target.value);
                setError(null);
                setSuccess(false);
              }}
              className="w-36 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-sm text-[var(--foreground)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_35%,transparent)]"
            >
              <option value="+1">+1 (US/Canada)</option>
            </select>
            <input
              id="phoneNumber"
              type="tel"
              value={phoneNumber}
              onChange={handlePhoneChange}
              placeholder="(123) 456-7890"
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--foreground)] outline-none transition-colors focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_35%,transparent)]"
            />
          </div>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-400">
          Profile updated successfully!
        </div>
      )}

      {/* Submit Button */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isPending}
          className="rounded-lg border border-[var(--accent)] bg-[var(--accent)] px-6 py-2.5 text-sm font-semibold text-[var(--background)] transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[0_0_16px_rgba(154,182,194,0.3)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPending ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </form>
  );
}

