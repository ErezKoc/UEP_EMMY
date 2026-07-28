import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, createPost } from "../../api/client";
import { ArrowLeftIcon, Button, Card, ImageIcon, Input, Textarea, XIcon, useToast } from "../../components/ui";
import type { PostPrefill } from "../../types";

export default function NewPostPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const prefill = (location.state as { prefill?: PostPrefill } | null)?.prefill;

  const [title, setTitle] = useState(prefill?.title ?? "");
  const [content, setContent] = useState(prefill?.content ?? "");
  const [attachment, setAttachment] = useState(prefill ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const post = await createPost({
        title: title.trim(),
        content: content.trim(),
        analysis_id: attachment?.analysis_id ?? null,
      });
      toast("Post published.", "success");
      navigate(`/community/${post.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not publish the post.");
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Link to="/community" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700">
        <ArrowLeftIcon className="h-4 w-4" /> Back to community
      </Link>
      <h1 className="text-2xl font-bold text-slate-800">New community post</h1>
      <p className="mt-1 text-sm text-slate-500">Share a question or useful experience with the community.</p>

      <Card className="mt-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <Input
            label="Title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="What would you like help with?"
            maxLength={255}
            required
          />
          <Textarea
            label="Post"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Describe your question and include any useful details."
            rows={9}
            maxLength={10000}
            required
          />

          {attachment && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-start gap-3">
                <img src={attachment.image_url} alt="AI analysis attachment" className="h-20 w-20 shrink-0 rounded-lg object-cover" />
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                    <ImageIcon className="h-4 w-4" /> AI analysis attached
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">
                    The analyzed photo will appear with this post.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setAttachment(null)}
                  aria-label="Remove analysis attachment"
                  title="Remove attachment"
                  className="rounded-lg p-2 text-slate-500 hover:bg-white hover:text-slate-800"
                >
                  <XIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{error}</p>}

          <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
            <Link to="/community" className="inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">Cancel</Link>
            <Button type="submit" loading={submitting} disabled={!title.trim() || !content.trim()}>
              Publish post
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
