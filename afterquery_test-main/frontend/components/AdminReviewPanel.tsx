"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/utils/api";

export type ReviewData = {
  invite: { id: string; status: string; started_at?: string | null; submitted_at?: string | null };
  assessment: { id: string; title: string; seed_repo_url: string };
  candidate: { id: string; email: string; full_name?: string | null };
  repo?: { full_name: string; pinned_main_sha?: string | null; archived: boolean } | null;
  submission?: { final_sha?: string | null; submitted_at: string } | null;
  commits: any[];
  diff: { against: { seed_repo: string; branch: string }; files_changed: any[] };
};

export default function AdminReviewPanel({ data }: { data: ReviewData }) {
  const { invite, assessment, candidate, repo, submission, commits, diff } = data;
  const [followups, setFollowups] = useState<any[]>([]);
  const [followupsLoading, setFollowupsLoading] = useState(true);
  const [diffFiles, setDiffFiles] = useState<any[]>([]);
  const [diffLoading, setDiffLoading] = useState(true);
  const [inlineComments, setInlineComments] = useState<any[]>([]);
  const [inlineLoading, setInlineLoading] = useState(true);
  const [overallText, setOverallText] = useState("");
  const [savingOverall, setSavingOverall] = useState(false);
  const [overallComments, setOverallComments] = useState<any[]>([]);
  const [overallLoading, setOverallLoading] = useState(true);
  const [sendingInlineComments, setSendingInlineComments] = useState(false);

  useEffect(() => {
    setFollowupsLoading(true);
    fetch(`${API_BASE_URL}/api/review/followup/${invite.id}`)
      .then((r) => r.json())
      .then(setFollowups)
      .finally(() => setFollowupsLoading(false));
  }, [invite.id]);

  useEffect(() => {
    setDiffLoading(true);
    fetch(`${API_BASE_URL}/api/review/diff/${invite.id}`)
      .then((r) => r.json())
      .then(setDiffFiles)
      .finally(() => setDiffLoading(false));
  }, [invite.id]);

  useEffect(() => {
    setInlineLoading(true);
    fetch(`${API_BASE_URL}/api/review/inline-comments/${invite.id}`)
      .then((r) => r.json())
      .then(setInlineComments)
      .finally(() => setInlineLoading(false));
  }, [invite.id]);

  useEffect(() => {
    setOverallLoading(true);
    fetch(`${API_BASE_URL}/api/review/comments/${invite.id}`)
      .then((r) => r.json())
      .then(setOverallComments)
      .finally(() => setOverallLoading(false));
  }, [invite.id]);

  async function sendFollowUp() {
    try {
      await fetch(`${API_BASE_URL}/api/review/followup/${invite.id}`, { method: "POST" });
      alert("Follow-up email sent");
      // refresh history
      setFollowupsLoading(true);
      fetch(`${API_BASE_URL}/api/review/followup/${invite.id}`)
        .then((r) => r.json())
        .then(setFollowups)
        .finally(() => setFollowupsLoading(false));
    } catch (e) {
      alert("Failed to send follow-up");
    }
  }
  return (
    <div className="grid gap-6 max-w-2xl mx-auto p-6">
      <section className="rounded bg-white p-4 shadow-sm border">
        <h2 className="text-2xl font-bold mb-1">{assessment.title}</h2>
        <div className="text-xs text-gray-500">Seed: {assessment.seed_repo_url} · Branch: {diff.against.branch}</div>
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <div><span className="font-bold">Candidate:</span> {candidate.full_name || candidate.email} ({candidate.email})</div>
        <div><span className="font-bold">Status:</span> {invite.status.charAt(0).toUpperCase() + invite.status.slice(1)}</div>
        <div className="text-xs text-gray-500">
          {invite.started_at ? <>Started: {new Date(invite.started_at).toLocaleString()} &middot; </> : null}
          {invite.submitted_at ? <>Submitted: {new Date(invite.submitted_at).toLocaleString()}</> : null}
        </div>
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <h3 className="font-semibold mb-2 text-lg">Repository</h3>
        {repo ? (
          <div>
            <div>
              Repo: <a
                href={`https://github.com/${repo.full_name}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-blue-600 hover:underline"
              >
                {repo.full_name}
              </a>
            </div>
            {repo.pinned_main_sha ? <div>Pinned SHA: <span className="font-mono text-gray-600">{repo.pinned_main_sha}</span></div> : null}
            <div>Archived: {repo.archived ? "Yes" : "No"}</div>
          </div>
        ) : (
          <div className="text-gray-400">No repo created.</div>
        )}
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <h3 className="font-semibold mb-2 text-lg">Submission</h3>
        {submission ? (
          <div>
            <div>Final SHA: <span className="font-mono">{submission.final_sha || "(unknown)"}</span></div>
            <div>Submitted At: {new Date(submission.submitted_at).toLocaleString()}</div>
            <div className="mt-2">
              <button onClick={sendFollowUp} className="bg-violet-600 hover:bg-violet-700 text-white px-3 py-1.5 rounded font-semibold">Send Follow-Up</button>
            </div>
            <div className="mt-4">
              <div className="font-semibold mb-1">Follow-Up History</div>
              {followupsLoading ? (
                <div className="text-gray-400 text-sm">Loading…</div>
              ) : followups.length === 0 ? (
                <div className="text-gray-400 text-sm">No follow-ups sent yet.</div>
              ) : (
                <ul className="text-sm divide-y divide-gray-100">
                  {followups.map((f) => (
                    <li key={f.id} className="py-1 flex justify-between gap-2">
                      <span className="truncate text-gray-700">{f.template_subject}</span>
                      <span className="text-gray-500 text-xs">{new Date(f.sent_at).toLocaleString()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : (
          <div className="text-gray-600">Not submitted yet. Status: <span className="font-bold">In Progress</span></div>
        )}
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <h3 className="font-semibold mb-2 text-lg">Commit History</h3>
        {commits.length === 0 ? (
          <div className="text-gray-400">No commits listed.</div>
        ) : (
          <ul className="divide-y divide-gray-100 text-sm">
            {commits.map((c: any, idx: number) => (
              <li key={idx} className="py-2">
                <div className="flex justify-between flex-wrap gap-2">
                  <span className="font-semibold text-gray-900 truncate">{c.message}</span>
                  <span className="text-gray-600 truncate text-right max-w-[48%]">{c.author_name} &lt;{c.author_email}&gt;</span>
                </div>
                <div className="flex justify-between items-center gap-2 text-xs mt-0.5">
                  <span className="text-gray-400 font-mono">{c.sha.slice(0, 12)}</span>
                  <span className="text-gray-400 text-right min-w-[110px]">{new Date(c.date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} on {new Date(c.date).toLocaleDateString()}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <div className="flex justify-between items-center mb-2">
          <h3 className="font-semibold text-lg">Diff vs Seed (main)</h3>
          {inlineComments.length > 0 && (
            <button
              onClick={async () => {
                setSendingInlineComments(true);
                try {
                  const response = await fetch(`${API_BASE_URL}/api/review/send-inline-comments/${invite.id}`, {
                    method: "POST",
                  });
                  if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || "Failed to send email");
                  }
                  alert(`Email sent successfully! Sent ${inlineComments.length} inline comments to ${candidate.email}`);
                } catch (e: any) {
                  alert(`Failed to send email: ${e?.message || "Unknown error"}`);
                } finally {
                  setSendingInlineComments(false);
                }
              }}
              disabled={sendingInlineComments}
              className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
              title={`Send inline comments to ${candidate.email}`}
            >
              {sendingInlineComments ? "Sending..." : "Send Inline Comments via Email"}
            </button>
          )}
        </div>
        {diffLoading ? (
          <div className="text-gray-400">Loading…</div>
        ) : diffFiles.length === 0 ? (
          <div className="text-gray-400">No changes detected.</div>
        ) : (
          <ul className="text-sm space-y-4">
            {diffFiles.map((f) => (
              <DiffFileBlock
                key={f.filename}
                file={f}
                inviteId={invite.id}
                inlineComments={inlineComments.filter((c) => c.file_path === f.filename)}
                inlineLoading={inlineLoading}
                onRefreshComments={async () => {
                  setInlineLoading(true);
                  fetch(`${API_BASE_URL}/api/review/inline-comments/${invite.id}`)
                    .then((r) => r.json())
                    .then(setInlineComments)
                    .finally(() => setInlineLoading(false));
                }}
              />
            ))}
          </ul>
        )}
      </section>
      <section className="rounded bg-white p-4 shadow-sm border">
        <h3 className="font-semibold mb-2 text-lg">Overall Feedback</h3>
        {/* Existing feedback */}
        {overallLoading ? (
          <div className="text-gray-400 text-sm mb-3">Loading…</div>
        ) : overallComments.length === 0 ? (
          <div className="text-gray-400 text-sm mb-3">No feedback yet.</div>
        ) : (
          <ul className="text-sm divide-y divide-gray-100 mb-3">
            {overallComments.map((c) => (
              <li key={c.id} className="py-2 flex justify-between gap-2">
                <span className="text-gray-700">{c.message}</span>
                <span className="text-gray-400 text-xs">{new Date(c.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!overallText.trim()) return;
            setSavingOverall(true);
            await fetch(`${API_BASE_URL}/api/review/comments/${invite.id}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_type: "admin",
                author_email: "admin@yourdomain.com",
                author_name: "Admin",
                message: overallText.trim(),
              }),
            });
            setOverallText("");
            setSavingOverall(false);
            // refresh list
            setOverallLoading(true);
            fetch(`${API_BASE_URL}/api/review/comments/${invite.id}`)
              .then((r) => r.json())
              .then(setOverallComments)
              .finally(() => setOverallLoading(false));
          }}
          className="grid gap-2"
        >
          <textarea
            className="border rounded p-2 h-28 text-sm"
            placeholder="Share overall feedback for the candidate…"
            value={overallText}
            onChange={(e) => setOverallText(e.target.value)}
          />
          <div>
            <button type="submit" disabled={savingOverall || !overallText.trim()} className="px-4 py-2 rounded bg-gray-900 text-white font-semibold disabled:bg-gray-400">{savingOverall ? "Sending…" : "Send Feedback"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

function InlineCommentForm({ inviteId, filePath, onAdded, prefillLine }: { inviteId: string; filePath: string; onAdded: () => void; prefillLine?: number | null }) {
  const [message, setMessage] = useState("");
  const [line, setLine] = useState<string>("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (prefillLine != null) {
      setLine(String(prefillLine));
    }
  }, [prefillLine]);

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!message.trim()) return;
        setSaving(true);
        await fetch(`${API_BASE_URL}/api/review/inline-comments/${inviteId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: filePath, line: line ? Number(line) : null, message, author_email: "admin@yourdomain.com", author_name: "Admin" }),
        });
        setMessage("");
        setLine("");
        setSaving(false);
        onAdded();
      }}
      className="mt-2 flex gap-2 items-center"
    >
      <input
        type="number"
        placeholder="Line"
        value={line}
        onChange={(e) => setLine(e.target.value)}
        className="w-20 border rounded p-1 text-xs"
      />
      <input
        type="text"
        placeholder="Add an inline comment…"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        className="flex-1 border rounded p-1.5 text-xs"
      />
      <button type="submit" disabled={saving || !message.trim()} className="px-2 py-1 rounded bg-gray-900 text-white text-xs disabled:bg-gray-400">{saving ? "Adding…" : "Comment"}</button>
    </form>
  );
}

function DiffFileBlock({ file, inviteId, inlineComments, inlineLoading, onRefreshComments }: { file: any; inviteId: string; inlineComments: any[]; inlineLoading: boolean; onRefreshComments: () => void }) {
  const [selectedLine, setSelectedLine] = useState<number | null>(null);

  return (
    <li className="border rounded p-3">
      <div className="flex justify-between text-sm font-medium mb-2">
        <span className="font-mono text-blue-600">{file.filename}</span>
        <span className="text-gray-500">+{file.additions} -{file.deletions} · {file.status}</span>
      </div>
      {file.patch ? (
        <DiffViewer patch={file.patch} onPickLine={(ln) => setSelectedLine(ln)} />
      ) : (
        <div className="text-xs text-gray-400">No patch available.</div>
      )}
      <div className="mt-3">
        <div className="font-medium mb-1">Inline Comments</div>
        {inlineLoading ? (
          <div className="text-xs text-gray-400">Loading…</div>
        ) : (
          <ul className="text-xs space-y-1">
            {inlineComments.map((c) => (
              <li key={c.id} className="flex justify-between items-center gap-2">
                <div className="flex-1">
                  <span className="text-gray-700">{c.message}</span>
                  <span className="text-gray-400 ml-2">{c.line != null ? `L${c.line}` : ''} {new Date(c.created_at).toLocaleString()}</span>
                </div>
                <button
                  onClick={async () => {
                    if (!confirm("Are you sure you want to delete this comment?")) return;
                    try {
                      const response = await fetch(`${API_BASE_URL}/api/review/inline-comments/${c.id}`, {
                        method: "DELETE",
                      });
                      if (!response.ok) {
                        throw new Error("Failed to delete comment");
                      }
                      onRefreshComments();
                    } catch (e: any) {
                      alert(`Failed to delete comment: ${e?.message || "Unknown error"}`);
                    }
                  }}
                  className="px-2 py-1 rounded bg-red-600 hover:bg-red-700 text-white text-xs font-medium"
                  title="Delete comment"
                >
                  Delete
                </button>
              </li>
            ))}
            {inlineComments.length === 0 ? (
              <li className="text-gray-400">No comments yet.</li>
            ) : null}
          </ul>
        )}
        <InlineCommentForm inviteId={inviteId} filePath={file.filename} onAdded={onRefreshComments} prefillLine={selectedLine} />
      </div>
    </li>
  );
}

function DiffViewer({ patch, onPickLine }: { patch: string; onPickLine: (line: number) => void }) {
  // Parse unified diff and render with old/new line numbers.
  // We display new-file line numbers for additions and context lines; deletions show old-file numbers.
  const lines = patch.split("\n");
  let oldLine = 0;
  let newLine = 0;
  const rendered = [] as any[];

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (raw.startsWith("@@")) {
      // Hunk header: @@ -a,b +c,d @@
      const m = raw.match(/@@\s-([0-9]+)(?:,[0-9]+)?\s\+([0-9]+)(?:,[0-9]+)?\s@@/);
      if (m) {
        oldLine = parseInt(m[1], 10);
        newLine = parseInt(m[2], 10);
      }
      rendered.push(
        <div key={`h-${i}`} className="bg-gray-100 text-gray-600 px-2 py-1 rounded text-[11px] font-mono overflow-auto">
          {raw}
        </div>
      );
      continue;
    }

    let type: "add" | "del" | "ctx" = "ctx";
    let displayOld: number | null = null;
    let displayNew: number | null = null;

    if (raw.startsWith("+")) {
      type = "add";
      displayOld = null;
      displayNew = newLine;
      newLine += 1;
    } else if (raw.startsWith("-")) {
      type = "del";
      displayOld = oldLine;
      displayNew = null;
      oldLine += 1;
    } else {
      type = "ctx";
      displayOld = oldLine;
      displayNew = newLine;
      oldLine += 1;
      newLine += 1;
    }

    // Build line number cells
    const oldCell = (
      <span className="w-10 text-right pr-2 text-[11px] text-gray-400 select-none">
        {displayOld != null ? displayOld : ''}
      </span>
    );
    const newCell = (
      <span className="w-10 text-right pr-2 text-[11px] text-gray-400 select-none">
        {displayNew != null ? displayNew : ''}
      </span>
    );

    const bg = type === "add" ? "bg-green-50" : type === "del" ? "bg-red-50" : "";
    const sign = raw[0] || " ";
    const content = raw.startsWith("+") || raw.startsWith("-") ? raw.slice(1) : raw;

    rendered.push(
      <div
        key={`l-${i}`}
        className={`flex items-start font-mono text-[12px] ${bg} border-b border-gray-100`}
      >
        {oldCell}
        {newCell}
        <span className="w-4 text-center text-gray-400 select-none">{sign}</span>
        <button
          type="button"
          className="text-left whitespace-pre-wrap flex-1 px-2 py-0.5 hover:bg-yellow-50"
          onClick={() => {
            // Prefer new-file line for commenting when available; fallback to old.
            const ln = displayNew != null ? displayNew : (displayOld != null ? displayOld : 0);
            if (ln) onPickLine(ln);
          }}
          title={displayNew != null ? `Comment on L${displayNew}` : (displayOld != null ? `Comment on L${displayOld}` : undefined)}
        >
          {content}
        </button>
      </div>
    );
  }

  return (
    <div className="text-xs overflow-auto bg-gray-50 border rounded">
      {/* header row */}
      <div className="flex items-center px-2 py-1 border-b border-gray-200 text-[11px] text-gray-500 font-mono">
        <span className="w-10 pr-2 text-right">old</span>
        <span className="w-10 pr-2 text-right">new</span>
        <span className="w-4 text-center">±</span>
        <span className="pl-2">code</span>
      </div>
      {rendered}
    </div>
  );
}
