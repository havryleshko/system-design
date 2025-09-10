import ChatClient from './ChatClient'
import { createServerSupabase } from '@/utils/supabase/server'

export default async function Page() {
    const supabase = await createServerSupabase()
    const { data: {user}} = await supabase.auth.getUser()
    const initialMessages: { role: 'user'|'assistant'|'system'; content: string }[] = [] // getting signedin user
    return <ChatClient userId={user?.id ?? null} initialMessages={initialMessages} />
}

