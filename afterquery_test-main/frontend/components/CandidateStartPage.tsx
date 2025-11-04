"use client";

import { useEffect, useState } from "react";
import { api } from "@/utils/api";
import { useMemo } from "react";

export type StartMeta = {
  assessment: { title: string; instructions?: string | null; seed_repo_url: string; branch: string };
  invite: { status: string; start_deadline_at?: string | null; complete_deadline_at?: string | null; started_at?: string | null; submitted_at?: string | null };
  git?: { clone_url: string; branch: string };
};

export default function CandidateStartPage({ slug }: { slug: string }) {
  const [meta, setMeta] = useState<StartMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [git, setGit] = useState<{ clone_url: string; branch: string } | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [commitLoading, setCommitLoading] = useState(false);
  const [commits, setCommits] = useState<any[]>([]);
  const [commitsError, setCommitsError] = useState<string | null>(null);

  useEffect(() => {
    api.get<StartMeta>(`/api/candidate/start/${slug}`)
      .then((data) => {
        console.log("GET response:", data);
        setMeta(data);
        // If git info is included in the response, set it
        if (data.git && data.git.clone_url) {
          console.log("Setting git info:", data.git);
          setGit(data.git);
        } else {
          console.log("No git info in response");
          // If status is started/submitted but no git info, clear git state
          // (this shouldn't happen, but handle gracefully)
          setGit(null);
        }
      })
      .catch((e) => {
        console.error("Error fetching start page:", e);
        setError(e?.message || "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [slug]);

  // Fetch commits if started or submitted
  useEffect(() => {
    if (!meta) return;
    if (["started", "submitted"].includes(meta.invite.status)) {
      setCommitLoading(true);
      setCommitsError(null);
      api.get<any[]>(`/api/candidate/commits/${slug}`)
        .then(setCommits)
        .catch(e => setCommitsError("Could not load commits"))
        .finally(() => setCommitLoading(false));
    } else {
      setCommits([]);
    }
  }, [meta, slug]);

  async function handleStart() {
    try {
      setError(null);
      const res = await api.post<{ git: { clone_url: string; branch: string } }>(`/api/candidate/start/${slug}`);
      setGit(res.git);
      // refresh meta after starting to get deadlines
      const m = await api.get<StartMeta>(`/api/candidate/start/${slug}`);
      setMeta(m);
    } catch (e: any) {
      setError(e?.message || "Failed to start");
    }
  }

  async function handleSubmit() {
    try {
      setError(null);
      await api.post(`/api/candidate/submit/${slug}`);
      const m = await api.get<StartMeta>(`/api/candidate/start/${slug}`);
      setMeta(m);
      // Extract git info from refreshed meta
      if (m.git) {
        setGit(m.git);
      }
      setSuccess("Your assessment has been submitted successfully. The client will review and follow up shortly.");
    } catch (e: any) {
      setError(e?.message || "Failed to submit");
    }
  }

  if (loading) return <div>Loading...</div>;
  if (error) return <div style={{ color: "#b91c1c" }}>{error}</div>;
  if (!meta) return <div>Not found</div>;

  const { assessment, invite } = meta;

  return (
    <div className="grid gap-6 max-w-2xl mx-auto p-6">
      {success ? (
        <div className="bg-emerald-50 border border-emerald-400 text-emerald-700 p-3 rounded">{success}</div>
      ) : null}

      {/* Status banner */}
      <div className="flex items-center gap-3">
        <span className={`px-2 py-1 rounded font-semibold text-xs ${invite.status === "started" ? "bg-yellow-200 text-yellow-900" : invite.status === "submitted" ? "bg-green-100 text-green-900" : "bg-gray-200 text-gray-800"}`}>{
          invite.status === "started"
            ? "In Progress"
            : invite.status.charAt(0).toUpperCase() + invite.status.slice(1)
        }</span>
        {invite.started_at && <span className="text-xs text-gray-500">Started on {new Date(invite.started_at).toLocaleString()}</span>}
      </div>

      {/* Title and repo info */}
      <h2 className="text-2xl font-bold mb-1">{assessment.title}</h2>
      <div className="text-xs text-gray-500 mb-2">Seed: {assessment.seed_repo_url} · Branch: {assessment.branch}</div>

      {/* Clone command */}
      {git && git.clone_url ? (
        <section>
          <div className="font-semibold mb-1">A git repository has been created for you. Clone it with:</div>
          <div className="bg-gray-100 p-3 rounded flex items-center text-sm">
            <code className="whitespace-nowrap overflow-x-auto">{`git clone ${git.clone_url}`}</code>
          </div>
          <div className="text-xs text-gray-500 mt-2">Once complete, ensure your work is committed and pushed to the <span className="font-bold">main</span> branch.</div>
        </section>
      ) : invite.status === "pending" ? null : (
        <section>
          <div className="text-gray-500 text-sm">
            {"Check your GitHub repositories. It will be the latest generated one."}
          </div>
        </section>
      )}

      {/* Instructions */}
      <section>
        <h3 className="font-bold mb-2 text-lg">Instructions</h3>
        {assessment.instructions ? (
          <div className="bg-gray-50 border border-gray-200 rounded p-3 whitespace-pre-line">{assessment.instructions}</div>
        ) : (
          <div className="bg-gray-50 border border-gray-200 rounded p-3">No instructions have been provided for this challenge.</div>
        )}
      </section>

      {/* Commits info */}
      {invite.status !== "pending" ? (
        <section>
          <h3 className="font-bold mb-2 text-lg">Your Commits</h3>
          <div className="bg-gray-50 border border-gray-200 rounded p-3">
            {commitLoading ? (
              <div className="text-gray-400">Loading commits…</div>
            ) : commitsError ? (
              <div className="text-red-700">{commitsError}</div>
            ) : commits.length === 0 ? (
              <div className="text-gray-400">No commits pushed yet.</div>
            ) : (
              <>
                <div className="text-sm mb-2">You have pushed {commits.length} commit{commits.length > 1 ? "s" : ""} to the main branch:</div>
                <ul className="divide-y divide-gray-100 text-sm">
                  {commits.map((c) => (
                    <li key={c.sha} className="py-2">
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
              </>
            )}
            <div className="text-xs text-gray-400 mt-2">Tip: run <code>git push origin main</code> from your repo.</div>
          </div>
        </section>
      ) : null}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handleStart}
          disabled={invite.status !== "pending"}
          className={`rounded px-4 py-2 text-white font-semibold transition ${invite.status !== "pending" ? "bg-gray-500 cursor-not-allowed opacity-60" : "bg-gray-900 hover:bg-gray-800"}`}
        >
          Start
        </button>
        <button
          onClick={handleSubmit}
          disabled={invite.status !== "started"}
          className={`rounded px-4 py-2 text-white font-semibold transition ${invite.status !== "started" ? "bg-blue-200 cursor-not-allowed opacity-60" : "bg-green-600 hover:bg-green-700"}`}
        >
          Mark as Finished
        </button>
      </div>
    </div>
  );
}
