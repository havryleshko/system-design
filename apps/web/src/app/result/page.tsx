
import { getState } from "../actions";


export default async function ResultPage() {
    const { state } = await getState(undefined, { redirectTo: "/result" });
    const plan = state?.values?.plan || "";
    const designBrief = state?.values?.design_brief || "";
    const designJson = state?.values?.design_json || {};
    const criticScore = state?.values?.critic_score;
    const criticNotes = state?.values?.critic_notes || "";
    const criticFixes: string[] = state?.values?.critic_fixes || [];
    const output = state?.values?.output || "";


    return (
        <div style={{maxWidth: 800, margin: "40px auto", padding: 24}}>
            <h1>System Design Result</h1>
            {output ? (
                <article>
                    <pre style={{whiteSpace: "pre-wrap"}}>{output}</pre>
                </article>
            ) : (
                <p>Final output not ready yet; return to the chat to continue the conversation.</p>
            )}

            <div style={{marginTop: 24}}>
                <a href="/chat">Back to Chat</a>
            </div>

            <details style={{ marginTop: 24}}>
                <summary>Debug fields</summary>
                <h3>Plan</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{plan}</pre>
                <h3>Design Brief</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{designBrief}</pre>
                <h3>Design JSON</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{JSON.stringify(designJson, null, 2)}</pre>
                <h3>Critic Score</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{criticScore ?? "n/a"}</pre>
                <h3>Critic Notes</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{criticNotes}</pre>
                {criticFixes.length ? (
                    <>
                        <h3>Critic Fixes</h3>
                        <ul>
                            {criticFixes.map((fix, idx) => (
                                <li key={idx}>{fix}</li>
                            ))}
                        </ul>
                    </>
                ) : null}
            </details>
        </div>
    );
}