import ChatClient from './ChatClient'
import { createServerSupabase } from '@/utils/supabase/server'
import { getState } from '../actions'

export default async function Page() {
    const supabase = await createServerSupabase()
    const { data: {user}} = await supabase.auth.getUser()
    const { runId } = await getState(undefined, { redirectTo: '/chat' })
    const initialMessages: { role: 'user'|'assistant'|'system'; content: string }[] = [] // getting signedin user
    return <ChatClient userId={user?.id ?? null} initialMessages={initialMessages} runId={runId} />
}

