// TODO: Rebuild result page when frontend↔backend wiring is reimplemented
// This page previously used getState() which was removed as part of wiring reset

export default async function ResultPage() {
  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: 24 }}>
      <h1>System Design Result</h1>
      <p>Result page is being rebuilt as part of frontend↔backend wiring redesign.</p>
      <div style={{ marginTop: 24 }}>
        <a href="/chat">Back to Chat</a>
      </div>
    </div>
  );
}
