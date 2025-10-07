
import { createThread, getState } from "../actions";


export default async function ResultPage() {
    await createThread();
    const { state } = await getState();
    const plan = state?.values?.plan || "";
    const designBrief = state?.values?.design_brief || "";
    const designJson = state?.values?.design_json || {};
    const output = state?.values?.output || "";


    return (
        <div style={{maxWidth: 800, margin: "40px auto", padding: 24}}>
            <h1>System Design Result</h1>
            {output ? (
                <article>
                    <pre style={{whiteSpace: "pre-wrap"}}>{output}</pre>
                </article>
            ) : (
                <p>Final output not ready yet; return to Clarifier and answer the questions.</p>
            )}

            <div style={{marginTop: 24}}>
                <a href="/clarifier">Back to Clarifier</a>
            </div>

            <details style={{ marginTop: 24}}>
                <summary>Debug fields</summary>
                <h3>Plan</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{plan}</pre>
                <h3>Design Brief</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{designBrief}</pre>
                <h3>Design JSON</h3>
                <pre style={{ whiteSpace: "pre-wrap"}}>{JSON.stringify(designJson, null, 2)}</pre>
            </details>
        </div>
    );
}