"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/utils/api";
import type { Assessment } from "@/components/ChallengeCreationForm";

type ManagedAssessment = Assessment & { _archived?: boolean };

export default function ManageChallengesPage() {
  const [assessments, setAssessments] = useState<ManagedAssessment[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalAssessment, setModalAssessment] = useState<Assessment | null>(null);
  const [newRepoUrl, setNewRepoUrl] = useState("");

  // Local form state for editing repository URL (and optionally title for clarity)
  const selected = useMemo(() => assessments.find(a => a.id === selectedId) || null, [assessments, selectedId]);
  const [editTitle, setEditTitle] = useState<string>("");
  const [editRepoUrl, setEditRepoUrl] = useState<string>("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const available = await api.get<Assessment[]>("/api/assessments/?status=available");
        const archived = await api.get<Assessment[]>("/api/assessments/?status=archived");
        setAssessments([
          ...available.map(a => ({ ...a, _archived: false })),
          ...archived.map(a => ({ ...a, _archived: true })),
        ]);
      } catch (e: any) {
        setError(e?.message || "Failed to load challenges");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (selected) {
      setEditTitle(selected.title);
      setEditRepoUrl(selected.seed_repo_url);
    } else {
      setEditTitle("");
      setEditRepoUrl("");
    }
  }, [selectedId, selected]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.put<Assessment>(`/api/assessments/${selected.id}`, {
        title: editTitle,
        seed_repo_url: editRepoUrl,
      });
      setAssessments(prev => prev.map(a => (a.id === updated.id ? { ...a, ...updated } : a)));
    } catch (e: any) {
      setError(e?.message || "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  function openActionsModal(a: Assessment) {
    setModalAssessment(a);
    setNewRepoUrl("");
    setModalOpen(true);
  }

  function closeActionsModal() {
    setModalOpen(false);
    setModalAssessment(null);
    setNewRepoUrl("");
  }

  async function handleModalDelete() {
    if (!modalAssessment) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(`/api/assessments/${modalAssessment.id}`);
      setAssessments(prev => prev.filter(a => a.id !== modalAssessment.id));
      if (selectedId === modalAssessment.id) setSelectedId(null);
      closeActionsModal();
    } catch (e: any) {
      setError(e?.message || "Failed to delete challenge");
    } finally {
      setDeleting(false);
    }
  }

  async function handleModalOverwrite() {
    if (!modalAssessment) return;
    const url = newRepoUrl.trim();
    if (!url) {
      setError("Please provide a GitHub repo URL to overwrite with");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await api.put<Assessment>(`/api/assessments/${modalAssessment.id}`, {
        seed_repo_url: url,
      });
      setAssessments(prev => prev.map(a => (a.id === updated.id ? { ...a, ...updated } : a)));
      // If overwriting currently selected, reflect new value in editor
      if (selectedId === updated.id) {
        setEditRepoUrl(updated.seed_repo_url);
      }
      closeActionsModal();
    } catch (e: any) {
      setError(e?.message || "Failed to overwrite repository URL");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    if (!confirm("Are you sure you want to delete this challenge? This cannot be undone.")) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(`/api/assessments/${selected.id}`);
      setAssessments(prev => prev.filter(a => a.id !== selected.id));
      setSelectedId(null);
    } catch (e: any) {
      setError(e?.message || "Failed to delete challenge");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="grid gap-6">
      <h1 className="text-3xl font-semibold text-gray-800">Manage Challenges</h1>
      {error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded">{error}</div>
      ) : null}
      {loading ? (
        <div>Loading…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <h2 className="text-lg font-medium mb-3">Your Challenges</h2>
            {assessments.length === 0 ? (
              <div className="text-sm text-gray-600">No challenges found.</div>
            ) : (
              <ul className="list-none p-0 m-0 divide-y">
                {assessments.map(a => (
                  <li key={a.id} className={`py-3 ${selectedId === a.id ? "bg-emerald-50" : ""}`}>
                    <div className="flex items-start justify-between gap-3 px-2">
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => openActionsModal(a)}
                          className="font-medium text-left text-gray-900 hover:text-emerald-700 focus:outline-none"
                          title="Manage challenge"
                        >
                          {a.title}
                        </button>
                        <div className="text-xs text-gray-500 truncate max-w-[34ch]">{a.seed_repo_url}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!a._archived ? (
                          <button
                            type="button"
                            onClick={() => setSelectedId(a.id)}
                            className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
                            title="Select to edit"
                          >
                            Edit
                          </button>
                        ) : null}
                        <a href={`/challenges/${a.id}`} className="text-blue-600 text-xs underline">Invite</a>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <h2 className="text-lg font-medium mb-3">Edit Challenge</h2>
            {selected ? (
              <form onSubmit={handleSave} className="grid gap-3">
                <label className="flex flex-col gap-1">
                  <span className="text-sm font-medium">Title</span>
                  <input
                    value={editTitle}
                    onChange={e => setEditTitle(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-sm font-medium">Seed GitHub Repo URL</span>
                  <input
                    value={editRepoUrl}
                    onChange={e => setEditRepoUrl(e.target.value)}
                    placeholder="https://github.com/org/repo"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </label>

                <div className="flex items-center gap-3 mt-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="bg-gray-900 hover:bg-gray-800 text-white px-4 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {saving ? "Saving…" : "Save Changes"}
                  </button>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleting ? "Deleting…" : "Delete Challenge"}
                  </button>
                </div>
              </form>
            ) : (
              <div className="text-sm text-gray-600">Select a challenge from the list to edit its repository or delete it.</div>
            )}
          </div>
        </div>
      )}

      {modalOpen && modalAssessment ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={closeActionsModal} />
          <div className="relative bg-white w-full max-w-md mx-4 rounded-lg shadow-xl border border-gray-200 p-5">
            <h3 className="text-lg font-semibold mb-2">Manage “{modalAssessment.title}”</h3>
            <p className="text-sm text-gray-600 mb-4">Choose an action below. Overwriting will replace the seed GitHub repository URL used for new invites.</p>

            <div className="grid gap-3 mb-4">
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">Overwrite with new GitHub repo URL</span>
                <input
                  value={newRepoUrl}
                  onChange={e => setNewRepoUrl(e.target.value)}
                  placeholder="https://github.com/org/repo"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </label>
            </div>

            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleModalDelete}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Delete Challenge"}
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={closeActionsModal}
                  className="px-4 py-2 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleModalOverwrite}
                  disabled={saving}
                  className="bg-gray-900 hover:bg-gray-800 text-white px-4 py-2 rounded-md disabled:opacity-50"
                >
                  {saving ? "Overwriting…" : "Overwrite Repo"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

