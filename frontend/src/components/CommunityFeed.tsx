import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, getPosts } from "../api/client";
import { formatRelativeTime } from "../lib/format";
import type { Post } from "../types";
import {
  Avatar,
  Button,
  ChatIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  EmptyState,
  RoleBadge,
  SearchIcon,
  Spinner,
} from "./ui";

const PAGE_SIZE = 6;

function excerpt(content: string, compact: boolean): string {
  const maximum = compact ? 150 : 260;
  return content.length > maximum ? `${content.slice(0, maximum).trim()}...` : content;
}

function PostItem({ post, compact }: { post: Post; compact: boolean }) {
  return (
    <Link
      to={`/community/${post.id}`}
      className="group block rounded-lg border border-slate-200 bg-white p-4 transition hover:border-primary-300 hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
    >
      <article className="flex gap-4">
        <div className="min-w-0 flex-1">
          <header className="flex flex-wrap items-center gap-2">
            <Avatar name={post.author.display_name} src={post.author.avatar_url} size="sm" />
            <span className="text-sm font-semibold text-slate-800">{post.author.display_name}</span>
            <RoleBadge user={post.author} />
            <time className="sm:ml-auto text-xs text-slate-400" dateTime={post.created_at}>
              {formatRelativeTime(post.created_at)}
            </time>
          </header>
          <h3 className="mt-3 font-semibold text-slate-800 group-hover:text-primary-700">
            {post.title}
          </h3>
          <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-slate-600">
            {excerpt(post.content, compact)}
          </p>
          {/*
            Every row used to look identical whether a professional had answered
            it or nobody had. That is most of what "the community looks quiet"
            actually was: a wall of undifferentiated questions with no way to
            see which had gone anywhere.
          */}
          <footer className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs font-medium text-slate-500">
            <span className="flex items-center gap-1.5">
              <ChatIcon className="h-4 w-4" />
              {post.comment_count === 0
                ? "No answers yet"
                : `${post.comment_count} ${post.comment_count === 1 ? "answer" : "answers"}`}
            </span>

            {post.has_vet_answer && (
              <span className="rounded-full bg-teal-50 px-2 py-0.5 text-teal-700 ring-1 ring-teal-200">
                Answered by a vet
              </span>
            )}

            {/* An invitation, not a status: an unanswered question is the one
                place a passing reader can most usefully act. */}
            {post.comment_count === 0 && (
              <span className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-800">
                Needs an answer
              </span>
            )}

            {post.last_activity_at && post.comment_count > 0 && (
              <span className="text-slate-400">
                last reply {formatRelativeTime(post.last_activity_at)}
              </span>
            )}
          </footer>
        </div>
        {post.image_url && (
          <img
            src={post.image_url}
            alt="Attached AI analysis"
            className="h-20 w-20 shrink-0 rounded-lg object-cover ring-1 ring-slate-200 sm:h-24 sm:w-24"
          />
        )}
      </article>
    </Link>
  );
}

