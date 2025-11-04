"use client";

import { useState, useEffect } from "react";
import ChallengeCreationForm, { Assessment } from "../../components/ChallengeCreationForm";
import { api } from "@/utils/api";

async function fetchAvailableAssessments(): Promise<Assessment[]> {
  return api.get<Assessment[]>("/api/assessments/?status=available");
}

async function fetchArchivedAssessments(): Promise<Assessment[]> {
  return api.get<Assessment[]>("/api/assessments/?status=archived");
}

export default function ChallengesPage() {
  // const [showSuccess, setShowSuccess] = useState(true);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [activeTab, setActiveTab] = useState<"available" | "archived">("available");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal state for edit actions (delete or overwrite repo URL)
  const [modalOpen, setModalOpen] = useState(false);
  const [modalAssessment, setModalAssessment] = useState<Assessment | null>(null);
  // Modal states
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Fetch assessments whenever the active tab changes
  useEffect(() => {
    const fetch = activeTab === "available" ? fetchAvailableAssessments : fetchArchivedAssessments;
    setError(null);
    fetch().then(setAssessments).catch((e: any) => {
      setAssessments([]);
      setError(e?.message || "Failed to load challenges");
    });
  }, [activeTab]);

  function openActionsModal(a: Assessment) {
    setModalAssessment(a);
    setNewRepoUrl("");
    setConfirmName("");
    setShowDeleteConfirm(false);
    setModalOpen(true);
  }

  function openDeleteModal(a: Assessment) {
    setModalAssessment(a);
    setNewRepoUrl("");
    setConfirmName("");
    setShowDeleteConfirm(true);
    setModalOpen(true);
  }

  function closeActionsModal() {
    setModalOpen(false);
    setModalAssessment(null);
    setNewRepoUrl("");
    setConfirmName("");
    setShowDeleteConfirm(false);
  }

  async function handleModalDelete() {
    if (!modalAssessment) return;
    setDeleting(true);
    setError(null);
    try {
      await api.delete(`/api/assessments/${modalAssessment.id}`);
      setAssessments(prev => prev.filter(a => a.id !== modalAssessment.id));
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
      setAssessments(prev => prev.map(a => (a.id === updated.id ? updated : a)));
      closeActionsModal();
    } catch (e: any) {
      setError(e?.message || "Failed to overwrite repository URL");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main>
      {/* {showSuccess && (
        <div className="bg-green-100 border border-green-500 rounded px-4 py-3 mb-6">
          <div className="flex justify-between items-center">
            <span className="text-green-800 text-sm">Welcome! You have signed up successfully.</span>
            <button 
              onClick={() => setShowSuccess(false)}
              className="bg-transparent border-none cursor-pointer text-lg text-green-800 p-0 w-6 h-6 hover:text-green-900"
            >
              ×
            </button>
          </div>
        </div>
      )} */}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-semibold text-gray-800">Challenges</h1>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-8 shadow-sm">
        <p className="mb-4 text-gray-700">To create a new challenge click below:</p>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="bg-emerald-500 hover:bg-emerald-600 text-white border-none rounded-md px-5 py-2.5 text-sm font-medium cursor-pointer transition-colors"
        >
          Create Challenge
        </button>

        {showCreateForm && (
          <div className="mt-6">
            <ChallengeCreationForm
              onCreated={(assessment) => {
                setAssessments([...assessments, assessment]);
                setShowCreateForm(false);
              }}
            />
          </div>
        )}
      </div>

      <div className="mt-8">
        <div className="flex gap-6 mb-4">
          <button
            onClick={() => setActiveTab("available")}
            className={`bg-transparent border-none pb-2 text-sm cursor-pointer transition-all underline ${
              activeTab === "available" 
                ? "text-blue-600 font-medium border-b-2 border-blue-600" 
                : "text-gray-500 font-normal border-b-2 border-transparent"
            }`}
          >
            Available
          </button>
          <button
            onClick={() => setActiveTab("archived")}
            className={`bg-transparent border-none pb-2 text-sm cursor-pointer transition-all underline ${
              activeTab === "archived" 
                ? "text-blue-600 font-medium border-b-2 border-blue-600" 
                : "text-gray-500 font-normal border-b-2 border-transparent"
            }`}
          >
            Archived
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          {error ? (
            <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-4">{error}</div>
          ) : null}
          {assessments.length === 0 ? (
            <div className="text-center py-10 px-5">
              <p className="text-base font-semibold mb-2 text-gray-800">
                No Challenges Found
              </p>
              <p className="text-sm text-gray-500 mb-2">
                You don&apos;t have any challenges available.
              </p>
              <p className="text-sm text-gray-500">
                If this is your first time here, why not{" "}
                <a 
                  href="#" 
                  onClick={(e) => {
                    e.preventDefault();
                    setShowCreateForm(true);
                  }}
                  className="text-blue-600 underline cursor-pointer hover:text-blue-700"
                >
                  create a challenge
                </a>{" "}
                to see how the process works?
              </p>
            </div>
          ) : (
            <ul className="list-none p-0">
              {assessments.map((a) => (
                <li key={a.id} className="mb-4 p-4 border border-gray-200 rounded-md hover:border-gray-300 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="font-semibold mb-1">{a.title}</div>
                      <div className="text-xs text-gray-500">{a.seed_repo_url}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      {activeTab === "available" ? (
                        <>
                          <a
                            href={`/challenges/${a.id}`}
                            className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1.5 rounded-md no-underline"
                          >
                            Invite
                          </a>
                          <button
                            onClick={async () => {
                              await api.put<Assessment>(`/api/assessments/${a.id}/archive`);
                              const updated = await fetchAvailableAssessments();
                              setAssessments(updated);
                            }}
                            className="bg-gray-200 hover:bg-gray-300 text-gray-800 text-sm px-3 py-1.5 rounded-md border border-gray-300 cursor-pointer"
                          >
                            Archive
                          </button>
                          <button
                            onClick={() => openActionsModal(a)}
                            className="bg-white hover:bg-gray-50 text-gray-800 text-sm px-3 py-1.5 rounded-md border border-gray-300 cursor-pointer"
                            title="Edit challenge"
                          >
                            Edit
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={async () => {
                              await api.put<Assessment>(`/api/assessments/${a.id}/unarchive`);
                              const updated = await fetchArchivedAssessments();
                              setAssessments(updated);
                            }}
                            className="bg-gray-200 hover:bg-gray-300 text-gray-800 text-sm px-3 py-1.5 rounded-md border border-gray-300 cursor-pointer"
                          >
                            Unarchive
                          </button>
                          <button
                            onClick={() => openDeleteModal(a)}
                            className="bg-white hover:bg-gray-50 text-red-700 text-sm px-3 py-1.5 rounded-md border border-red-200 cursor-pointer"
                            title="Delete challenge"
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {modalOpen && modalAssessment ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={closeActionsModal} />
          <div className="relative bg-white w-full max-w-md mx-4 rounded-lg shadow-xl border border-gray-200 p-5">
            <h3 className="text-lg font-semibold mb-2">Manage “{modalAssessment.title}”</h3>
            <p className="text-sm text-gray-600 mb-4">Choose an action below. Overwriting will replace the seed GitHub repository URL used for new invites.</p>

            <div className="grid gap-3 mb-4">
              {!showDeleteConfirm ? (
                <label className="flex flex-col gap-1">
                  <span className="text-sm font-medium">Overwrite with new GitHub repo URL</span>
                  <input
                    value={newRepoUrl}
                    onChange={e => setNewRepoUrl(e.target.value)}
                    placeholder="https://github.com/org/repo"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </label>
              ) : null}
              {showDeleteConfirm ? (
                <label className="flex flex-col gap-1">
                  <span className="text-sm font-medium">Type the challenge name to confirm deletion</span>
                  <input
                    value={confirmName}
                    onChange={e => setConfirmName(e.target.value)}
                    placeholder={modalAssessment.title}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500"
                  />
                  <span className="text-xs text-gray-500">Exact match required: “{modalAssessment.title}”</span>
                </label>
              ) : null}
            </div>

            <div className="flex items-center justify-between gap-3">
              {showDeleteConfirm ? (
                <button
                  type="button"
                  onClick={handleModalDelete}
                  disabled={deleting || confirmName !== modalAssessment.title}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
                >
                  {deleting ? "Deleting…" : "Confirm Delete"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="bg-red-50 hover:bg-red-100 text-red-700 px-4 py-2 rounded-md border border-red-200"
                >
                  Delete
                </button>
              )}
              <div className="flex items-center gap-2">
                {!showDeleteConfirm ? (
                  <button
                    type="button"
                    onClick={handleModalOverwrite}
                    disabled={saving}
                    className="bg-gray-900 hover:bg-gray-800 text-white px-4 py-2 rounded-md disabled:opacity-50"
                  >
                    {saving ? "Overwriting…" : "Overwrite Repo"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
