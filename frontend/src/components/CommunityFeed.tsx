import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, createPost, getPosts } from "../api/client";
import type { Post, UserRole } from "../types";
import { formatRelativeTime } from "../lib/format";

function RoleBadge({ role }: { role: UserRole }) {
  if (role === "veterinarian") {
    return (
      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
        Veterinarian
      </span>
    );
  }
  return (
    <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
      Pet Owner
    </span>
  );
}

function PostItem({ post }: { post: Post }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-800">{post.author.display_name}</span>
        <RoleBadge role={post.author.role} />
        <time className="ml-auto text-xs text-slate-400" dateTime={post.created_at}>
          {formatRelativeTime(post.created_at)}
        </time>
      </header>
      <h3 className="mt-2 font-semibold text-slate-800">{post.title}</h3>
      <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-slate-600">
        {post.content}
      </p>
      <footer className="mt-3 text-xs text-slate-400">
        {post.comment_count} {post.comment_count === 1 ? "comment" : "comments"}
      </footer>
    </article>
  );
}

export default function CommunityFeed() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const loadPosts = useCallback(async () => {
    setLoadError(null);
    try {
      setPosts(await getPosts());
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : "Could not load posts. Is the backend running?",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPosts();
  }, [loadPosts]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim() || !content.trim()) return;

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await createPost(title.trim(), content.trim());
      setTitle("");
      setContent("");
      await loadPosts();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Could not publish the post.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <h2 className="text-lg font-semibold text-slate-800">Community discussions</h2>
      <p className="mt-1 text-sm text-slate-500">
        Ask questions and get feedback from other owners and veterinary professionals.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Post title"
          maxLength={255}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Describe your question or share advice…"
          rows={3}
          className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <div className="flex items-center justify-between gap-3">
          {submitError ? (
            <p className="text-sm text-rose-600" role="alert">
              {submitError}
            </p>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={isSubmitting || !title.trim() || !content.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isSubmitting ? "Publishing…" : "Publish post"}
          </button>
        </div>
      </form>

      <div className="mt-5 space-y-3">
        {isLoading && <p className="text-sm text-slate-500">Loading discussions…</p>}

        {loadError && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {loadError}{" "}
            <button onClick={() => void loadPosts()} className="font-medium underline">
              Retry
            </button>
          </div>
        )}

        {!isLoading && !loadError && posts.length === 0 && (
          <p className="text-sm text-slate-500">No discussions yet — start the first one!</p>
        )}

        {posts.map((post) => (
          <PostItem key={post.id} post={post} />
        ))}
      </div>
    </section>
  );
}
