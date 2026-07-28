import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, createComment, getPost } from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import {
  ArrowLeftIcon,
  Avatar,
  Badge,
  Button,
  ChatIcon,
  SendIcon,
  Spinner,
  Textarea,
  useToast,
} from "../../components/ui";
import { formatRelativeTime } from "../../lib/format";
import type { PostDetail, UserRole } from "../../types";

function RoleBadge({ role }: { role: UserRole }) {
  return (
    <Badge variant={role === "veterinarian" ? "vet" : "neutral"}>
      {role === "veterinarian" ? "Veterinarian" : "Pet owner"}
    </Badge>
  );
}

export default function PostDetailPage() {
  const { postId } = useParams();
  const { user } = useSession();
  const { toast } = useToast();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
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

  const handleComment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!postId || !post || !comment.trim()) return;
    setSubmitting(true);
    setCommentError(null);
    try {
      const created = await createComment(postId, comment.trim());
      setPost({ ...post, comments: [...post.comments, created], comment_count: post.comment_count + 1 });
      setComment("");
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
              <RoleBadge role={post.author.role} />
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
                    <RoleBadge role={item.author.role} />
                    <time className="sm:ml-auto text-xs text-slate-400" dateTime={item.created_at}>{formatRelativeTime(item.created_at)}</time>
                  </header>
                  <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{item.content}</p>
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