export default function CommunityFeed({ compact = false }: { compact?: boolean }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = compact ? "" : searchParams.get("q") ?? "";
  const roleParam = compact ? "" : searchParams.get("role") ?? "";
  const statusParam = compact ? "" : searchParams.get("status") ?? "";
  const sortParam = compact ? "" : searchParams.get("sort") ?? "";
  // Only these two roles author community content, so admin is not a filter option.
  const role: "owner" | "veterinarian" | "" =
    roleParam === "owner" || roleParam === "veterinarian" ? roleParam : "";
  const parsedPage = Number.parseInt(compact ? "1" : searchParams.get("page") ?? "1", 10);
  const page = Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const limit = compact ? 4 : PAGE_SIZE;

  const [draftQuery, setDraftQuery] = useState(query);
  const [posts, setPosts] = useState<Post[]>([]);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => setDraftQuery(query), [query]);

  const loadPosts = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const result = await getPosts({
        limit: compact ? limit : limit + 1,
        offset: compact ? 0 : (page - 1) * limit,
        q: query,
        authorRole: role,
        // Undefined, not false: `answered=false` is the whole point of the
        // "unanswered" filter, so the absent case has to be distinguishable
        // from the deliberate false.
        answered: statusParam === "unanswered" ? false : undefined,
        vetAnswered: statusParam === "vet" ? true : undefined,
        sort: (sortParam || "active") as "recent" | "active" | "discussed",
      });
      setPosts(result.slice(0, limit));
      setHasNextPage(!compact && result.length > limit);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load community posts.");
    } finally {
      setIsLoading(false);
    }
  }, [compact, limit, page, query, role, statusParam, sortParam]);

  useEffect(() => {
    void loadPosts();
  }, [loadPosts]);

  const updateFilters = (next: {
    q?: string;
    role?: string;
    status?: string;
    sort?: string;
    page?: number;
  }) => {
    const params = new URLSearchParams(searchParams);
    const nextQuery = next.q === undefined ? query : next.q.trim();
    const nextRole = next.role === undefined ? role : next.role;
    const nextStatus = next.status === undefined ? statusParam : next.status;
    const nextSort = next.sort === undefined ? sortParam : next.sort;
    const nextPage = next.page ?? 1;
    if (nextQuery) params.set("q", nextQuery);
    else params.delete("q");
    if (nextRole) params.set("role", nextRole);
    else params.delete("role");
    if (nextStatus) params.set("status", nextStatus);
    else params.delete("status");
    if (nextSort) params.set("sort", nextSort);
    else params.delete("sort");
    if (nextPage > 1) params.set("page", String(nextPage));
    else params.delete("page");
    setSearchParams(params);
  };

  /*
   * The filters, as chips rather than another dropdown.
   *
   * "Unanswered" is the one that earns its place. Somebody willing to help had
   * no way to find the questions nobody had replied to — they scrolled a list
   * ordered by date and gave up, which is how a board goes quiet and stays
   * quiet. It is deliberately first.
   */
  const STATUS_FILTERS = [
    { value: "", label: "All" },
    { value: "unanswered", label: "Unanswered" },
    { value: "vet", label: "Answered by a vet" },
  ];

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    updateFilters({ q: draftQuery, page: 1 });
  };

  return (
    <section className={compact ? "rounded-lg bg-white p-5 shadow-sm ring-1 ring-slate-200" : ""}>
      {compact && (
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Community discussions</h2>
            <p className="mt-1 text-sm text-slate-500">Recent questions and advice.</p>
          </div>
          <Link to="/community" className="shrink-0 text-sm font-medium text-primary-600 hover:text-primary-700">
            View all
          </Link>
        </div>
      )}

      {!compact && (
        <div className="grid gap-3 sm:grid-cols-[1fr_190px]">
          <form onSubmit={handleSearch} className="flex gap-2">
            <label htmlFor="community-search" className="sr-only">Search community</label>
            <div className="relative min-w-0 flex-1">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="community-search"
                type="search"
                value={draftQuery}
                onChange={(event) => setDraftQuery(event.target.value)}
                placeholder="Search topics or authors"
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
              />
            </div>
            <Button type="submit" variant="secondary">Search</Button>
          </form>
          <label className="sr-only" htmlFor="author-role">Filter by author</label>
          <select
            id="author-role"
            value={role}
            onChange={(event) => updateFilters({ role: event.target.value, page: 1 })}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
          >
            <option value="">All authors</option>
            <option value="owner">Pet owners</option>
            <option value="veterinarian">Veterinarians</option>
          </select>
        </div>
      )}

      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((option) => (
            <button
              key={option.value}
              onClick={() => updateFilters({ status: option.value, page: 1 })}
              aria-pressed={statusParam === option.value}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                statusParam === option.value
                  ? "bg-primary-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {option.label}
            </button>
          ))}

          <span className="ml-auto flex items-center gap-2">
            <label htmlFor="community-sort" className="text-xs text-slate-500">
              Sort
            </label>
            <select
              id="community-sort"
              value={sortParam || "active"}
              onChange={(event) => updateFilters({ sort: event.target.value, page: 1 })}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-primary-500 focus:outline-none"
            >
              {/*
                "Recently active" is the default, not "newest". A question
                asked in July and answered this morning is live, and ordering
                by asked-date buried every conversation the moment it started.
              */}
              <option value="active">Recently active</option>
              <option value="recent">Newest question</option>
              <option value="discussed">Most discussed</option>
            </select>
          </span>
        </div>
      )}

      <div className={compact ? "mt-5 space-y-3" : "mt-5 space-y-3"}>
        {isLoading && <div className="flex justify-center py-12"><Spinner /></div>}
        {!isLoading && loadError && (
          <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {loadError} <button onClick={() => void loadPosts()} className="font-medium underline">Retry</button>
          </div>
        )}
        {!isLoading && !loadError && posts.length === 0 && (
          <EmptyState
            icon={<ChatIcon className="h-6 w-6" />}
            title="No discussions found"
            description={
              query || role || statusParam
                ? "Nothing matches those filters yet."
                : "Nobody has asked anything yet. Be the first — owners and verified vets both answer here."
            }
            action={
              !compact && (query || role || statusParam) ? (
                <Button
                  variant="secondary"
                  onClick={() => updateFilters({ q: "", role: "", status: "", page: 1 })}
                >
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        )}
        {!isLoading && !loadError && posts.map((post) => (
          <PostItem key={post.id} post={post} compact={compact} />
        ))}
      </div>

      {!compact && !isLoading && !loadError && posts.length > 0 && (
        <nav className="mt-5 flex items-center justify-between border-t border-slate-200 pt-4" aria-label="Community pages">
          <Button variant="secondary" disabled={page === 1} onClick={() => updateFilters({ page: page - 1 })}>
            <ChevronLeftIcon className="h-4 w-4" /> Previous
          </Button>
          <span className="text-sm text-slate-500">Page {page}</span>
          <Button variant="secondary" disabled={!hasNextPage} onClick={() => updateFilters({ page: page + 1 })}>
            Next <ChevronRightIcon className="h-4 w-4" />
          </Button>
        </nav>
      )}
    </section>
  );
}
