"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"

function BillingContent() {
    const searchParams = useSearchParams()
    const [status, setStatus] = useState<'success' | 'cancel' | null>(null)

    useEffect(() => {
        const success = searchParams.get('success')
        const cancel = searchParams.get('cancel')

        if (success === 'true') {
            setStatus('success')
        } else if (cancel === 'true') {
            setStatus('cancel')
        }
    }, [searchParams])

    return (
        <div className="flex min-h-screen items-center justify-center bg-black text-white">
            <div className="w-full max-w-md space-y-6 px-6">
                {status === 'success' && (
                    <div className="rounded-md border border-green-500/20 bg-green-500/5 px-6 py-8 text-center">
                        <div className="mb-4 text-4xl">✓</div>
                        <h1 className="text-xl font-semibold uppercase tracking-wide">Welcome to Pro!</h1>
                        <p className="mt-3 text-sm text-white/60">
                            Your subscription is now active. You have full access to all Pro features.
                        </p>
                        <Link
                            href="/chat"
                            className="mt-6 inline-block rounded-sm border border-white/20 px-6 py-3 text-sm uppercase tracking-wide transition hover:bg-white hover:text-black"
                        >
                            Go to Chat
                        </Link>
                    </div>
                )}

                {status === 'cancel' && (
                    <div className="rounded-md border border-white/15 bg-white/5 px-6 py-8 text-center">
                        <div className="mb-4 text-4xl text-white/40">×</div>
                        <h1 className="text-xl font-semibold uppercase tracking-wide">Checkout Cancelled</h1>
                        <p className="mt-3 text-sm text-white/60">
                            Your checkout was cancelled. No charges were made.
                        </p>
                        <div className="mt-6 flex gap-3 justify-center">
                            <Link
                                href="/chat"
                                className="inline-block rounded-sm border border-white/20 px-6 py-3 text-sm uppercase tracking-wide transition hover:bg-white/10"
                            >
                                Back to Chat
                            </Link>
                            <button
                                onClick={async () => {
                                    const res = await fetch('/api/stripe/checkout', { method: 'POST' })
                                    if (res.ok) {
                                        const data = await res.json()
                                        if (data?.url) {
                                            window.location.href = data.url
                                        }
                                    }
                                }}
                                className="rounded-sm border border-white/20 px-6 py-3 text-sm uppercase tracking-wide transition hover:bg-white hover:text-black"
                            >
                                Try Again
                            </button>
                        </div>
                    </div>
                )}

                {!status && (
                    <div className="rounded-md border border-white/15 bg-white/5 px-6 py-8 text-center">
                        <h1 className="text-xl font-semibold uppercase tracking-wide">Billing</h1>
                        <p className="mt-3 text-sm text-white/60">
                            Manage your subscription and billing details.
                        </p>
                        <Link
                            href="/chat"
                            className="mt-6 inline-block rounded-sm border border-white/20 px-6 py-3 text-sm uppercase tracking-wide transition hover:bg-white/10"
                        >
                            Back to Chat
                        </Link>
                    </div>
                )}
            </div>
        </div>
    )
}

export default function BillingPage() {
    return (
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-black text-white">Loading…</div>}>
            <BillingContent />
        </Suspense>
    )
}

