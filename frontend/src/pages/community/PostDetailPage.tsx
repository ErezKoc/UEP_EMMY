import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, createComment, getPost, toggleHelpful } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import ReportButton from "../../components/ReportButton";
import {
  ArrowLeftIcon,
  Avatar,
  Button,
  ChatIcon,
  CheckIcon,
  Input,
  RoleBadge,
  SendIcon,
  Spinner,
  Textarea,
  useToast,
} from "../../components/ui";
import { formatRelativeTime } from "../../lib/format";
// `Comment` is imported explicitly because the DOM has a global type of the
// same name, and TypeScript resolves that one otherwise.
import type { Comment, PostDetail } from "../../types";

export default function PostDetailPage() {
  const { postId } = useParams();
  const { user } = useSession();
  const { toast } = useToast();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // The answer currently being voted on, so its button can disable itself
  // without freezing every other button in the thread.
  const [voting, setVoting] = useState<string | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [commentError, setCommentError] = useState<string | null>(null);

  const loadPost = useCallback(async () => {
    if (!postId) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      setPost(await getPost(postId));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load this post.");
    } finally {
      setIsLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    void loadPost();
  }, [loadPost]);

  /*
   * Optimistic, and reconciled from the server's answer.
   *
   * The count is the only number on this page anybody acts on, so the button
   * reflects the press immediately and then takes whatever the server says as
   * the truth — a failed request puts the old value back rather than leaving a
   * vote the database never recorded.
   */
  const markHelpful = async (target: Comment) => {
    if (!user || user.id === target.author.id) return;
    setVoting(target.id);
    try {
      const updated = await toggleHelpful(target.id);
      setPost((current) =>
        current
          ? {
              ...current,
              comments: current.comments.map((c) => (c.id === updated.id ? updated : c)),
            }
          : current,
      );
    } catch (err) {
      setCommentError(err instanceof ApiError ? err.message : "Could not record that.");
    } finally {
      setVoting(null);
    }
  };

  const handleComment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!postId || !post || !comment.trim()) return;
    setSubmitting(true);
    setCommentError(null);
    try {
      const created = await createComment(postId, comment.trim(), {
        url: sourceUrl,
        title: sourceTitle,
      });
      setPost({ ...post, comments: [...post.comments, created], comment_count: post.comment_count + 1 });
      setComment("");
      setSourceUrl("");
      setSourceTitle("");
      toast("Comment posted.", "success");
    } catch (err) {
      setCommentError(err instanceof ApiError ? err.message : "Could not post the comment.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/community" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
        <ArrowLeftIcon className="h-4 w-4" /> Back to community
      </Link>

      {isLoading && <div className="flex justify-center py-20"><Spinner /></div>}
      {!isLoading && loadError && (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
          {loadError} <button onClick={() => void loadPost()} className="font-medium underline">Retry</button>
        </div>
      )}

      {!isLoading && post && (
        <>
          <article className="rounded-lg bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <header className="flex flex-wrap items-center gap-2">
              <Avatar name={post.author.display_name} src={post.author.avatar_url} />
              <div>
                <p className="text-sm font-semibold text-slate-800">{post.author.display_name}</p>
                <time className="text-xs text-slate-400" dateTime={post.created_at}>{formatRelativeTime(post.created_at)}</time>
              </div>
              <RoleBadge user={post.author} />
              <div className="ml-auto">
                <ReportButton
                  authorId={post.author.id}
                  target={{ type: "post", id: post.id, authorName: post.author.display_name }}
                />
              </div>
            </header>
            <h1 className="mt-5 text-2xl font-bold text-slate-800">{post.title}</h1>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">{post.content}</p>
            {post.image_url && (
              <img src={post.image_url} alt="AI analysis shared with this post" className="mt-5 max-h-[32rem] w-full rounded-lg object-contain bg-slate-100 ring-1 ring-slate-200" />
            )}
          </article>

          <section className="mt-6">
            <div className="flex items-center gap-2">
              <ChatIcon className="h-5 w-5 text-slate-500" />
              <h2 className="text-lg font-semibold text-slate-800">Comments ({post.comment_count})</h2>
            </div>

            <div className="mt-4 space-y-3">
              {post.comments.length === 0 && (
                <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">No comments yet. Start the conversation.</p>
              )}
              {post.comments.map((item) => (
                <article key={item.id} className="rounded-lg border border-slate-200 bg-white p-4">
                  <header className="flex flex-wrap items-center gap-2">
                    <Avatar name={item.author.display_name} src={item.author.avatar_url} size="sm" />
                    <span className="text-sm font-semibold text-slate-800">{item.author.display_name}</span>
                    <RoleBadge user={item.author} />
                    <time className="sm:ml-auto text-xs text-slate-400" dateTime={item.created_at}>{formatRelativeTime(item.created_at)}</time>
                  </header>
                  <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{item.content}</p>

                  {/*
                    The citation, presented as one. This platform already holds
                    its own clinical advice to "name the page it came from";
                    an answer typed here reaches an owner the same way and
                    carried nothing until now.
                  */}
                  {item.source_url && (
                    <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <span className="font-semibold">Source: </span>
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="break-all text-primary-600 underline hover:text-primary-700"
                      >
                        {item.source_title || item.source_url.replace(/^https?:\/\//, "")}
                      </a>
                    </p>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => void markHelpful(item)}
                      disabled={!user || user.id === item.author.id || voting === item.id}
                      aria-pressed={item.viewer_found_helpful}
                      title={
                        !user
                          ? "Sign in to mark answers helpful"
                          : user.id === item.author.id
                            ? "You cannot mark your own answer helpful"
                            : item.viewer_found_helpful
                              ? "You marked this helpful — press again to undo"
                              : "This answer helped me"
                      }
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                        item.viewer_found_helpful
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      <CheckIcon className="h-3.5 w-3.5" />
                      Helpful
                      {item.helpful_count > 0 && (
                        <span className="tabular-nums">· {item.helpful_count}</span>
                      )}
                    </button>

                    <span className="ml-auto">
                      <ReportButton
                        authorId={item.author.id}
                        target={{ type: "comment", id: item.id, authorName: item.author.display_name }}
                      />
                    </span>
                  </div>
                </article>
              ))}
            </div>

            <div className="mt-5 rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200">
              {user ? (
                <form onSubmit={handleComment}>
                  <Textarea
                    label="Add a comment"
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Share useful advice or ask a follow-up question."
                    rows={4}
                    maxLength={5000}
                  />
                  {/*
                    Offered to everyone, not just veterinarians. An owner
                    linking the page that helped them is worth as much to the
                    next reader, and gating the field by role would make the
                    absence of a source look like a professional judgement
                    rather than a choice.
                  */}
                  <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr]">
                    <Input
                      label="Source link (optional)"
                      value={sourceUrl}
                      onChange={(event) => setSourceUrl(event.target.value)}
                      placeholder="https://"
                      maxLength={1024}
                    />
                    <Input
                      label="What is it called? (optional)"
                      value={sourceTitle}
                      onChange={(event) => setSourceTitle(event.target.value)}
                      placeholder="VCA — First Aid for Limping Dogs"
                      maxLength={200}
                      hint="Shown with your answer so readers can check it."
                    />
                  </div>

                  {commentError && <p className="mt-2 text-sm text-rose-600" role="alert">{commentError}</p>}
                  <div className="mt-3 flex justify-end">
                    <Button type="submit" loading={submitting} disabled={!comment.trim()}>
                      <SendIcon className="h-4 w-4" /> Post comment
                    </Button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-slate-600">Sign in to join this discussion.</p>
                  <Link to="/login" state={{ from: `/community/${post.id}` }} className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">Sign in to comment</Link>
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
